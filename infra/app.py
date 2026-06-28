#!/usr/bin/env python3
"""Selom AWS infrastructure as code (AWS CDK, Python).

This is the IaC home for Selom's foundational, stateful, security-sensitive AWS
resources. We adopt CDK now — at the AWS-setup stage, with almost nothing
provisioned — because it's the cheapest moment to start (the `cdk import` cost of
adopting click-ops resources only grows). CDKTF is archived and Terraform moved to
BSL, so for an AWS-only Python stack CDK-Python is the right fit.

Stacks land here as the materialization plan reaches them:
  - SelomGithubOidc  (now)       — GitHub Actions OIDC provider + deploy role.
  - SelomData        (step 8)    — S3 (lifecycle/CORS), Aurora Serverless v2 (min=0 ACU).
  - SelomCompute     (step 8)    — light zip Lambda (API) + heavy Fargate task (compute).
  - SelomAsync       (step 8)    — S3-event → EventBridge → Step Functions → Fargate.

Deploy (admin/root creds — the OIDC + IAM bits need iam:*, which the day-to-day
selom-dev PowerUser cannot do):
    cd infra
    python -m venv .venv && . .venv/Scripts/activate   # (Windows: .venv\\Scripts\\activate)
    pip install -r requirements.txt
    npx aws-cdk@2 bootstrap aws://417673081852/ap-southeast-2   # once per account/region
    npx aws-cdk@2 deploy SelomGithubOidc
See infra/README.md and docs/aws-materialization/integrations.md for the full runbook.
"""
import os

import aws_cdk as cdk

from stacks.github_oidc_stack import GithubOidcStack

app = cdk.App()

env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT", "417673081852"),
    region=os.environ.get("CDK_DEFAULT_REGION", "ap-southeast-2"),
)

GithubOidcStack(app, "SelomGithubOidc", env=env)

app.synth()
