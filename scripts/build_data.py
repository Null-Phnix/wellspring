"""Prepare August plus September-to-date from public ST1, retaining exact raw input."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
import hashlib,json
from pathlib import Path
from wellspring.ingest.fetch import archive_members, day_url, download
from wellspring.ingest.parser import parse_report
from wellspring.ingest.publish import snapshot, write_local
from wellspring.ingest.models import ReportError


def get_day(day, rawdir):
    url=day_url(day);p=rawdir/f'{day.isoformat()}.txt'
    if p.exists():
        cached=p.read_bytes()
        try:
            report=parse_report(cached,source_url=url,expected_date=day.isoformat())
            if report.issues:raise ReportError('cached report is incomplete')
        except ReportError:
            # Retain rejected bytes by hash before replacing the rolling cache.
            (rawdir/f'{hashlib.sha256(cached).hexdigest()}.txt').write_bytes(cached)
        else:
            return (day.isoformat(),url,cached,None,datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat())
    result=download(url)
    if result.status=='downloaded':p.write_bytes(result.raw)
    return (day.isoformat(),url,result.raw,result.status if result.status!='downloaded' else None,datetime.now(timezone.utc).isoformat())


def main():
    output=Path('output/source-data');output.mkdir(parents=True,exist_ok=True)
    rawdir=output/'raw';rawdir.mkdir(exist_ok=True)
    sources=[]
    archive=Path('fixtures/dwll2026-08.zip').read_bytes()
    (rawdir/'dwll2026-08.zip').write_bytes(archive)
    provenance=json.loads(Path('fixtures/sources.json').read_text())
    archive_time=next(r['retrieved_at'] for r in provenance['sources'] if r['file']=='dwll2026-08.zip')
    for day,(name,raw) in archive_members(archive,2026,8).items():
        sources.append((day,'https://www.aer.ca/prd/data/well-lic/dwll2026-08.zip#'+name,raw,None,archive_time))
    with ThreadPoolExecutor(max_workers=3) as pool:
        sources.extend(pool.map(lambda n:get_day(date(2026,9,n),rawdir),range(1,27)))
    events=[];dates=[]
    for day,url,raw,error,retrieved_at in sorted(sources):
        if raw is None:
            dates.append({'date':day,'status':'missing' if error=='missing' else 'failed','reason':error});continue
        digest=hashlib.sha256(raw).hexdigest();(rawdir/f'{digest}.txt').write_bytes(raw)
        try:
            r=parse_report(raw,source_url=url,expected_date=day,retrieved_at=retrieved_at)
            if r.issues:raise ReportError(f'{len(r.issues)} parse issues')
            events.extend(e.to_dict() for e in r.events)
            dates.append({'date':day,'status':r.status,'sha256':digest,'source_url':url})
        except ReportError as exc:dates.append({'date':day,'status':'failed','reason':str(exc),'parse_issue_count':1})
    raw,manifest=snapshot(events,dates)
    write_local(output,raw,manifest)
    print(json.dumps({'events':len(events),'coverage':manifest['coverage'],'output':str(output)}))

if __name__=='__main__':main()
