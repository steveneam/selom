"""GitHub Actions → AWS via OpenID Connect (no long-lived keys).

This replaces the static `~/.aws/credentials` access key for CI/CD (the day-old
AKIA… key the account inspection flagged as the top security risk) and the stored
PAT pattern from the Medium DevOps guide. GitHub Actions presents a short-lived OIDC
token; AWS STS exchanges it for temporary creds on a role whose trust policy is
scoped to THIS repo only. Nothing is stored on GitHub except the (non-secret) role ARN.

Creating this requires iam:* — run `cdk deploy` with admin/root creds, once.
"""
from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_iam as iam
from constructs import Construct

GITHUB_OWNER = "steveneam"
GITHUB_REPO = "selom"


class GithubOidcStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # GitHub's OIDC identity provider. CDK manages the thumbprint; AWS validates
        # GitHub's token signature against the well-known JWKS at this issuer.
        provider = iam.OpenIdConnectProvider(
            self,
            "GithubOidcProvider",
            url="https://token.actions.githubusercontent.com",
            client_ids=["sts.amazonaws.com"],
        )

        # Trust ONLY this repo, and only the main branch + the `production` GitHub
        # Environment (so a fork or an arbitrary branch can't assume the role).
        # `aud` is pinned to sts.amazonaws.com (the GitHub→AWS audience).
        principal = iam.OpenIdConnectPrincipal(
            provider,
            conditions={
                "StringEquals": {
                    "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                },
                "StringLike": {
                    "token.actions.githubusercontent.com:sub": [
                        f"repo:{GITHUB_OWNER}/{GITHUB_REPO}:ref:refs/heads/main",
                        f"repo:{GITHUB_OWNER}/{GITHUB_REPO}:environment:production",
                    ],
                },
            },
        )

        deploy_role = iam.Role(
            self,
            "GithubDeployRole",
            role_name="selom-github-deploy",
            assumed_by=principal,
            max_session_duration=Duration.hours(1),
            description="Assumed by GitHub Actions (OIDC) to deploy Selom via CDK.",
        )

        # Least-privilege: the deploy job's only job is to run `cdk deploy`, which
        # itself assumes CDK's bootstrap roles (cdk-<qualifier>-deploy-role,
        # -file-publishing-role, -image-publishing-role). So the GitHub role needs
        # exactly one thing — permission to assume those CDK roles. This is the
        # recommended OIDC+CDK pattern; it avoids granting broad ECR/Lambda/S3/CFN
        # rights directly to the CI principal. Expand ONLY if a step-8 job deploys
        # outside CDK (e.g. a raw `aws lambda update-function-code` fast path).
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                sid="AssumeCdkDeploymentRoles",
                actions=["sts:AssumeRole"],
                resources=[f"arn:aws:iam::{self.account}:role/cdk-*"],
            )
        )

        CfnOutput(
            self,
            "DeployRoleArn",
            value=deploy_role.role_arn,
            description="Set this as the GitHub repo variable AWS_DEPLOY_ROLE_ARN.",
        )
        CfnOutput(
            self,
            "OidcProviderArn",
            value=provider.open_id_connect_provider_arn,
        )
