#!/usr/bin/env python3
"""Fail closed if any generated preview page is indexable or absent."""
from html.parser import HTMLParser
from pathlib import Path
import sys

root = Path(sys.argv[1])
langs = ['ru', 'en', 'es', 'zh-Hans', 'ar']
class Head(HTMLParser):
    def __init__(self):
        super().__init__(); self.robots = []; self.canonical = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'meta' and a.get('name', '').lower() == 'robots': self.robots.append(a.get('content', '').lower())
        if tag == 'link' and a.get('rel') == 'canonical': self.canonical.append(a.get('href'))
for lang in langs:
    pages = sorted((root / lang).rglob('index.html'))
    assert len(pages) == 22, (lang, len(pages))
    for page in pages:
        text = page.read_text(encoding='utf-8'); parser = Head(); parser.feed(text)
        assert parser.robots and all('noindex' in r for r in parser.robots), page
        assert not parser.canonical, page
        assert 'language-switch' in text and 'http-equiv="refresh"' not in text, page
for page in [root / 'index.html', root / '404.html']:
    parser = Head(); parser.feed(page.read_text(encoding='utf-8'))
    assert parser.robots and all('noindex' in r for r in parser.robots), page
assert not (root / 'sitemap.xml').exists(), 'Preview must not contain an indexable sitemap'
print('PASS: 110 language pages and root/404 are noindex; no sitemap')
