import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import io
import json
import signal
import threading
import time

import pytest
from wellspring.api import ask, handler, provider


@pytest.fixture
def ready(monkeypatch):
    monkeypatch.setenv('ASK_KEY_PARAMETER', '/wellspring/ask/provider_key')
    monkeypatch.setenv('ASK_QUOTA_TABLE', 'quota')
    monkeypatch.setenv('ASK_MODEL', 'deepseek-chat')
    monkeypatch.setenv('ASK_PROVIDER_URL', 'https://api.deepseek.com')
    monkeypatch.setattr(ask, 'read_key', lambda parameter: 'unit-secret')
    monkeypatch.setattr(ask, 'acquire_quota', lambda table, cap: 1)
    records = [{'id':'a','licence_number':'0000001','report_date':'2026-08-01',
                'event_type':'issued','licensee':'Public Co','substance':'GAS'}]
    dataset = handler.Dataset(records, {'date_from':'2026-08-01','date_to':'2026-08-01',
        'data_as_of':'2026-09-27T13:00:00Z','coverage':{'reports_loaded':1}})
    monkeypatch.setattr(handler, '_dataset', lambda: dataset)
    return records


def event(question='Count issued licences'):
    return {'rawPath':'/ask','requestContext':{'http':{'method':'POST'}},
            'body':json.dumps({'question':question}), 'headers':{'origin':'http://localhost:4200'}}


def invoke(request):
    response = handler.lambda_handler(request, None)
    assert response['statusCode'] == 200
    return json.loads(response['body'])


def test_stubbed_model_end_to_end_returns_query_rows_metadata_and_actual_model(ready,monkeypatch,capsys):
    monkeypatch.setattr(ask,'generate_sql',lambda *a,**kw:('SELECT count(*) AS total FROM events', 'deepseek-flash'))
    result=invoke(event('PRIVATE_SENTINEL'))
    assert result['status']=='ok' and result['rows']==[{'total':1}]
    assert result['columns']==['total'] and result['row_count']==1
    assert result['model']=='deepseek-flash' and result['refusal'] is None
    assert result['meta']['coverage']['reports_loaded']==1
    logged=capsys.readouterr().out
    assert 'PRIVATE_SENTINEL' not in logged and 'unit-secret' not in logged and 'SELECT' not in logged


@pytest.mark.parametrize('sql',[
    'INSERT INTO events(id) VALUES(\'x\')','UPDATE events SET id=\'x\'',
    'DELETE FROM events','DROP TABLE events','PRAGMA query_only=OFF',
    "ATTACH '/tmp/private' AS secret",'SELECT 1; DELETE FROM events',
    '/* hide */ DELETE FROM events','SELECT 1 -- comment','SELECT load_extension(\'bad\')',
])
def test_model_write_and_comment_tricks_are_refused(ready,monkeypatch,sql):
    monkeypatch.setattr(ask,'generate_sql',lambda *a,**kw:(sql,'test-model'))
    result=invoke(event())
    assert result['status']=='refused' and result['sql'] is None and result['rows']==[]
    assert ready[0]['id']=='a'


def test_missing_key_configuration_never_calls_model(ready,monkeypatch):
    monkeypatch.delenv('ASK_KEY_PARAMETER')
    monkeypatch.setattr(ask,'generate_sql',lambda *a,**k:pytest.fail('provider called'))
    assert invoke(event())['refusal']['code']=='ASK_UNAVAILABLE'


def test_exhausted_or_unavailable_quota_prevents_model_call(ready,monkeypatch):
    monkeypatch.setattr(ask,'acquire_quota',lambda *a: (_ for _ in ()).throw(ask.unavailable()))
    monkeypatch.setattr(ask,'generate_sql',lambda *a,**k:pytest.fail('provider called'))
    assert invoke(event())['refusal']['code']=='ASK_UNAVAILABLE'


def test_hard_deadline_interrupts_blocking_provider_and_restores_alarm(ready,monkeypatch):
    before=signal.getsignal(signal.SIGALRM)
    monkeypatch.setattr(ask,'WALL_SECONDS',0.04)
    def slow(*a,**kw):time.sleep(1);return 'SELECT 1','test'
    monkeypatch.setattr(ask,'generate_sql',slow)
    start=time.monotonic();result=invoke(event())
    assert time.monotonic()-start < 0.5
    assert result['refusal']['code']=='QUERY_TIMEOUT'
    assert signal.getsignal(signal.SIGALRM)==before
    assert signal.getitimer(signal.ITIMER_REAL)[0]==0


def test_row_cap_and_truncation_reach_http_contract(ready,monkeypatch):
    ready.extend({**ready[0],'id':str(i)} for i in range(250))
    monkeypatch.setattr(ask,'generate_sql',lambda *a,**kw:('SELECT id FROM events ORDER BY id','test'))
    result=invoke(event())
    assert result['row_count']==200 and len(result['rows'])==200 and result['truncated']


@pytest.mark.parametrize('body',['not json','[]','{}',json.dumps({'question':''}),json.dumps({'question':'x'*1201})])
def test_invalid_question_does_not_consume_quota(ready,monkeypatch,body):
    monkeypatch.setattr(ask,'acquire_quota',lambda *a:pytest.fail('quota charged'))
    request=event();request['body']=body
    assert invoke(request)['refusal']['code']=='INVALID_QUESTION'


def test_provider_exception_body_is_not_exposed(ready,monkeypatch):
    monkeypatch.setattr(ask,'generate_sql',lambda *a,**kw:(_ for _ in ()).throw(provider.ProviderUnavailable('secret-value')))
    result=invoke(event())
    assert result['refusal']['code']=='ASK_UNAVAILABLE'
    assert 'secret-value' not in json.dumps(result)


def test_atomic_daily_quota_uses_one_conditional_update_across_callers():
    class Counter:
        def __init__(self):self.count=0;self.lock=threading.Lock();self.requests=[]
        def update_item(self,**kw):
            assert kw['ConditionExpression']=='attribute_not_exists(#calls) OR #calls < :cap'
            with self.lock:
                cap=int(kw['ExpressionAttributeValues'][':cap']['N'])
                if self.count>=cap:raise RuntimeError('conditional failure')
                self.count+=1;self.requests.append(kw)
                return {'Attributes':{'calls':{'N':str(self.count)}}}
    client=Counter();now=datetime(2026,9,27,tzinfo=timezone.utc)
    def attempt(_):
        try:return ask.acquire_quota('table',10,client=client,now=now)
        except ask.AskRefusal:return None
    with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(attempt,range(40)))
    assert len([x for x in results if x is not None])==10 and client.count==10
    assert client.requests[0]['Key']=={'quota_key':{'S':'ASK#2026-09-27'}}
    assert 'question' not in json.dumps(client.requests)


def test_provider_redirects_never_receive_authorization():
    assert provider.NoRedirect().redirect_request(None,None,302,'redirect',{},'https://other.test') is None


def test_provider_endpoint_is_confined():
    with pytest.raises(provider.ProviderUnavailable):
        provider.generate_sql('count',api_key='unit-key',base_url='https://other.test',model='test',deadline=time.monotonic()+1)


def test_secret_reader_restricts_parameter_and_never_enumerates():
    class Client:
        def get_parameter(self,**kw):
            assert kw=={'Name':'/wellspring/ask/provider_key','WithDecryption':True}
            return {'Parameter':{'Value':'unit-only-secret'}}
    ask._secret_cache=None
    assert ask.read_key('/wellspring/ask/provider_key',client=Client())=='unit-only-secret'
    with pytest.raises(ask.AskRefusal):ask.read_key('/other/secret',client=Client())
    ask._secret_cache=None
