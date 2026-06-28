# Selom infrastructure (AWS CDK, Python)

IaC home for Selom's foundational AWS resources. See
`docs/aws-materialization/integrations.md` for the full GitHub↔AWS↔Vercel design;
this README is the operational runbook.

## Why CDK, why now

We're at the AWS-setup stage with almost nothing provisioned — the cheapest moment to
adopt IaC (the `cdk import` cost of adopting click-ops resources only grows). CDK-Python
fits an AWS-only Python stack; CDKTF is archived and Terraform moved to BSL.

## Stacks

| Stack | When | Contents |
|---|---|---|
| `SelomGithubOidc` | **now** | GitHub Actions OIDC provider + `selom-github-deploy` role (no stored keys) |
| `SelomData` | step 8 | S3 (lifecycle/CORS), Aurora Serverless v2 **min=0 ACU** |
| `SelomCompute` | step 8 | light zip Lambda (API) + heavy **Fargate** task (compute) |
| `SelomAsync` | step 8 | S3-event → EventBridge → Step Functions → Fargate |

## Prerequisites

- Node.js (for the `cdk` CLI — invoked via `npx aws-cdk@2`, no global install needed).
- Python 3.12 + the deps in `requirements.txt`.
- **Admin/root AWS credentials** for the first deploy. The day-to-day `selom-dev` user is
  PowerUserAccess, which excludes `iam:*` — it CANNOT create the OIDC provider or roles.
  Use a temporary admin profile (or root with MFA) for `bootstrap` + the `SelomGithubOidc`
  deploy only.

## One-time setup (admin creds)

```bash
cd infra
python -m venv .venv
. .venv/Scripts/activate          # Windows; macOS/Linux: . .venv/bin/activate
pip install -r requirements.txt

# Bootstrap the account/region for CDK (creates the cdk-* deploy roles + asset bucket).
npx aws-cdk@2 bootstrap aws://417673081852/ap-southeast-2

# Deploy the GitHub OIDC provider + deploy role.
npx aws-cdk@2 deploy SelomGithubOidc
```

The deploy prints `DeployRoleArn`. Set it as a **GitHub repository variable** (not a
secret — the ARN is not sensitive):

- GitHub → repo Settings → Secrets and variables → Actions → Variables →
  `AWS_DEPLOY_ROLE_ARN = arn:aws:iam::417673081852:role/selom-github-deploy`

A deploy workflow (added at step 8) then assumes it via
`aws-actions/configure-aws-credentials@v4` with `role-to-assume: ${{ vars.AWS_DEPLOY_ROLE_ARN }}`
and `permissions: id-token: write` — no access keys anywhere.

## After OIDC works

Deactivate and delete the static `selom-dev` access key once CI/CD runs via OIDC and
local dev moves to IAM Identity Center (`aws configure sso`). A leaked long-lived key is
the most common solo-dev breach; OIDC removes the class of risk.

## Useful

```bash
npx aws-cdk@2 ls                 # list stacks
npx aws-cdk@2 diff SelomGithubOidc
npx aws-cdk@2 synth SelomGithubOidc   # emit CloudFormation without deploying
```
