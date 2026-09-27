import hashlib,io,json
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from wellspring.ingest.cloud import run
from wellspring.ingest.publish import snapshot
import pytest

class Missing(Exception):
    response={'Error':{'Code':'NoSuchKey'}}

class S3:
    def __init__(self):self.objects={};self.calls=[]
    def get_object(self,**kw):
        if kw['Key'] not in self.objects:raise Missing()
        return {'Body':io.BytesIO(self.objects[kw['Key']]),'ETag':'"previous"'}
    def put_object(self,**kw):
        self.calls.append(kw);self.objects[kw['Key']]=kw['Body']


def test_cloud_real_day_then_failure_keeps_valid_data():
    client=S3();raw=Path('fixtures/WELLS0925.TXT').read_bytes()
    first=run(client,'test',[date(2026,9,25)],fetch=lambda _:SimpleNamespace(status='downloaded',raw=raw))
    assert first['event_count']==48
    prior=json.loads(client.objects['published/manifest.json'])
    second=run(client,'test',[date(2026,9,25)],fetch=lambda _:SimpleNamespace(status='failed',raw=None))
    assert second['event_count']==48
    current=json.loads(client.objects['published/manifest.json'])
    assert current['export_sha256']==prior['export_sha256']
    assert current['dates'][0]['last_attempt']['status']=='failed'
    assert client.calls[-1]['IfMatch']=='"previous"'


def test_wrong_header_never_becomes_empty_report():
    client=S3();raw=Path('fixtures/WELLS0925.TXT').read_bytes()
    r=run(client,'test',[date(2026,9,26)],fetch=lambda _:SimpleNamespace(status='downloaded',raw=raw))
    assert r['event_count']==0 and r['attempts'][0]['status']=='failed'
    m=json.loads(client.objects['published/manifest.json'])
    assert m['coverage']['empty_dates']==[]
    assert m['coverage']['failed_dates']==['2026-09-26']


def test_corrupt_previous_snapshot_fails_without_any_write():
    client=S3();raw,m=snapshot([],[])
    client.objects['published/manifest.json']=json.dumps(m).encode()
    client.objects['published/'+m['export_file']]=b'changed'
    with pytest.raises(ValueError,match='hash mismatch'):run(client,'test',[])
    assert client.calls==[]


def test_data_read_failure_is_not_new_empty_snapshot():
    class Denied(S3):
        def get_object(self,**kw):raise PermissionError('denied')
    client=Denied()
    with pytest.raises(PermissionError):run(client,'test',[])
    assert client.calls==[]


def test_repeat_identical_source_retains_original_provenance():
    client=S3();raw=Path('fixtures/WELLS0925.TXT').read_bytes()
    fetch=lambda _:SimpleNamespace(status='downloaded',raw=raw)
    a=run(client,'test',[date(2026,9,25)],fetch=fetch)
    b=run(client,'test',[date(2026,9,25)],fetch=fetch)
    assert a['export_sha256']==b['export_sha256']


def test_unsupported_surface_dls_publishes_day_with_null_map_position():
    raw=Path('fixtures/WELLS0925.TXT').read_bytes().replace(b'16-12-066-03W4',b'16-12-066-03W3',1)
    client=S3()
    result=run(client,'test',[date(2026,9,25)],fetch=lambda _:SimpleNamespace(status='downloaded',raw=raw))
    assert result['event_count']==48 and result['attempts'][0]['status']=='loaded'
    manifest=json.loads(client.objects['published/manifest.json'])
    rows=[json.loads(line) for line in client.objects['published/'+manifest['export_file']].splitlines()]
    target=next(r for r in rows if r['licence_number']=='0456133')
    assert target['latitude'] is None and target['longitude'] is None
    assert target['location_reason']=='invalid_surface_dls'
    assert manifest['coverage']['reports_loaded']==1
    assert manifest['coverage']['failed_dates']==[]
