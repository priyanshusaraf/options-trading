#!/usr/bin/env python3
"""Bounded, serial, cached public-site inventory; never marks content reviewed.

This is an audit evidence collector, not product infrastructure. No dependencies.
Only first-party HTML is traversed; external links and embedded assets are recorded.
PDF annotation links and external one-hop resources require subsequent review.
"""
from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

HOST = 'martin.kleppmann.com'
UA = 'StrategyOS-ReferenceAudit/1.0 (serial bounded public research)'
ROOTS = ['https://' + HOST + p for p in ('/', '/archive.html', '/talks.html', '/2020/11/18/distributed-systems-and-elliptic-curves.html')]
ASSETS = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.css', '.js', '.woff', '.woff2', '.mp3', '.mp4', '.webm'}


def canonical(url: str, base: str) -> str | None:
    p = urllib.parse.urlsplit(urllib.parse.urljoin(base, url))
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
        return None
    host = p.hostname.lower()
    scheme = 'https' if host == HOST else p.scheme
    netloc = host + (':' + str(p.port) if p.port else '')
    return urllib.parse.urlunsplit((scheme, netloc, p.path or '/', p.query, ''))


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.edges = []
        self.title = []
        self.text = []
        self.in_title = False
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'title': self.in_title = True
        if tag in ('script', 'style'): self.skip += 1
        key = 'href' if tag == 'a' else 'src' if tag in ('img', 'iframe', 'source') else None
        if key and attrs.get(key): self.edges.append((tag, attrs[key]))

    def handle_endtag(self, tag):
        if tag == 'title': self.in_title = False
        if tag in ('script', 'style'): self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if self.in_title: self.title.append(data)
        if not self.skip and data.strip(): self.text.append(data.strip())


def write_json(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    tmp.replace(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cache', required=True, type=Path)
    ap.add_argument('--max-fetches', type=int, default=700)
    ap.add_argument('--delay', type=float, default=1.0)
    args = ap.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    index_path = args.cache / 'inventory.json'
    rows = json.loads(index_path.read_text()) if index_path.exists() else {}
    robots_url = 'https://' + HOST + '/robots.txt'
    req = urllib.request.Request(robots_url, headers={'User-Agent': UA})
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            robots = response.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as exc:
        if exc.code not in (404, 410): raise
        robots = ''
    (args.cache / 'robots.txt').write_text(robots)
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(robots.splitlines())
    delay = max(1.0, args.delay, rp.crawl_delay(UA) or rp.crawl_delay('*') or 0)

    def add(url, source, tag='a'):
        if url not in rows:
            first = urllib.parse.urlsplit(url).hostname == HOST
            suffix = Path(urllib.parse.urlsplit(url).path).suffix.lower()
            asset = suffix in ASSETS or tag in ('img', 'source')
            rows[url] = {'url': url, 'source_pages': [], 'first_party': first,
                         'kind': 'asset' if asset else 'content', 'status': 'pending' if first and not asset else 'asset_inventory_only' if asset else 'external_pending_triage',
                         'read_status': 'not_read', 'visuals_inspected': False}
        if source not in rows[url]['source_pages']: rows[url]['source_pages'].append(source)

    for root in ROOTS: add(root, 'owner-mandate-root')
    write_json(index_path, rows)
    fetched = 0
    while fetched < args.max_fetches:
        pending = [u for u, r in rows.items() if r['status'] == 'pending']
        if not pending: break
        url = pending[0]
        row = rows[url]
        if not rp.can_fetch(UA, url):
            row['status'] = 'robots_disallowed'; write_json(index_path, rows); continue
        suffix = Path(urllib.parse.urlsplit(url).path).suffix.lower()
        if suffix in {'.zip', '.gz', '.tgz', '.exe', '.dmg', '.tar', '.xml'}:
            row['status'] = 'download_deferred'; write_json(index_path, rows); continue
        time.sleep(delay)
        fetched += 1
        row['accessed_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=25) as response:
                data = response.read(30 * 1024 * 1024 + 1)
                row.update(http_status=response.status, final_url=response.url, content_type=response.headers.get_content_type())
                if len(data) > 30 * 1024 * 1024:
                    row['status'] = 'size_limit_deferred'; continue
            digest = hashlib.sha256(data).hexdigest()
            (args.cache / digest).write_bytes(data)
            row.update(status='fetched', checksum=digest, bytes=len(data), cache_file=digest)
            if row['content_type'] == 'text/html':
                page = Page(); page.feed(data.decode('utf-8', 'replace'))
                row['title'] = ' '.join(page.title).strip()
                (args.cache / (digest + '.txt')).write_text('\n'.join(page.text) + '\n')
                row['outgoing'] = []
                for tag, href in page.edges:
                    target = canonical(href, row['final_url'])
                    if target:
                        row['outgoing'].append({'url': target, 'tag': tag})
                        add(target, url, tag)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            row.update(status='fetch_error', error=str(exc))
        finally:
            write_json(index_path, rows)
        if fetched % 25 == 0:
            print(json.dumps({'fetched_this_run': fetched, 'urls': len(rows), 'pending': sum(r['status'] == 'pending' for r in rows.values())}), flush=True)
    print(json.dumps({'fetched_this_run': fetched, 'urls': len(rows), 'pending': sum(r['status'] == 'pending' for r in rows.values())}), flush=True)


if __name__ == '__main__': main()
