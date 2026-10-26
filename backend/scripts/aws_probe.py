"""Which AWS services can our role use in ap-south-1? Read-only checks, no resources are created.
Run after `aws sso login --profile FAI-TCE-Builder-AI-402365884845`:   python backend/scripts/aws_probe.py
"""
import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config  # noqa: E402

PROFILE = os.getenv("AWS_PROFILE", config.AWS_PROFILE)
REGION = os.getenv("AWS_REGION", config.AWS_REGION)
s = boto3.Session(profile_name=PROFILE, region_name=REGION)


def check(name, fn):
    try:
        out = fn()
        print(f"  OK       {name}  {out or ''}")
    except ClientError as e:
        code = e.response["Error"]["Code"]
        print(f"  {'DENIED ' if 'Denied' in code or 'Unauthorized' in code else 'ERROR  '}  {name}  {code}")
    except (BotoCoreError, Exception) as e:  # noqa: BLE001
        print(f"  ERROR    {name}  {type(e).__name__}: {str(e)[:90]}")


print(f"profile={PROFILE} region={REGION}")
check("sts get-caller-identity", lambda: s.client("sts").get_caller_identity()["Arn"].split("/")[-2:])
check("bedrock-runtime invoke Nova Micro", lambda: s.client("bedrock-runtime").converse(
    modelId=config.MODEL_NOVA_MICRO, messages=[{"role": "user", "content": [{"text": "hi"}]}], inferenceConfig={"maxTokens": 5})["usage"]["totalTokens"])
check("bedrock-runtime invoke Ministral 3B", lambda: s.client("bedrock-runtime").converse(
    modelId=config.MODEL_MINISTRAL_3B, messages=[{"role": "user", "content": [{"text": "hi"}]}], inferenceConfig={"maxTokens": 5})["usage"]["totalTokens"])
check("s3 list buckets", lambda: len(s.client("s3").list_buckets()["Buckets"]))
check("dynamodb list tables", lambda: s.client("dynamodb").list_tables()["TableNames"])
check("lambda list functions", lambda: len(s.client("lambda").list_functions()["Functions"]))
check("apigateway get rest apis", lambda: len(s.client("apigateway").get_rest_apis()["items"]))
# Textract: a 1x1 image is allowed-but-empty if we have access, AccessDenied if not
PNG1 = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360000002000001e221bc330000000049454e44ae426082")
check("textract detect_document_text", lambda: len(s.client("textract").detect_document_text(Document={"Bytes": PNG1})["Blocks"]))
check("transcribe list jobs", lambda: len(s.client("transcribe").list_transcription_jobs(MaxResults=1)["TranscriptionJobSummaries"]))
check("cognito-idp list user pools", lambda: len(s.client("cognito-idp").list_user_pools(MaxResults=1)["UserPools"]))
check("polly describe voices (Tamil)", lambda: len(s.client("polly").describe_voices(LanguageCode="ta-IN")["Voices"]))
check("translate (Tamil)", lambda: s.client("translate").translate_text(Text="hello", SourceLanguageCode="en", TargetLanguageCode="ta")["TranslatedText"][:10])
