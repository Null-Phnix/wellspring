"""Scheduled intake of recent complete Mountain-time days into versioned S3 snapshots."""
from __future__ import annotations
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import hashlib,json,os,re
from .fetch import day_url, download
from .parser import parse_report
from .publish import merge_reports, snapshot, publish_s3
from .models import ReportError


def _read(client, bucket, key, maximum):
    response=client.get_object(Bucket=bucket,Key=key)
    raw=response['Body'].read(maximum+1)
    if len(raw)>maximum:raise ValueError('published object exceeds size limit')
    return raw,response.get('ETag')


def run(client, bucket, days, *, fetch=download):
    try:
        manifest_raw,etag=_read(client,bucket,'published/manifest.json',2*1024*1024)
    except Exception as exc:
        code=getattr(exc,'response',{}).get('Error',{}).get('Code')
        if code not in ('NoSuchKey','404'):raise
        manifest,old_events,etag={},[],None
    else:
        manifest=json.loads(manifest_raw)
        name=manifest['export_file']
        if not re.fullmatch(r'events-[0-9a-f]{64}\.jsonl',name):raise ValueError('invalid published export name')
        raw,_=_read(client,bucket,'published/'+name,64*1024*1024)
        if hashlib.sha256(raw).hexdigest()!=manifest['export_sha256']:raise ValueError('published export hash mismatch')
        old_events=[json.loads(line) for line in raw.splitlines() if line.strip()]
    previous_dates={r["date"]:r for r in manifest.get("dates",[])}
    replacements={};attempts=[]
    for day in days:
        url=day_url(day);result=fetch(url)
        if result.status!='downloaded':
            attempts.append({'date':day.isoformat(),'status':'missing' if result.status=='missing' else 'failed','reason':result.status});continue
        raw=result.raw;digest=hashlib.sha256(raw).hexdigest()
        client.put_object(Bucket=bucket,Key=f'raw/{day.isoformat()}/{digest}.txt',Body=raw,ContentType='text/plain')
        prior=previous_dates.get(day.isoformat())
        if prior and prior.get('sha256')==digest and prior.get('status') in ('loaded','empty'):
            replacements[day.isoformat()]=[r for r in old_events if r['report_date']==day.isoformat()]
            attempts.append({k:v for k,v in prior.items() if k!='last_attempt'})
            continue
        try:
            report=parse_report(raw,source_url=url,expected_date=day.isoformat())
            if report.issues:raise ReportError(f'{len(report.issues)} parse issues')
            from wellspring.geo import enrich_event
            replacements[day.isoformat()]=[enrich_event(e.to_dict()) for e in report.events]
            attempts.append({'date':day.isoformat(),'status':report.status,'sha256':digest,'source_url':url})
        except ReportError as exc:
            attempts.append({'date':day.isoformat(),'status':'failed','reason':str(exc),'parse_issue_count':1})
    rows,date_rows=merge_reports(old_events,manifest.get('dates',[]),replacements,attempts)
    raw,new_manifest=snapshot(rows,date_rows)
    publish_s3(client,bucket,raw,new_manifest,previous_etag=etag)
    return {'event_count':len(rows),'attempts':attempts,'export_sha256':new_manifest['export_sha256']}


def lambda_handler(event, context):
    # Catch-up window absorbs weekends and short publication delays; header dates
    # still prevent yesterday's rolling filename from becoming today's record.
    today=datetime.now(ZoneInfo('America/Edmonton')).date()
    days=[today-timedelta(days=n) for n in (3,2,1)]
    import boto3
    return run(boto3.client('s3'),os.environ['DATA_BUCKET'],days)
