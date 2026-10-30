from pathlib import Path
from xml.etree import ElementTree as ET
from html.parser import HTMLParser
import re
base = 'https://atlas.mazunin.science/'
pages = list(Path('dist').rglob('*.html'))
indexed = []
class Head(HTMLParser):
    def __init__(self, html):
        super().__init__(); self.links = []; self.feed(html)
    def handle_starttag(self, tag, attrs):
        if tag == 'link': self.links.append(dict(attrs))
for page in pages:
    html = page.read_text()
    path = page.relative_to('dist').as_posix()
    if path.startswith(('ru/', 'en/', 'es/', 'zh-Hans/', 'ar/')):
        assert re.search(r'<meta\b[^>]*name="robots"[^>]*content="index, follow"', html), page
        assert not re.search(r'<meta\b[^>]*name=[\"\x27]robots[\"\x27][^>]*content=[\"\x27][^\"\x27]*noindex', html, re.I), page
        assert 'language-switch' in html and 'http-equiv="refresh"' not in html, page
        links = Head(html).links
        canonical = base + path.removesuffix('index.html')
        assert [l['href'] for l in links if l.get('rel') == 'canonical'] == [canonical], page
        expected = {lang: base + re.sub(r'^(ru|en|es|zh-Hans|ar)/', lang+'/', path).removesuffix('index.html') for lang in ['ru', 'en', 'es', 'zh-Hans', 'ar']}
        assert {l['hreflang']: l['href'] for l in links if l.get('rel') == 'alternate'} == expected, page
        indexed.append(canonical)
    else:
        assert 'noindex' in html, page
assert len(indexed) == 110, len(indexed)
sitemap = ET.parse('dist/sitemap.xml')
ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9', 'x': 'http://www.w3.org/1999/xhtml'}
urls = sitemap.findall('s:url', ns)
assert len(urls) == 110
assert {u.findtext('s:loc', namespaces=ns) for u in urls} == set(indexed)
for entry in urls:
    location = entry.findtext('s:loc', namespaces=ns)
    assert {l.attrib['hreflang']: l.attrib['href'] for l in entry.findall('x:link', ns)} == {lang: re.sub(r'/(ru|en|es|zh-Hans|ar)/', '/'+lang+'/', location, count=1) for lang in ['ru','en','es','zh-Hans','ar']}
assert Path('dist/robots.txt').read_text() == f'User-agent: *\nAllow: /\nSitemap: {base}sitemap.xml\n'
print(f'PASS: {len(indexed)} indexable RU/EN/ES/ZH/AR pages; reciprocal hreflang, canonical URLs and sitemap')
