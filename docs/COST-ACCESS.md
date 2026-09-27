# Cost and access evidence

Observed September 27, 2026 from the deployed ca-central-1 stack. This record is a snapshot; M4 inference has not been enabled.

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
reduces bursts but is not a monthly spending cap. Josii owns the $5 budget alarm.

Sources:
- https://aws.amazon.com/lambda/pricing/ (1M requests and 400,000 GB-s allowance)
- https://aws.amazon.com/api-gateway/pricing/ (HTTP API example US$1/million)
- https://aws.amazon.com/eventbridge/pricing/ (14M Scheduler invocations allowance)
- https://aws.amazon.com/cloudfront/faqs/ (pay-as-you-go 1 TB/10M request allowance)
- https://aws.amazon.com/s3/pricing/ and AWS Price List API receipt s3-price.json
- https://aws.amazon.com/cloudwatch/pricing/ (log pricing and allowances)

## Verified access boundaries

Both S3 buckets have all four PublicAccessBlock flags enabled. ACLs grant only
the owning canonical account FULL_CONTROL. CloudFront's service principal has
GetObject for the site bucket only when AWS:SourceArn matches distribution
E2OWOTRIGM4VB1; it receives no write action.

The API Lambda role has only GetObject on data/published/* for S3. The ingestion
role intentionally has GetObject and PutObject on published/*, raw/* and history/*.
The deployment identity manages the stack and uploads artifacts/site data.
Both functions can write their own CloudWatch streams. Therefore “the deploy
user is the only writer” would be false. Account administrators may also have
IAM authority; this scoped stack audit does not claim an exhaustive account audit.

There is no unexpected public bucket or public ingestion endpoint to repair.
The public API intentionally exposes public AER data. M4's additional secret
read and quota-counter write scopes remain proposed, not deployed.

Local receipts: output/deployment/morning-access-audit.json, morning-usage.json,
s3-price.json, cloudfront-morning.json and scheduled-ingest-morning.json.
