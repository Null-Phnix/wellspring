"""Repeatable two-phase CloudFormation deployment; no credentials enter artifacts."""
import argparse,base64,hashlib,json,subprocess,zipfile
from pathlib import Path
from aws_task import aws_env

STACK='wellspring-demo'
REGION='ca-central-1'
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/deployment'


def aws(*args,capture=False):
    r=subprocess.run(['aws',*args,'--region',REGION],env=aws_env(),check=True,capture_output=capture,text=capture)
    return json.loads(r.stdout) if capture else None


def state():
    s=aws('cloudformation','describe-stacks','--stack-name',STACK,capture=True)['Stacks'][0]
    return s,{o['OutputKey']:o['OutputValue'] for o in s.get('Outputs',[])}


def require_publish_ready(stack):
    if stack['StackStatus'] not in ('CREATE_COMPLETE','UPDATE_COMPLETE'):
        raise ValueError('Wait for a completed stack before publishing.')
    params={p['ParameterKey']:p['ParameterValue'] for p in stack.get('Parameters',[])}
    if params.get('ScheduleState')!='DISABLED':
        raise ValueError('Disable the daily schedule and wait for UPDATE_COMPLETE before publishing data.')


def require_coverage_preserved(current, proposed):
    def loaded(m):return {d['date'] for d in m.get('dates',[]) if d['status'] in ('loaded','empty')}
    if not loaded(current).issubset(loaded(proposed)):
        raise ValueError('Proposed snapshot would discard an already loaded source date.')


def current_manifest(bucket):
    target=OUT/'previous-manifest.json'
    try:
        result=aws('s3api','get-object','--bucket',bucket,'--key','published/manifest.json',str(target),capture=True)
    except subprocess.CalledProcessError as exc:
        if '(NoSuchKey)' in (exc.stderr or '') or '(404)' in (exc.stderr or ''):
            return None,None
        raise
    return json.loads(target.read_text()),result['ETag']


def verify_deployment(stack, outputs, receipt):
    if stack['StackStatus']!='UPDATE_COMPLETE':
        raise ValueError('Application update has not completed.')
    params={p['ParameterKey']:p['ParameterValue'] for p in stack.get('Parameters',[])}
    if params.get('CodeKey')!=receipt['code_key']:
        raise ValueError('Stack does not point to the candidate code key.')
    expected_ask = receipt.get('ask_enabled', False)
    if (params.get('AskEnabled', 'false') == 'true') != expected_ask:
        raise ValueError('Stack AskEnabled does not match the deployment receipt.')
    if expected_ask:
        for param, field in [('AskModel','ask_model'), ('AskProviderUrl','provider_url'),
                             ('AskKeyParameter','key_parameter'), ('AskDailyLimit','daily_limit')]:
            if str(params.get(param)) != str(receipt.get(field)):
                raise ValueError('Stack Ask configuration does not match the deployment receipt.')
    expected=base64.b64encode(bytes.fromhex(receipt['code_sha256'])).decode()
    functions={}
    for key in ('ApiFunction','IngestFunction'):
        config=aws('lambda','get-function-configuration','--function-name',outputs[key],capture=True)
        if config['CodeSha256']!=expected or config.get('LastUpdateStatus')!='Successful':
            raise ValueError('Lambda code hash or update state does not match candidate.')
        if key == 'ApiFunction' and 'AskEnabled' in params:
            env = config.get('Environment', {}).get('Variables', {})
            expected_env = {'ASK_KEY_PARAMETER': params.get('AskKeyParameter') if expected_ask else '',
                        'ASK_MODEL': params.get('AskModel'), 'ASK_PROVIDER_URL': params.get('AskProviderUrl'),
                        'ASK_DAILY_LIMIT': str(params.get('AskDailyLimit')),
                        'ASK_QUOTA_TABLE': outputs.get('AskQuotaTable')}
            if any(env.get(name) != value for name, value in expected_env.items()):
                raise ValueError('Lambda Ask environment does not match the stack parameters.')
        functions[key]={'code_sha256_base64':config['CodeSha256'],'revision_id':config['RevisionId']}
    return {**receipt,'status':'verified_deployed','outputs':outputs,'functions':functions}


def update_parameters(stack, overrides):
    names = {p['ParameterKey'] for p in stack.get('Parameters', [])} | set(overrides)
    return [f'ParameterKey={name},ParameterValue={overrides[name]}' if name in overrides
            else f'ParameterKey={name},UsePreviousValue=true' for name in sorted(names)]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['bootstrap','status','publish','verify','enable-schedule','disable-schedule'])
    parser.add_argument('--data',type=Path,default=ROOT/'output/published')
    parser.add_argument('--enable-ask',action='store_true',help='Enable approved provider only after SSM metadata preflight')
    args=parser.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    if args.action=='bootstrap':
        aws('cloudformation','create-stack','--stack-name',STACK,'--template-body','file://'+str(ROOT/'infra/template.json'),'--capabilities','CAPABILITY_IAM','--parameters','ParameterKey=ScheduleState,ParameterValue=DISABLED')
        return
    s,o=state()
    if args.action=='status':
        print(json.dumps({'status':s['StackStatus'],'outputs':o},indent=2));return
    if args.action=='verify':
        receipt=json.loads((OUT/'publish-receipt.json').read_text())
        verified=verify_deployment(s,o,receipt)
        (OUT/'verified-deployment.json').write_text(json.dumps(verified,indent=2)+'\n')
        print(json.dumps({'status':verified['status'],'code_sha256':verified['code_sha256'],'source_commit':verified['source_commit']}));return
    if args.action in ('enable-schedule','disable-schedule'):
        if s['StackStatus'] not in ('CREATE_COMPLETE','UPDATE_COMPLETE'):raise SystemExit('Stack update still in progress.')
        code=next(p['ParameterValue'] for p in s['Parameters'] if p['ParameterKey']=='CodeKey')
        if not code:raise SystemExit('No application code has been deployed.')
        state_value='ENABLED' if args.action=='enable-schedule' else 'DISABLED'
        aws('cloudformation','update-stack','--stack-name',STACK,'--template-body','file://'+str(ROOT/'infra/template.json'),'--capabilities','CAPABILITY_IAM','--parameters',*update_parameters(s,{'ScheduleState':state_value}))
        return
    require_publish_ready(s)
    previous_parameters={p['ParameterKey']:p['ParameterValue'] for p in s.get('Parameters',[])}
    enable_ask=args.enable_ask or previous_parameters.get('AskEnabled')=='true'
    if enable_ask:
        key_metadata=aws('ssm','get-parameter','--name','/wellspring/ask/provider_key',
                         '--query','Parameter.{Name:Name,Type:Type,Version:Version}',capture=True)
        if key_metadata.get('Type')!='SecureString':
            raise SystemExit('A configured SecureString is required before enabling Ask.')
    # Public code must be traceable to a committed source tree.
    if subprocess.check_output(['git','status','--porcelain','--','wellspring'],cwd=ROOT).strip():
        raise SystemExit('Commit runtime source before packaging it for publication.')
    source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    manifest=json.loads((args.data/'manifest.json').read_text())
    path=args.data/manifest['export_file']
    if path.parent.resolve()!=args.data.resolve() or hashlib.sha256(path.read_bytes()).hexdigest()!=manifest['export_sha256']:
        raise SystemExit('Refusing invalid export path or hash.')
    previous,etag=current_manifest(o['DataBucket'])
    if previous is not None:require_coverage_preserved(previous,manifest)
    bundle=OUT/'lambda.zip'
    with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted((ROOT/'wellspring').rglob('*')):
            if p.is_file() and p.suffix in ('.py','.json'):z.write(p,p.relative_to(ROOT))
        z.writestr('build-receipt.json',json.dumps({'source_commit':source_commit}))
    digest=hashlib.sha256(bundle.read_bytes()).hexdigest();key=f'artifacts/lambda-{digest}.zip'
    aws('s3','cp',str(bundle),f"s3://{o['DataBucket']}/{key}",'--only-show-errors')
    aws('s3','cp',str(path),f"s3://{o['DataBucket']}/published/{path.name}",'--content-type','application/x-ndjson','--only-show-errors')
    conditional=['--if-match',etag] if etag else ['--if-none-match','*']
    aws('s3api','put-object','--bucket',o['DataBucket'],'--key','published/manifest.json','--body',str(args.data/'manifest.json'),'--content-type','application/json',*conditional)
    aws('s3','sync',str(ROOT/'output/source-data/raw'),f"s3://{o['DataBucket']}/raw/bootstrap/",'--only-show-errors')
    aws('cloudformation','update-stack','--stack-name',STACK,'--template-body','file://'+str(ROOT/'infra/template.json'),'--capabilities','CAPABILITY_IAM','--parameters',*update_parameters(s,{'CodeKey':key,'ScheduleState':'DISABLED','AskEnabled':'true' if enable_ask else 'false'}))
    (OUT/'publish-receipt.json').write_text(json.dumps({'status':'update_requested','stack':STACK,'ask_enabled':enable_ask,'ask_model':previous_parameters.get('AskModel','deepseek-chat'),'provider_url':previous_parameters.get('AskProviderUrl','https://api.deepseek.com'),'key_parameter':previous_parameters.get('AskKeyParameter','/wellspring/ask/provider_key'),'daily_limit':previous_parameters.get('AskDailyLimit','100'),'source_commit':source_commit,'code_key':key,'code_sha256':digest,'export_sha256':manifest['export_sha256']},indent=2)+'\n')
    print('Update requested; run verify after UPDATE_COMPLETE to prove deployed code.')

if __name__=='__main__':main()
