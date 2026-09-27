import hashlib,json
from wellspring.ingest.publish import snapshot,merge_reports,publish_s3
import pytest


def row(day='2026-08-01',id='one'):
    return {'id':id,'report_date':day,'event_type':'issued','licence_number':'0000001'}


def test_snapshot_hash_and_coverage():
    raw,m=snapshot([row()],[{'date':'2026-08-01','status':'loaded'},{'date':'2026-08-02','status':'empty'},{'date':'2026-08-03','status':'missing'}])
    assert hashlib.sha256(raw).hexdigest()==m['export_sha256']
    assert m['coverage']['reports_loaded']==2
    assert m['coverage']['empty_dates']==['2026-08-02']
    assert m['coverage']['missing_dates']==['2026-08-03']


def test_failed_retry_keeps_valid_day():
    events,dates=merge_reports([row()],[{'date':'2026-08-01','status':'loaded'}],{},[{'date':'2026-08-01','status':'failed'}])
    assert events==[row()]
    assert dates[0]['status']=='loaded'
    assert dates[0]['last_attempt']['status']=='failed'


def test_valid_empty_replacement_removes_prior_rows():
    rows,dates=merge_reports([row()],[{'date':'2026-08-01','status':'loaded'}],{'2026-08-01':[]},[{'date':'2026-08-01','status':'empty'}])
    assert rows==[] and dates[0]['status']=='empty'


def test_publish_switches_manifest_last_and_uses_cas():
    calls=[]
    class Client:
        def put_object(self,**kw):calls.append(kw)
    raw,m=snapshot([row()],[{'date':'2026-08-01','status':'loaded'}])
    publish_s3(Client(),'bucket',raw,m,previous_etag='"old"')
    assert calls[-1]['Key']=='published/manifest.json'
    assert calls[-1]['IfMatch']=='"old"'
    assert calls[0]['Key']=='published/'+m['export_file']


def test_publish_failure_never_switches_manifest():
    calls=[]
    class Client:
        def put_object(self,**kw):
            calls.append(kw['Key'])
            raise RuntimeError('write failed')
    raw,m=snapshot([],[])
    with pytest.raises(RuntimeError):publish_s3(Client(),'bucket',raw,m)
    assert calls==['published/'+m['export_file']]


def test_invalid_snapshot_sources_refused():
    with pytest.raises(ValueError):snapshot([row()],[])
    with pytest.raises(ValueError):snapshot([row(),row()],[{'date':'2026-08-01','status':'loaded'}])


def test_failed_retry_is_visible_without_erasing_loaded_coverage():
    _,m=snapshot([row()],[{'date':'2026-08-01','status':'loaded','last_attempt':{'status':'failed'}}])
    assert m['coverage']['reports_loaded']==1
    assert m['coverage']['failed_dates']==[]
    assert m['coverage']['retry_failed_dates']==['2026-08-01']
