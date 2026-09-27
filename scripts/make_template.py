"""Generate the one plain CloudFormation template; no SAM CLI required."""
import json
from pathlib import Path

ref=lambda x:{'Ref':x}
att=lambda x,y:{'Fn::GetAtt':[x,y]}
sub=lambda s:{'Fn::Sub':s}
policy=lambda statements:{'Version':'2012-10-17','Statement':statements}
trust=lambda service:policy([{'Effect':'Allow','Principal':{'Service':service},'Action':'sts:AssumeRole'}])
r={}
for name in ('DataBucket','SiteBucket'):
    r[name]={'Type':'AWS::S3::Bucket','DeletionPolicy':'Retain','UpdateReplacePolicy':'Retain','Properties':{'PublicAccessBlockConfiguration':{'BlockPublicAcls':True,'BlockPublicPolicy':True,'IgnorePublicAcls':True,'RestrictPublicBuckets':True},'BucketEncryption':{'ServerSideEncryptionConfiguration':[{'ServerSideEncryptionByDefault':{'SSEAlgorithm':'AES256'}}]},'VersioningConfiguration':{'Status':'Enabled'}}}
r['OriginAccess']={'Type':'AWS::CloudFront::OriginAccessControl','Properties':{'OriginAccessControlConfig':{'Name':sub('${AWS::StackName}-site'),'OriginAccessControlOriginType':'s3','SigningBehavior':'always','SigningProtocol':'sigv4'}}}
r['Distribution']={'Type':'AWS::CloudFront::Distribution','Properties':{'DistributionConfig':{'Enabled':True,'DefaultRootObject':'index.html','PriceClass':'PriceClass_100','Origins':[{'Id':'site','DomainName':att('SiteBucket','RegionalDomainName'),'OriginAccessControlId':ref('OriginAccess'),'S3OriginConfig':{'OriginAccessIdentity':''}}],'DefaultCacheBehavior':{'TargetOriginId':'site','ViewerProtocolPolicy':'redirect-to-https','AllowedMethods':['GET','HEAD','OPTIONS'],'CachedMethods':['GET','HEAD'],'Compress':True,'ForwardedValues':{'QueryString':False,'Cookies':{'Forward':'none'}},'DefaultTTL':300,'MaxTTL':3600,'MinTTL':0},'CustomErrorResponses':[{'ErrorCode':code,'ResponseCode':200,'ResponsePagePath':'/index.html','ErrorCachingMinTTL':0} for code in (403,404)],'ViewerCertificate':{'CloudFrontDefaultCertificate':True}}}}
r['SitePolicy']={'Type':'AWS::S3::BucketPolicy','Properties':{'Bucket':ref('SiteBucket'),'PolicyDocument':policy([{'Effect':'Allow','Principal':{'Service':'cloudfront.amazonaws.com'},'Action':'s3:GetObject','Resource':sub('${SiteBucket.Arn}/*'),'Condition':{'StringEquals':{'AWS:SourceArn':sub('arn:${AWS::Partition}:cloudfront::${AWS::AccountId}:distribution/${Distribution}')}}}])}}
for prefix in ('Api','Ingest'):
    actions=['s3:GetObject'] if prefix=='Api' else ['s3:GetObject','s3:PutObject']
    resources=[sub('${DataBucket.Arn}/published/*')] if prefix=='Api' else [sub('${DataBucket.Arn}/published/*'),sub('${DataBucket.Arn}/raw/*'),sub('${DataBucket.Arn}/history/*')]
    r[prefix+'Role']={'Type':'AWS::IAM::Role','Properties':{'AssumeRolePolicyDocument':trust('lambda.amazonaws.com'),'Policies':[{'PolicyName':'project-data-and-logs','PolicyDocument':policy([{'Effect':'Allow','Action':actions,'Resource':resources},{'Effect':'Allow','Action':['logs:CreateLogStream','logs:PutLogEvents'],'Resource':sub('arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:/aws/lambda/${AWS::StackName}-'+prefix.lower()+':*')}])}]}}
    r[prefix+'Logs']={'Type':'AWS::Logs::LogGroup','Properties':{'LogGroupName':sub('/aws/lambda/${AWS::StackName}-'+prefix.lower()),'RetentionInDays':7}}
    r[prefix+'Function']={'Type':'AWS::Lambda::Function','DependsOn':prefix+'Logs','Properties':{'FunctionName':sub('${AWS::StackName}-'+prefix.lower()),'Runtime':'python3.13','Architectures':['arm64'],'Role':att(prefix+'Role','Arn'),'MemorySize':256 if prefix=='Api' else 512,'Timeout':15 if prefix=='Api' else 180,'Handler':{'Fn::If':['HasCode','wellspring.api.handler.lambda_handler' if prefix=='Api' else 'wellspring.ingest.cloud.lambda_handler','index.handler']},'Code':{'Fn::If':['HasCode',{'S3Bucket':ref('DataBucket'),'S3Key':ref('CodeKey')},{'ZipFile':'def handler(event, context):\n    return {"statusCode":503,"body":"Dataset is being prepared"}\n'}]},'Environment':{'Variables':{'DATA_BUCKET':ref('DataBucket'),'MANIFEST_KEY':'published/manifest.json','ALLOWED_ORIGINS':sub('https://${Distribution.DomainName},http://localhost:4200')}}}}
r['HttpApi']={'Type':'AWS::ApiGatewayV2::Api','Properties':{'Name':sub('${AWS::StackName}-api'),'ProtocolType':'HTTP'}}
r['ApiIntegration']={'Type':'AWS::ApiGatewayV2::Integration','Properties':{'ApiId':ref('HttpApi'),'IntegrationType':'AWS_PROXY','IntegrationUri':att('ApiFunction','Arn'),'PayloadFormatVersion':'2.0','TimeoutInMillis':16000}}
r['ApiRoute']={'Type':'AWS::ApiGatewayV2::Route','Properties':{'ApiId':ref('HttpApi'),'RouteKey':'$default','Target':{'Fn::Join':['',['integrations/',ref('ApiIntegration')]]}}}
r['ApiStage']={'Type':'AWS::ApiGatewayV2::Stage','Properties':{'ApiId':ref('HttpApi'),'StageName':'$default','AutoDeploy':True,'DefaultRouteSettings':{'ThrottlingBurstLimit':5,'ThrottlingRateLimit':2}}}
r['ApiInvoke']={'Type':'AWS::Lambda::Permission','Properties':{'FunctionName':ref('ApiFunction'),'Action':'lambda:InvokeFunction','Principal':'apigateway.amazonaws.com','SourceArn':sub('arn:${AWS::Partition}:execute-api:${AWS::Region}:${AWS::AccountId}:${HttpApi}/*')}}
r['ScheduleRole']={'Type':'AWS::IAM::Role','Properties':{'AssumeRolePolicyDocument':trust('scheduler.amazonaws.com'),'Policies':[{'PolicyName':'invoke-ingestion','PolicyDocument':policy([{'Effect':'Allow','Action':'lambda:InvokeFunction','Resource':att('IngestFunction','Arn')}])}]}}
r['DailySchedule']={'Type':'AWS::Scheduler::Schedule','Properties':{'Description':'Public AER ST1 intake at 07:00 Mountain including daylight saving time','State':ref('ScheduleState'),'ScheduleExpression':'cron(0 7 * * ? *)','ScheduleExpressionTimezone':'America/Edmonton','FlexibleTimeWindow':{'Mode':'OFF'},'Target':{'Arn':att('IngestFunction','Arn'),'RoleArn':att('ScheduleRole','Arn'),'Input':'{}','RetryPolicy':{'MaximumRetryAttempts':1,'MaximumEventAgeInSeconds':3600}}}}
t={'AWSTemplateFormatVersion':'2010-09-09','Description':'Wellspring public demo: private source buckets, scoped read-only API, static frontend and daily ST1 intake.','Parameters':{'CodeKey':{'Type':'String','Default':''},'ScheduleState':{'Type':'String','Default':'DISABLED','AllowedValues':['ENABLED','DISABLED']}},'Conditions':{'HasCode':{'Fn::Not':[{'Fn::Equals':[ref('CodeKey'),'']}]}},'Resources':r,'Outputs':{'DataBucket':{'Value':ref('DataBucket')},'SiteBucket':{'Value':ref('SiteBucket')},'ApiUrl':{'Value':att('HttpApi','ApiEndpoint')},'CloudFrontDomain':{'Value':att('Distribution','DomainName')},'ApiFunction':{'Value':ref('ApiFunction')},'IngestFunction':{'Value':ref('IngestFunction')}}}
# M4: encrypted provider reference and one anonymous daily quota row.
t['Parameters'].update({
    'AskEnabled': {'Type':'String','Default':'false','AllowedValues':['true','false']},
    'AskProviderUrl': {'Type':'String','Default':'https://api.deepseek.com','AllowedValues':['https://api.deepseek.com']},
    'AskModel': {'Type':'String','Default':'deepseek-chat','AllowedValues':['deepseek-chat']},
    'AskKeyParameter': {'Type':'String','Default':'/wellspring/ask/provider_key','AllowedValues':['/wellspring/ask/provider_key']},
    'AskDailyLimit': {'Type':'Number','Default':100,'MinValue':1,'MaxValue':1000},
})
t['Conditions']['AskEnabledCondition']={'Fn::Equals':[ref('AskEnabled'),'true']}
r['AskQuotaTable']={
    'Type':'AWS::DynamoDB::Table','DeletionPolicy':'Retain','UpdateReplacePolicy':'Retain',
    'Properties':{'BillingMode':'PAY_PER_REQUEST',
        'AttributeDefinitions':[{'AttributeName':'quota_key','AttributeType':'S'}],
        'KeySchema':[{'AttributeName':'quota_key','KeyType':'HASH'}],
        'TimeToLiveSpecification':{'AttributeName':'expires_at','Enabled':True},
        'SSESpecification':{'SSEEnabled':True}}}
r['ApiRole']['Properties']['Policies'].append({
    'PolicyName':'ask-secret-and-quota',
    'PolicyDocument':policy([
        {'Effect':'Allow','Action':['ssm:GetParameter'],
         'Resource':sub('arn:${AWS::Partition}:ssm:${AWS::Region}:${AWS::AccountId}:parameter${AskKeyParameter}')},
        {'Effect':'Allow','Action':['dynamodb:UpdateItem'],'Resource':att('AskQuotaTable','Arn'),
         'Condition':{'ForAllValues:StringLike':{'dynamodb:LeadingKeys':['ASK#*']}}},
    ])})
r['ApiFunction']['Properties']['Environment']['Variables'].update({
    'ASK_KEY_PARAMETER':{'Fn::If':['AskEnabledCondition',ref('AskKeyParameter'),'']},
    'ASK_QUOTA_TABLE':ref('AskQuotaTable'),
    'ASK_PROVIDER_URL':ref('AskProviderUrl'),'ASK_MODEL':ref('AskModel'),
    'ASK_DAILY_LIMIT':{'Fn::Sub':'${AskDailyLimit}'},
})
# A full January-to-current snapshot peaked at 251 MB during a warm refresh
# in the 256 MB API allocation. Keep headroom for the old and new snapshots.
r['ApiFunction']['Properties']['MemorySize']=512
t['Outputs']['AskQuotaTable']={'Value':ref('AskQuotaTable')}
t['Outputs']['AskEnabled']={'Value':ref('AskEnabled')}
t['Outputs']['AskModel']={'Value':ref('AskModel')}

Path('infra/template.json').write_text(json.dumps(t,indent=2)+'\n')
