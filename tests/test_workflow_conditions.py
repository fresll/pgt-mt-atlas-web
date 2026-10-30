"""Exercise job gates against the checked-in Actions expressions, without deploying."""
import ast
from pathlib import Path
import re
import unittest

WORKFLOW = Path(__file__).resolve().parents[1] / '.github/workflows/atlas.yml'


def job_condition(job):
    text = WORKFLOW.read_text()
    section = re.search(rf'^  {job}:\n(.*?)(?=^  [a-z_]+:\n|\Z)', text, re.M | re.S)
    if not section:
        raise AssertionError(f'Missing job: {job}')
    match = re.search(r'^    if: (.+)$', section.group(1), re.M)
    if not match:
        raise AssertionError(f'Missing condition: {job}')
    return match.group(1)


def evaluate(condition, values):
    # Only accept the grammar used by these three job gates.
    expression = condition.replace('always()', 'True').replace('cancelled()', str(values['cancelled']))
    for key in sorted((key for key in values if key != 'cancelled'), key=len, reverse=True):
        expression = expression.replace(key, repr(values[key]))
    expression = re.sub(r'!(?!=)', ' not ', expression.replace('&&', ' and ').replace('||', ' or '))
    tree = ast.parse(expression.strip(), mode='eval')
    allowed = (ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not,
               ast.Compare, ast.Eq, ast.NotEq, ast.Constant, ast.Load)
    if any(not isinstance(node, allowed) for node in ast.walk(tree)):
        raise AssertionError(f'Unexpected condition syntax: {condition}')
    return bool(eval(compile(tree, '<workflow condition>', 'eval'), {'__builtins__': {}}, {}))


class WorkflowConditions(unittest.TestCase):
    def scenario(self, event, mode, select_result, needs_update, build_result, build_mode, cancelled=False):
        values = {'github.event_name': event, 'inputs.mode': mode,
                  'needs.select.result': select_result, 'needs.select.outputs.needs_update': needs_update,
                  'needs.build.result': build_result, 'needs.build.outputs.mode': build_mode,
                  'cancelled': cancelled}
        return tuple(evaluate(job_condition(job), values) for job in ('select', 'build', 'deploy'))

    def test_manual_release_and_previews(self):
        self.assertEqual(self.scenario('workflow_dispatch', 'release', 'skipped', '', 'success', 'release'), (False, True, True))
        self.assertEqual(self.scenario('workflow_dispatch', 'preview', 'skipped', '', 'success', 'preview'), (False, True, False))
        self.assertEqual(self.scenario('workflow_dispatch', 'sync-preview', 'success', 'true', 'success', 'preview'), (True, True, False))
        self.assertEqual(self.scenario('workflow_dispatch', 'sync-preview', 'success', 'false', 'skipped', ''), (True, False, False))

    def test_failed_or_cancelled_build_never_deploys(self):
        for result in ('failure', 'cancelled', 'skipped'):
            with self.subTest(result=result):
                self.assertFalse(self.scenario('workflow_dispatch', 'release', 'skipped', '', result, 'release')[2])
        self.assertFalse(self.scenario('workflow_dispatch', 'release', 'skipped', '', 'success', 'release', cancelled=True)[1])
        self.assertFalse(self.scenario('workflow_dispatch', 'release', 'skipped', '', 'success', 'release', cancelled=True)[2])

    def test_schedule_release_only_when_selection_and_build_succeed(self):
        self.assertEqual(self.scenario('schedule', '', 'success', 'true', 'success', 'release'), (True, True, True))
        for result, update in [('success', 'false'), ('failure', 'true'), ('cancelled', 'true')]:
            with self.subTest(result=result, update=update):
                self.assertFalse(self.scenario('schedule', '', result, update, 'skipped', '')[1])
                self.assertFalse(self.scenario('schedule', '', result, update, 'skipped', '')[2])
        self.assertFalse(self.scenario('schedule', '', 'success', 'true', 'success', 'release', cancelled=True)[2])

    def test_schedule_remains_disabled(self):
        text = WORKFLOW.read_text()
        self.assertNotRegex(text, r'(?m)^  schedule:')


if __name__ == '__main__':
    unittest.main()
