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
