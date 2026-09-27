"""Build and publish complete, hashed snapshots without replacing good dates with failures."""
from __future__ import annotations
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def snapshot(events, dates, *, now=None):
    rows = sorted(events, key=lambda r: (r['report_date'], r['event_type'], r['licence_number'], r['id']))
    seen = set()
    for row in rows:
        if row['id'] in seen:
            raise ValueError('duplicate event ID in snapshot')
        seen.add(row['id'])
    raw = ''.join(json.dumps(r, ensure_ascii=False, sort_keys=True, allow_nan=False)+'\n' for r in rows).encode()
    digest = hashlib.sha256(raw).hexdigest()
    dates = sorted(dates, key=lambda r: r['date'])
    if len({r['date'] for r in dates}) != len(dates):
        raise ValueError('duplicate date in coverage')
    loaded = [r['date'] for r in dates if r['status'] in ('loaded', 'empty')]
    if any(r['report_date'] not in loaded for r in rows):
        raise ValueError('event has no successfully loaded source date')
    manifest = {
        'schema_version': 1, 'export_file': f'events-{digest}.jsonl', 'export_sha256': digest,
        'data_as_of': now or datetime.now(timezone.utc).isoformat(),
        'date_from': dates[0]['date'] if dates else None, 'date_to': dates[-1]['date'] if dates else None,
        'event_count': len(rows), 'counts_by_type': dict(Counter(r['event_type'] for r in rows)),
        'coverage': {'reports_loaded': len(loaded), 'loaded_dates': loaded,
            'empty_dates': [r['date'] for r in dates if r['status']=='empty'],
            'missing_dates': [r['date'] for r in dates if r['status']=='missing'],
            'failed_dates': [r['date'] for r in dates if r['status']=='failed'],
            'parse_issue_count': sum(r.get('parse_issue_count', 0) for r in dates),
            'parse_issues_by_date': {r['date']:r['parse_issue_count'] for r in dates if r.get('parse_issue_count')},
            'retry_failed_dates': [r['date'] for r in dates if r.get('last_attempt',{}).get('status') in ('failed','missing')]},
        'dates': dates,
        'attribution': 'Alberta Energy Regulator ST1; preliminary; noncommercial educational demo, not official or endorsed.'}
    return raw, manifest


def merge_reports(old_events, old_dates, replacements, attempts):
    """Only valid replacement days supersede published data; failures stay visible."""
    date_rows = {r['date']: dict(r) for r in old_dates}
    replacement_days = set(replacements)
    events = [r for r in old_events if r['report_date'] not in replacement_days]
    events.extend(r for rows in replacements.values() for r in rows)
    for attempt in attempts:
        day = attempt['date']
        if day in replacement_days:
            date_rows[day] = attempt
        elif day in date_rows and date_rows[day]['status'] in ('loaded','empty'):
            date_rows[day]['last_attempt'] = attempt
        else:
            date_rows[day] = attempt
    return events, list(date_rows.values())


def write_local(output: Path, raw: bytes, manifest: dict):
    output.mkdir(parents=True, exist_ok=True)
    (output/manifest['export_file']).write_bytes(raw)
    temp = output/'manifest.pending.json'
    temp.write_text(json.dumps(manifest, indent=2, allow_nan=False)+'\n')
    temp.replace(output/'manifest.json')


def publish_s3(client, bucket, raw, manifest, *, previous_etag=None):
    if hashlib.sha256(raw).hexdigest() != manifest['export_sha256']:
        raise ValueError('export hash mismatch')
    client.put_object(Bucket=bucket, Key='published/'+manifest['export_file'], Body=raw, ContentType='application/x-ndjson')
    body=json.dumps(manifest, sort_keys=True, allow_nan=False).encode()
    stamp=hashlib.sha256(body).hexdigest()
    client.put_object(Bucket=bucket, Key=f'history/manifests/{stamp}.json', Body=body, ContentType='application/json')
    # Compare-and-swap prevents overlapping daily invocations from losing days.
    condition={'IfMatch':previous_etag} if previous_etag else {'IfNoneMatch':'*'}
    client.put_object(Bucket=bucket, Key='published/manifest.json', Body=body, ContentType='application/json', **condition)
