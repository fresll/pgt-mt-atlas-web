#!/usr/bin/env python3
"""Verify every deployed byte against the artifact already validated before deployment."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import quote, urljoin, urlsplit
from urllib.request import Request, urlopen

root = Path(sys.argv[1])
base = os.environ['PAGES_URL'].rstrip('/') + '/'
assert base == 'https://atlas.mazunin.science/', base
manifest_path = root / 'atlas-provenance.json'
manifest = json.loads(manifest_path.read_text())
files = dict(manifest['files_sha256'])
files['atlas-provenance.json'] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
for rel, expected in sorted(files.items()):
    url = urljoin(base, quote(rel, safe='/'))
    for attempt in range(6):
        try:
            with urlopen(Request(url, headers={'User-Agent': 'Atlas-publication-check'}), timeout=30) as response:
                assert response.status == 200, (url, response.status)
                final = urlsplit(response.url)
                assert final.scheme == 'https' and final.netloc == 'atlas.mazunin.science', response.url
                actual = hashlib.sha256(response.read()).hexdigest()
                assert actual == expected, (url, actual, expected)
            break
        except Exception:
            if attempt == 5:
                raise
            time.sleep(5)
print(f'PASS: {len(files)} published files match the verified artifact')
