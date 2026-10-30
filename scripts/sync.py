#!/usr/bin/env python3
"""Fail closed unless the newest Pages deployment is a verified source workflow run."""
import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.request

API = 'https://api.github.com'
SOURCE = 'fresll/pgt-mt-atlas'
TARGET = 'fresll/pgt-mt-atlas-web'
DOMAIN = 'https://atlas.mazunin.science/'
SHA = re.compile(r'^[0-9a-f]{40}$')


def get(url, github=False):
    headers = {'User-Agent': 'atlas-sync-check', 'Cache-Control': 'no-cache'}
    if github:
        headers.update({'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'})
        if os.getenv('GH_TOKEN'):
            headers['Authorization'] = 'Bearer ' + os.environ['GH_TOKEN']
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
        if not github and response.geturl().split('?', 1)[0] != DOMAIN + 'atlas-provenance.json':
            raise ValueError('Unexpected provenance redirect')
        return json.load(response)


def source_version():
    deployments = get(f'{API}/repos/{SOURCE}/deployments?environment=github-pages&per_page=1', True)
    if not deployments:
        raise ValueError('No source Pages deployment found')
    deployment = deployments[0]
    statuses = get(f"{API}/repos/{SOURCE}/deployments/{deployment['id']}/statuses?per_page=1", True)
    if not statuses or statuses[0]['state'] != 'success':
        raise ValueError('Newest source deployment is not successfully completed')
    status = statuses[0]
    if deployment['ref'] not in ('main', 'refs/heads/main') or status.get('environment_url', '').rstrip('/') != 'https://fresll.github.io/pgt-mt-atlas':
        raise ValueError('Newest source deployment has an unexpected branch or address')
    match = re.fullmatch(r'https://github\.com/fresll/pgt-mt-atlas/actions/runs/(\d+)/job/\d+', status.get('log_url', ''))
    if not match:
        raise ValueError('Source deployment does not identify its workflow run')
    run = get(f'{API}/repos/{SOURCE}/actions/runs/{match[1]}', True)
    sha = deployment['sha']
    if not SHA.fullmatch(sha) or run.get('head_sha') != sha or run.get('head_branch') != 'main' or run.get('path') != '.github/workflows/deploy-pages.yml' or run.get('status') != 'completed' or run.get('conclusion') != 'success':
        raise ValueError('Source deployment is not backed by a successful matching workflow')
    return sha, match[1]


def target_version():
    data = get(DOMAIN + 'atlas-provenance.json?sync-check=' + str(int(dt.datetime.now(dt.timezone.utc).timestamp())))
    sha = data.get('source_sha', '')
    if data.get('source_repository') != SOURCE or data.get('mode') != 'release' or data.get('base') != '/' or data.get('canonical_base') != DOMAIN or not SHA.fullmatch(sha):
        raise ValueError('Published provenance is invalid')
    when = 'unknown (no confirmed automatic synchronization in current manifest)'
    run_id = str(data.get('publication_run_id', ''))
    if run_id.isdecimal():
        run = get(f'{API}/repos/{TARGET}/actions/runs/{run_id}', True)
        if (run.get('status') == 'completed' and run.get('conclusion') == 'success'
                and run.get('event') == 'schedule' and run.get('head_sha') == data.get('configuration_sha')
                and run.get('path') == '.github/workflows/atlas.yml'):
            when = run['updated_at']
        elif run.get('status') != 'completed' or run.get('conclusion') != 'success':
            when = 'unconfirmed: publication workflow has not completed successfully'
    return sha, when


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--expect', default='')
    args = parser.parse_args()
    source = target = 'unknown'
    when = 'unknown'
    reason = 'check failed'
    try:
        source, run = source_version()
        target, when = target_version()
        if args.expect and source != args.expect:
            raise ValueError('Source publication changed during build; stale deployment refused')
        reason = 'Already synchronized; no deployment needed' if source == target else 'New verified source publication available'
        if args.expect and source == target:
            raise ValueError('Target already has this source SHA; redundant deployment refused')
        print(f'Source workflow run: {run}')
        if os.getenv('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'], 'a') as out:
                out.write(f'sha={source}\nneeds_update={str(source != target).lower()}\n')
    except Exception as exc:
        reason = f'Error: {exc}'
        print(reason, file=sys.stderr)
        status = 1
    else:
        status = 0
    report = f'### Atlas synchronization\n\n- Source published SHA: `{source}`\n- New domain SHA: `{target}`\n- Versions match: {"unknown" if "unknown" in (source, target) else ("yes" if source == target else "no")}\n- Last confirmed automatic synchronization: {when}\n- Result: {reason}\n'
    print(report)
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as out:
            out.write(report)
    return status

if __name__ == '__main__':
    sys.exit(main())
