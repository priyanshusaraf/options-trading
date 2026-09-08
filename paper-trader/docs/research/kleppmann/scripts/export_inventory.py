#!/usr/bin/env python3
"""Derive tracked manifests from ignored crawl evidence and explicit reviews."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re


def source_id(url):
    return 'k-' + hashlib.sha256(url.encode()).hexdigest()[:16]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows = json.loads((args.cache / 'inventory.json').read_text())
    reviews = json.loads((args.output / 'source-reviews.json').read_text())
    priority = json.loads((args.output / 'priority-sources.json').read_text())
    priority_by_url = {r['url']: r for r in priority}
    triage_path = args.output / 'one-hop-triage.jsonl'
    triage = ([json.loads(line) for line in triage_path.read_text().splitlines()
               if line.strip()] if triage_path.exists() else [])
    pdf_review_path = args.output / 'pdf-review-ledger.json'
    pdf_review = (json.loads(pdf_review_path.read_text())
                  if pdf_review_path.exists() else {'sources': []})
    pdf_path = args.cache / 'pdf-metadata.json'
    pdfs = json.loads(pdf_path.read_text()) if pdf_path.exists() else {}
    seen_hashes = {}
    manifest = []
    external = []
    assets = []
    for url, row in sorted(rows.items()):
        if row['kind'] == 'asset':
            assets.append({'url': url, 'source_pages': row['source_pages'], 'status': row['status']})
            continue
        if not row['first_party']:
            external.append({'url': url, 'source_pages': row['source_pages'],
                             'status': row['status'],
                             'reason': 'Direct external link recorded; eligibility for one-hop artifact/course/high-priority review not yet decided.'})
            continue
        review = reviews.get(url, {})
        ranked = priority_by_url.get(url, {})
        digest = row.get('checksum')
        duplicate = seen_hashes.get(digest) if digest else None
        if digest and digest not in seen_hashes: seen_hashes[digest] = source_id(url)
        content = row.get('content_type')
        pdf = pdfs.get(url, {})
        date = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
        published = '-'.join(date.groups()) if date else None
        raw = (args.cache / digest).read_bytes() if digest else b''
        license_url = 'https://creativecommons.org/licenses/by/3.0/' if b'creativecommons.org/licenses/by/3.0/' in raw and content == 'text/html' else None
        manifest.append({
            'source_id': source_id(url), 'canonical_url': url,
            'source_page_url': next((p for p in row['source_pages'] if p.startswith('http')), None),
            'discovered_from': row['source_pages'], 'content_type': content,
            'artifact_type': 'pdf' if content == 'application/pdf' else 'web_page' if content == 'text/html' else 'unclassified',
            'first_party_or_external': 'first_party', 'title': row.get('title') or pdf.get('title'),
            'authors': pdf.get('author') or ('Martin Kleppmann' if 'blog' in row.get('title', '') else None),
            'published_date': published, 'published_date_basis': 'URL path; not independently verified' if published else None,
            'accessed_date': row.get('accessed_at'), 'page_or_slide_count': pdf.get('pages'),
            'checksum': digest, 'license': license_url, 'license_basis': 'Page footer; excludes separately licensed artifacts' if license_url else 'not verified',
            'transcript_available': None, 'visuals_inspected': review.get('visuals_inspected', False),
            'crawl_status': row['status'], 'http_status': row.get('http_status'), 'error': row.get('error'),
            'final_url': row.get('final_url'), 'duplicate_of': duplicate,
            'relevance_tier': ranked.get('tier', 'UNSCREENED'),
            'relevance_dimensions': ranked.get('scores'),
            'relevance_basis': ranked.get('reason', 'Not screened; no relevance judgment from title alone'),
            'strategy_os_domains': ranked.get('domains', []),
            'review_status': review.get('status', 'not_read'),
            'reviewed_sections': review.get('sections', []),
            'summary': review.get('summary'), 'key_claims': review.get('claim_ids', []),
            'limitations_or_age_risk': review.get('limitations', 'Not reviewed; date/title/fetch do not prove applicability'),
            'code_actionability': review.get('code_actionability', 'not_assessed'),
            'notes_path': review.get('notes_path'),
        })
    for name, values in [('corpus-manifest.jsonl', manifest), ('deferred-external-links.jsonl', external), ('assets-inventory.jsonl', assets)]:
        (args.output / name).write_text(''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n' for r in values))
    with (args.output / 'corpus-manifest.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(manifest[0]) if manifest else [])
        writer.writeheader()
        for row in manifest:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in row.items()})
    summary = {
        'first_party_content_records': len(manifest),
        'external_direct_links_recorded': len(external),
        'external_direct_links_triaged': len(triage),
        'external_direct_links_pending_triage': max(0, len(external) - len(triage)),
        'assets_inventoried': len(assets), 'all_discovered_urls': len(rows),
        'crawl_statuses': dict(Counter(r['crawl_status'] for r in manifest)),
        'review_statuses': dict(Counter(r['review_status'] for r in manifest)),
        'tiers': dict(Counter(r['relevance_tier'] for r in manifest)),
        'content_types': dict(Counter(r['content_type'] or 'unknown' for r in manifest)),
        'byte_duplicates': sum(r['duplicate_of'] is not None for r in manifest),
        'first_party_html_frontier_pending': sum(r['crawl_status'] == 'pending' for r in manifest),
        'one_hop_categories': dict(Counter(r['category'] for r in triage)),
        'one_hop_dispositions': dict(Counter(r['disposition'] for r in triage)),
        'selected_pdf_pages_directly_inspected': sum(
            int(r['pages']) for r in pdf_review['sources']),
        'selected_pdf_count_directly_inspected': len(pdf_review['sources']),
        'html_crawl_rerun_for_continuation': False,
        'all_mandate_coverage_complete': False,
        'limits': [
            'Triage is complete, but deferred one-hop artifacts are not retrieved or read',
            'PDF annotation links were not recursively traversed',
            'Unselected high-priority PDFs, slide decks and video transcripts remain incomplete',
            'The DDIA 2e book text was unavailable; official TOC and licensed companion references only',
            'All-domain code audits and final review remain incomplete',
        ],
    }
    (args.output / 'coverage.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__': main()
