#!/usr/bin/env python3
"""Bind every built byte to a source commit, then verify the packaged Pages artifact."""
import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('operation', choices=['write', 'verify'])
parser.add_argument('dist', type=Path)
parser.add_argument('--source', required=True)
parser.add_argument('--mode', required=True, choices=['preview', 'release'])
parser.add_argument('--config-sha', required=True)
args = parser.parse_args()
manifest = args.dist / 'atlas-provenance.json'
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def files():
    result = {}
    for path in sorted(args.dist.rglob('*')):
        if path.is_symlink():
            raise SystemExit(f'Symlinks are not allowed: {path}')
        if path.is_file() and path != manifest:
            result[path.relative_to(args.dist).as_posix()] = digest(path)
    return result
if args.operation == 'write':
    data = {'source_repository': 'fresll/pgt-mt-atlas', 'source_sha': args.source,
            'configuration_sha': args.config_sha, 'mode': args.mode, 'base': '/',
            'canonical_base': 'https://atlas.mazunin.science/', 'files_sha256': files()}
    if not data['files_sha256']:
        raise SystemExit('Empty site')
    manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
else:
    data = json.loads(manifest.read_text())
    expected = {'source_repository': 'fresll/pgt-mt-atlas', 'source_sha': args.source,
                'configuration_sha': args.config_sha, 'mode': args.mode, 'base': '/',
                'canonical_base': 'https://atlas.mazunin.science/'}
    for key, value in expected.items():
        if data.get(key) != value:
            raise SystemExit(f'Provenance mismatch: {key}')
    if data['files_sha256'] != files():
        raise SystemExit('Artifact files differ from provenance manifest')
    print(f"PASS: {len(data['files_sha256'])} files match source {args.source} ({args.mode})")
