# AWS staging checklist (nothing here has been deployed; run each step only with the owner's approval)

## 1. Code readiness (done, tested: `tests/test_aws_session.py`)
- Every boto3 client (Bedrock, Textract, Transcribe) now uses `aws_resources.session()`: the named SSO profile when it exists on the machine, otherwise the default credential chain (the task/instance/Lambda role).
- Region comes from `AWS_REGION` (default ap-south-1). CORS: set `CROPSY_CORS_ORIGINS=https://<staging-frontend>` (comma-separated); localhost origins stay.

## 2. Environment variables
| Variable | Staging value |
|---|---|
| AWS_REGION | ap-south-1 |
| AWS_PROFILE | leave unset (role is used) |
| CROPSY_CORS_ORIGINS | staging frontend https origin |
| CROPSY_STORE / CROPSY_BUCKET | S3 bucket for parcel/store data if not local (confirm which the code reads) |
| CROPSY_OFFICER_KEY | set from Secrets Manager, never in the repo |
| CROPSY_EXTERNAL_IMAGES | off unless Wikimedia egress is allowed |
| CROPSY_DOC_MAX_PAGES / _MB, CROPSY_VOICE_SECONDS / _MAX | keep defaults; confirm against gateway limits |

## 3. IAM (least privilege for the service role)
- `bedrock:InvokeModel` (and `InvokeModelWithResponseStream`) on: apac.amazon.nova-micro-v1:0, apac.amazon.nova-lite-v1:0, mistral.ministral-3-3b/8b-instruct, amazon.titan-embed-text-v2:0, amazon.titan-embed-image-v1 (inference-profile ARNs too).
- `textract:DetectDocumentText` (and `AnalyzeDocument` if used), `transcribe:StartStreamTranscription`.
- `s3:GetObject/PutObject/ListBucket` on the one bucket only. CloudWatch Logs write.
- Confirm model access is enabled in the Bedrock console for ap-south-1 for all five models.

## 4. Runtime limits to verify
- Request timeout end to end: a COMPLEX answer + verify + retry can exceed 30 s. Load balancer / API Gateway idle timeout >= 60 s (API Gateway's 29 s hard limit is too short for the text route; use ALB/App Runner/ECS). `/api/media` is a separate call so the text arrives first.
- WebSocket path for voice must be allowed through the load balancer.
- Memory: the knowledge index and embeddings load at start-up; check container RAM, cold-start time, and that `knowledge/` and `data/` ship in the image.
- Logs: confirm no farmer text, uploaded documents or credentials are logged.

## 5. Staging tests (after deployment)
Text (English/Tamil/Tanglish), photo, PDF, calculator (TM-31 fertilizer), retrieval, gold set (`tests/run_gold_live.py`), universal live set, voice via the real browser on HTTPS, CORS from the staging origin, role without SSO profile.

Production decision: HOLD until the agronomist and Tamil reviews are signed off.
