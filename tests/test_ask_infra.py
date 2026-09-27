import json
from pathlib import Path


def test_ask_roles_cannot_enumerate_secrets_or_change_counter_schema():
    template=json.loads(Path('infra/template.json').read_text())
    policies=template['Resources']['ApiRole']['Properties']['Policies']
    statements=[s for p in policies for s in p['PolicyDocument']['Statement']]
    ssm=[s for s in statements if any(a.startswith('ssm:') for a in s['Action'])]
    assert len(ssm)==1 and ssm[0]['Action']==['ssm:GetParameter']
    assert '*' not in ssm[0]['Resource']['Fn::Sub']
    assert template['Parameters']['AskKeyParameter']['AllowedValues']==['/wellspring/ask/provider_key']
    quota=[s for s in statements if any(a.startswith('dynamodb:') for a in s['Action'])]
    assert len(quota)==1 and quota[0]['Action']==['dynamodb:UpdateItem']
    assert quota[0]['Resource']=={'Fn::GetAtt':['AskQuotaTable','Arn']}
    assert quota[0]['Condition']['ForAllValues:StringLike']['dynamodb:LeadingKeys']==['ASK#*']
    ingest=json.dumps(template['Resources']['IngestRole'])
    assert 'ssm:' not in ingest and 'dynamodb:' not in ingest


def test_quota_is_anonymous_expiring_and_provider_defaults_disabled():
    template=json.loads(Path('infra/template.json').read_text())
    table=template['Resources']['AskQuotaTable']['Properties']
    assert table['BillingMode']=='PAY_PER_REQUEST'
    assert table['TimeToLiveSpecification']=={'AttributeName':'expires_at','Enabled':True}
    assert table['AttributeDefinitions']==[{'AttributeName':'quota_key','AttributeType':'S'}]
    assert template['Parameters']['AskDailyLimit']['Default']==100
    assert template['Parameters']['AskEnabled']['Default']=='false'
    env=template['Resources']['ApiFunction']['Properties']['Environment']['Variables']
    assert env['ASK_KEY_PARAMETER']['Fn::If'][-1]==''
    assert 'DEEPSEEK_API_KEY' not in env
