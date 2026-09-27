import importlib.util,sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import deploy

def test_publish_refuses_enabled_or_unknown_schedule():
    for state in ('ENABLED',None):
        stack={'StackStatus':'UPDATE_COMPLETE','Parameters':([] if state is None else [{'ParameterKey':'ScheduleState','ParameterValue':state}])}
        with pytest.raises(ValueError,match='Disable'):deploy.require_publish_ready(stack)

def test_publish_refuses_incomplete_stack():
    with pytest.raises(ValueError,match='completed'):deploy.require_publish_ready({'StackStatus':'UPDATE_IN_PROGRESS'})

def test_publish_cannot_discard_loaded_dates():
    current={'dates':[{'date':'2026-09-26','status':'loaded'}]}
    proposed={'dates':[{'date':'2026-09-26','status':'failed'}]}
    with pytest.raises(ValueError,match='discard'):deploy.require_coverage_preserved(current,proposed)

def test_verify_requires_completed_stack_before_reading_functions():
    with pytest.raises(ValueError,match='not completed'):deploy.verify_deployment({'StackStatus':'UPDATE_IN_PROGRESS'},{},{})

def test_verify_refuses_wrong_cloud_code(monkeypatch):
    stack={'StackStatus':'UPDATE_COMPLETE','Parameters':[{'ParameterKey':'CodeKey','ParameterValue':'bundle.zip'}]}
    monkeypatch.setattr(deploy,'aws',lambda *a,**kw:{'CodeSha256':'wrong','LastUpdateStatus':'Successful'})
    with pytest.raises(ValueError,match='does not match'):deploy.verify_deployment(stack,{'ApiFunction':'api'}, {'code_key':'bundle.zip','code_sha256':'0'*64})


def test_schedule_updates_preserve_provider_and_code_parameters():
    stack={'Parameters':[{'ParameterKey':'CodeKey','ParameterValue':'old.zip'},
                         {'ParameterKey':'AskEnabled','ParameterValue':'true'},
                         {'ParameterKey':'AskModel','ParameterValue':'deepseek-chat'}]}
    values=deploy.update_parameters(stack,{'ScheduleState':'DISABLED'})
    assert 'ParameterKey=AskEnabled,UsePreviousValue=true' in values
    assert 'ParameterKey=AskModel,UsePreviousValue=true' in values
    assert 'ParameterKey=CodeKey,UsePreviousValue=true' in values
    assert 'ParameterKey=ScheduleState,ParameterValue=DISABLED' in values


def test_verify_refuses_disabled_ask_when_receipt_claims_enabled():
    stack={'StackStatus':'UPDATE_COMPLETE','Parameters':[
        {'ParameterKey':'CodeKey','ParameterValue':'bundle.zip'},
        {'ParameterKey':'AskEnabled','ParameterValue':'false'}]}
    with pytest.raises(ValueError,match='AskEnabled'):
        deploy.verify_deployment(stack,{}, {'code_key':'bundle.zip','ask_enabled':True})


def test_verify_refuses_provider_parameter_drift_before_function_checks():
    stack={'StackStatus':'UPDATE_COMPLETE','Parameters':[
        {'ParameterKey':'CodeKey','ParameterValue':'bundle.zip'},
        {'ParameterKey':'AskEnabled','ParameterValue':'true'},
        {'ParameterKey':'AskModel','ParameterValue':'different'}]}
    with pytest.raises(ValueError,match='Ask configuration'):
        deploy.verify_deployment(stack,{}, {'code_key':'bundle.zip','ask_enabled':True,'ask_model':'deepseek-chat'})


def test_verify_checks_both_hashes_and_enabled_runtime_configuration(monkeypatch):
    import base64
    params={'CodeKey':'bundle.zip','AskEnabled':'true','AskModel':'deepseek-chat',
            'AskProviderUrl':'https://api.deepseek.com',
            'AskKeyParameter':'/wellspring/ask/provider_key','AskDailyLimit':'100'}
    stack={'StackStatus':'UPDATE_COMPLETE','Parameters':[{'ParameterKey':k,'ParameterValue':v} for k,v in params.items()]}
    outputs={'ApiFunction':'api','IngestFunction':'ingest','AskQuotaTable':'quota'}
    receipt={'code_key':'bundle.zip','code_sha256':'0'*64,'ask_enabled':True,
             'ask_model':'deepseek-chat','provider_url':'https://api.deepseek.com',
             'key_parameter':'/wellspring/ask/provider_key','daily_limit':'100'}
    code=base64.b64encode(bytes(32)).decode()
    env={'ASK_KEY_PARAMETER':params['AskKeyParameter'],'ASK_MODEL':params['AskModel'],
         'ASK_PROVIDER_URL':params['AskProviderUrl'],'ASK_DAILY_LIMIT':'100','ASK_QUOTA_TABLE':'quota'}
    called=[]
    def aws(*args,**kwargs):
        called.append(args)
        return {'CodeSha256':code,'LastUpdateStatus':'Successful','RevisionId':'r',
                'Environment':{'Variables':env}}
    monkeypatch.setattr(deploy,'aws',aws)
    verified=deploy.verify_deployment(stack,outputs,receipt)
    assert verified['status']=='verified_deployed' and len(called)==2
    env['ASK_KEY_PARAMETER']=''
    with pytest.raises(ValueError,match='environment'):
        deploy.verify_deployment(stack,outputs,receipt)
