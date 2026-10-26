"""Deployment readiness: no AWS call may depend on a named SSO profile existing (a deployed service uses its own role)."""
import re
from pathlib import Path

import boto3

from app import aws_resources


def test_session_falls_back_to_the_default_credential_chain_when_the_profile_is_missing(monkeypatch):
    calls = []
    real = boto3.Session

    def fake(*a, **k):
        calls.append(k)
        if k.get("profile_name"):
            raise boto3.session.botocore.exceptions.ProfileNotFound(profile="nope")
        return real(*a, **k)
    monkeypatch.setattr(boto3, "Session", fake)
    monkeypatch.setattr(aws_resources, "_session", None)
    s = aws_resources.session()
    assert s is not None and any(not c.get("profile_name") for c in calls)


def test_no_module_hardcodes_a_profile_or_region_outside_config():
    for f in Path("app").rglob("*.py"):
        src = f.read_text(encoding="utf-8")
        assert not re.search(r"Session\(profile_name=config\.AWS_PROFILE", src) or f.name in ("bedrock.py", "aws_resources.py"), f
        assert 'region_name="ap-south-1"' not in src, f
