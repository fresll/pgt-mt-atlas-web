import contextlib
import io
import os
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import sync

SOURCE = 'a' * 40
OTHER = 'b' * 40
DEPLOY = {'id': 17, 'sha': SOURCE, 'ref': 'main'}
STATUS = {'state': 'success', 'environment_url': 'https://fresll.github.io/pgt-mt-atlas/', 'log_url': 'https://github.com/fresll/pgt-mt-atlas/actions/runs/12/job/34'}
RUN = {'head_sha': SOURCE, 'head_branch': 'main', 'path': '.github/workflows/deploy-pages.yml', 'status': 'completed', 'conclusion': 'success'}
MANIFEST = {'source_repository': sync.SOURCE, 'source_sha': OTHER, 'mode': 'release', 'base': '/', 'canonical_base': sync.DOMAIN}

class TestSync(unittest.TestCase):
    def source(self, deployment=DEPLOY, status=STATUS, run=RUN):
        with patch.object(sync, 'get', side_effect=[[deployment], [status], run]):
            return sync.source_version()
    def test_verified_deployment(self):
        self.assertEqual(self.source(), (SOURCE, '12'))
    def test_fail_closed_on_incomplete_or_failed_deployment(self):
        for state in ('in_progress', 'failure', 'queued'):
            with self.subTest(state=state), self.assertRaises(ValueError):
                self.source(status={**STATUS, 'state': state})
    def test_reject_unverified_workflows_and_domains(self):
        for run in ({**RUN, 'conclusion': 'failure'}, {**RUN, 'status':'in_progress'}, {**RUN, 'head_sha': OTHER}, {**RUN, 'path':'other.yml'}):
            with self.subTest(run=run), self.assertRaises(ValueError): self.source(run=run)
        with self.assertRaises(ValueError): self.source(status={**STATUS, 'environment_url':'https://example.com/'})
        with self.assertRaises(ValueError): self.source(deployment={**DEPLOY, 'ref':'draft'})
    def test_invalid_target_fails_closed(self):
        with patch.object(sync, 'get', return_value={**MANIFEST, 'mode':'preview'}), self.assertRaises(ValueError): sync.target_version()
    def test_reports_target_completed_workflow(self):
        with patch.object(sync, 'get', side_effect=[{**MANIFEST,'publication_run_id':'55','configuration_sha':SOURCE}, {'status':'completed','conclusion':'success','event':'schedule','head_sha':SOURCE,'path':'.github/workflows/atlas.yml','updated_at':'2026-01-01T00:00:00Z'}]):
            self.assertEqual(sync.target_version(), (OTHER,'2026-01-01T00:00:00Z'))
    def invoke(self, source, target, expected=''):
        with patch.object(sync, 'source_version', return_value=(source,'12')), patch.object(sync, 'target_version', return_value=(target,'unknown')), patch.object(sys,'argv',['sync.py']+(['--expect',expected] if expected else [])), patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return sync.main()
    def test_stale_and_duplicate_rechecks_refuse_deploy(self):
        self.assertEqual(self.invoke(SOURCE, OTHER, OTHER), 1)
        self.assertEqual(self.invoke(SOURCE, SOURCE, SOURCE), 1)
        self.assertEqual(self.invoke(SOURCE, OTHER, SOURCE), 0)
    def test_same_sha_is_successful_noop(self):
        self.assertEqual(self.invoke(SOURCE, SOURCE), 0)

if __name__ == '__main__': unittest.main()
