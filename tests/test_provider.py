import json
import time
from urllib.error import HTTPError

import pytest
from wellspring.api import provider


class Response:
    def __init__(self, raw): self.raw=raw
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def read(self, maximum): return self.raw[:maximum]


def install(monkeypatch, raw, calls=None):
    class Opener:
        def open(self, req, timeout):
            if calls is not None: calls.append((req,timeout))
            return Response(raw)
    monkeypatch.setattr(provider.request,'build_opener',lambda *a:Opener())


def generate():
    return provider.generate_sql('Count gas licences',api_key='fake-test-key',
        base_url='https://api.deepseek.com',model='deepseek-chat',deadline=time.monotonic()+3)


def test_protocol_preserves_requested_alias_and_reports_served_model(monkeypatch):
    calls=[]
    install(monkeypatch,json.dumps({'model':'deepseek-flash','choices':[{'message':{'content':'SELECT count(*) FROM events;'}}]}).encode(),calls)
    sql,model=generate()
    assert model=='deepseek-flash' and sql=='SELECT count(*) FROM events;'
    req,timeout=calls[0];payload=json.loads(req.data)
    assert req.full_url=='https://api.deepseek.com/chat/completions'
    assert payload['model']=='deepseek-chat' and payload['thinking']=={'type':'disabled'}
    assert payload['stream'] is False and payload['max_tokens']==512
    assert payload['messages'][1]['content']=='Count gas licences'
    assert 0<timeout<=3


@pytest.mark.parametrize('raw',[
    b'not JSON',b'{}',b'{"choices":[]}',
    b'{"choices":[{"message":{"content":null}}]}',
    b'{"choices":[{"message":{"content":123}}]}',
    b'x'*(provider.MAX_RESPONSE_BYTES+1),
])
def test_malformed_or_oversize_provider_output_fails_closed(monkeypatch,raw):
    install(monkeypatch,raw)
    with pytest.raises(provider.ProviderUnavailable): generate()


def test_provider_refusal_never_becomes_sql(monkeypatch):
    install(monkeypatch,b'{"model":"deepseek-flash","choices":[{"message":{"content":"REFUSE"}}]}')
    with pytest.raises(provider.ProviderRefused):generate()


def test_expired_deadline_makes_no_request(monkeypatch):
    monkeypatch.setattr(provider.request,'build_opener',lambda *a:pytest.fail('network attempted'))
    with pytest.raises(TimeoutError):
        provider.generate_sql('count',api_key='fake',base_url='https://api.deepseek.com',
                              model='deepseek-chat',deadline=time.monotonic()-1)


def test_http_failure_does_not_reveal_provider_body(monkeypatch):
    class Opener:
        def open(self,*a,**kw):raise HTTPError('https://api.deepseek.com',401,'SECRET_BODY',{},None)
    monkeypatch.setattr(provider.request,'build_opener',lambda *a:Opener())
    with pytest.raises(provider.ProviderUnavailable) as exc:generate()
    assert 'SECRET_BODY' not in str(exc.value)


@pytest.mark.parametrize('model,sql', [
    (None, 'SELECT 1'), ('fake-test-key', 'SELECT 1'),
    ('deepseek-flash', "SELECT 'fake-test-key'"),
    ('unverified-provider-model', 'SELECT 1'),
])
def test_missing_untrusted_or_secret_echo_model_metadata_is_rejected(monkeypatch, model, sql):
    body={'choices':[{'message':{'content':sql}}]}
    if model is not None:body['model']=model
    install(monkeypatch,json.dumps(body).encode())
    with pytest.raises(provider.ProviderUnavailable):generate()
