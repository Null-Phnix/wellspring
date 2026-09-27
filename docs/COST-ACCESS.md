# Cost and access evidence

Observed September 27, 2026 from the deployed ca-central-1 stack. M4 inference
is enabled. The access readback below was collected at 16:44 UTC; traffic and
storage figures retain their separate morning observation window.

## Current resources

API Lambda: 256 MiB, 15 second timeout,Python3.13. Ingestion: 512 MiB, 180 seconds.
The first scheduled invocation used 127 MiB maximum and 2798 ms execution time.
CloudWatch's midnight-to-13:12 UTC window records 58 API calls and 3 ingest calls
(two manual verification calls plus the scheduled call). These are development
traffic, not a reliable prediction of public visitor demand.

Data bucket: 169 retained object versions, 31,903,895 bytes total at observation.
The current official AWS Price List API quotes S3 Standard in ca-central-1 at
US$0.025/GB-month for the first 50 TB. Holding those bytes for a full month is
roughly US$0.0008 before request charges. Versioning means storage grows unless
an explicitly chosen retention policy removes old versions; no history was purged.

For a conservative small-demo example of 100 API calls/day, 30 scheduled ingests
and less than 1 GB retained data: compute, scheduler and static distribution usage
are well below their published free allowances if those allowances remain
available to this account. HTTP API calls at the published US$1/million reference
rate are US$0.003 for 3,000 calls without credits. At this observed scale, hosting
is expected below US$1/month, excluding inference, taxes, other account workloads
and traffic growth. This is an estimate, not an invoice or a spending ceiling.
No VPC/NAT or dedicated compute is provisioned. The 2 requests/second API throttle
reduces bursts but is not a monthly spending cap. The $5 budget alarm remains
owner-managed; this release does not claim that its creation was verified.

Ask's configured alias is `deepseek-chat`; the live provider reports the served
model as `deepseek-flash`. DeepSeek's published Flash rates observed September 27
are US$0.15/US$0.30 per million uncached input tokens and US$0.60/US$1.20 per
million output tokens (off-peak/peak). For an illustrative 1,000 input tokens and
the configured maximum 512 output tokens per attempt, 3,000 attempts per month
would cost about US$1.37 off-peak or US$2.74 peak. Actual token counts and prices
vary. This is a scenario, not a measured bill or hard currency cap.

The demo atomically allocates at most 100 attempts per UTC day before a model
call. Failed calls still consume an attempt. DynamoDB on-demand writes, SSM
reads and logs add usage; SSM is cached for up to five minutes. The quota limits
request count, not all AWS usage, and other callers can exhaust the shared
allowance. No account-wide cost ceiling is claimed.

Sources:
- https://aws.amazon.com/lambda/pricing/ (1M requests and 400,000 GB-s allowance)
- https://aws.amazon.com/api-gateway/pricing/ (HTTP API example US$1/million)
- https://aws.amazon.com/eventbridge/pricing/ (14M Scheduler invocations allowance)
- https://aws.amazon.com/cloudfront/faqs/ (pay-as-you-go 1 TB/10M request allowance)
- https://aws.amazon.com/s3/pricing/ and AWS Price List API receipt s3-price.json
- https://aws.amazon.com/cloudwatch/pricing/ (log pricing and allowances)
- https://api-docs.deepseek.com/quick_start/pricing/ (Flash token rates)

## Verified access boundaries

Both S3 buckets have all four PublicAccessBlock flags enabled. ACLs grant only
the owning canonical account FULL_CONTROL. CloudFront's service principal has
GetObject for the site bucket only when AWS:SourceArn matches distribution
E2OWOTRIGM4VB1; it receives no write action.

The API Lambda role has only GetObject on data/published/* for S3. It also has
`ssm:GetParameter` on exactly `/wellspring/ask/provider_key` and
`dynamodb:UpdateItem` on its quota table with an `ASK#*` leading-key condition.
The parameter is SecureString version 1. The key itself is absent from Lambda
environment values, source and bundles. The API role is the only application
role granted the secret read; this does not exclude deployment or account
administrators with broader authority. The ingestion
role intentionally has GetObject and PutObject on published/*, raw/* and history/*.
The deployment identity manages the stack and uploads artifacts/site data.
Both function roles have no attached managed policies and can write their own
CloudWatch streams. The observed deployment identity is `wellspring-deploy`.
Therefore “the deploy
user is the only writer” would be false. Account administrators may also have
IAM authority; this scoped stack audit does not claim an exhaustive account audit.

There is no unexpected public bucket or public ingestion endpoint to repair.
The public API intentionally exposes public AER data. Neither ingestion nor
CloudFront receives secret-read or quota-table permissions.

Local receipts: output/deployment/morning-access-audit.json, morning-usage.json,
s3-price.json, cloudfront-morning.json, scheduled-ingest-morning.json,
m4-access-audit.json and m4-schedule-counter.json.
