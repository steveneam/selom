# Selom — GitHub ↔ AWS ↔ Vercel integration backbone

> **What this is.** The DevOps/runtime wiring between the three platforms Selom runs on:
> GitHub (source + CI/CD), AWS (backend + data), Vercel (frontend). Distinct from
> `docs/records/external-integrations.md` (bioinformatics tool integrations — OmicVerse etc.). Companion to
> the materialization `plan.md`/`spec.md`; the IaC lives in `infra/` (CDK Python).
>
> _Filed 2026-06-28 22:xx +10:00 · build phase, AWS-setup stage._

---

## 0. Why now, and why not the "DevOps guide" pattern

We're wiring this at the AWS-setup stage on purpose: it's the cheapest moment to establish
the integration backbone (fewest resources to import later) and it removes the single
biggest current security risk — the static `~/.aws/credentials` access key.

The shared Medium guide (*Connecting a GitHub Repository with AWS*) describes the **older,
heavier** AWS pattern: **CodePipeline + CodeBuild + CodeDeploy onto EC2**, authenticated
with a stored **GitHub Personal Access Token (PAT)**. We take its *intent* (GitHub as the
source of truth → automated deploy) but not its mechanics, because for Selom's
serverless + Vercel shape that pattern is wrong on three counts:

| Guide's approach | Why it's wrong for Selom | What we do instead |
|---|---|---|
| Stored GitHub **PAT** | A long-lived secret — exactly the stored-credential risk we're removing | **GitHub Actions OIDC** → assumed role, zero stored secrets |
| **CodePipeline/Build/Deploy** | Always-on managed CI we don't need; cost + complexity | **GitHub Actions** (CI) + **CDK deploy** (CD) |
| Deploy to **EC2** | Always-on box; wrong runtime | **Lambda** (API) + **Fargate** (compute) + **Vercel** (FE) |

---

## 1. The triangle

```
                         ┌──────────────┐
                         │    GitHub     │  source of truth (steveneam/selom)
                         │  Actions CI   │
                         └──────┬───┬────┘
            OIDC (no keys)      │   │   native Git integration
        ┌───────────────────────┘   └───────────────────────┐
        ▼                                                     ▼
┌─────────────────┐                                   ┌──────────────┐
│      AWS        │   runtime: HTTPS + Clerk JWT       │    Vercel    │
│  API (Lambda)   │◀──────────────────────────────────│  Next.js FE  │
│  Compute(Fargate)│   CORS scoped to Vercel origins   │ (syd1 funcs) │
│  Aurora · S3    │                                   └──────┬───────┘
└─────────────────┘                                          │
        ▲                                                     │
        └─────────────────── Clerk (identity / JWT) ─────────┘
```

Three edges, each its own section: **GitHub→Vercel** (§2), **GitHub→AWS** (§3),
**Vercel→AWS runtime** (§4). Clerk sits across the bottom as the shared identity (§5).

---

## 2. Edge A — GitHub → Vercel (frontend CD)

**Mechanism: Vercel's native Git integration.** Connect the GitHub repo once in the Vercel
dashboard; thereafter every push to a branch → a **preview deployment** with a unique URL,
and every push to `main` → **production**. No workflow YAML to maintain; Vercel runs its own
build. Root directory = `app/frontend`.

- **Preview URLs** are the review surface (per-PR). Pair with the `frontend-ci` workflow
  (lint/typecheck/test/build) so a PR gets both a green check and a clickable preview.
- **Build settings:** framework = Next.js (auto-detected), install = `npm ci --legacy-peer-deps`
  (react-plotly.js stale peer-deps), build = `next build`.
- **Region:** set Vercel Functions to **`syd1`** (Sydney) so any data-touching server
  component/route handler runs next to the AWS origin in `ap-southeast-2`, not on a far edge.

**Owner action (dashboard, one-time):** Vercel → Add New Project → import `steveneam/selom`
→ root dir `app/frontend` → set the env vars in §6 → set Functions region `syd1`.

---

## 3. Edge B — GitHub → AWS (backend CI/CD, keyless)

### 3.1 CI (now — no AWS needed)
`.github/workflows/backend-ci.yml` runs `ruff check` + `pytest -m "not slow"` on a clean
Linux checkout for any PR/push under `app/backend`. `frontend-ci.yml` does the FE gate.
These need **no AWS credentials** and work the moment they're pushed.

### 3.2 CD (keyless via OIDC + CDK)
The deploy path uses **GitHub Actions OIDC**, not a stored key:

1. A workflow job declares `permissions: id-token: write`.
2. `aws-actions/configure-aws-credentials@v4` exchanges the GitHub OIDC token for temporary
   STS creds on the **`selom-github-deploy`** role (`role-to-assume: ${{ vars.AWS_DEPLOY_ROLE_ARN }}`).
3. The job runs `cdk deploy`, which assumes CDK's bootstrap roles to provision/update infra.

The role's trust policy (`infra/stacks/github_oidc_stack.py`) is scoped to **this repo only**,
`main` + the `production` environment — a fork or arbitrary branch cannot assume it. Its
permission is minimal: assume the `cdk-*` deployment roles (expand only if a job ever
deploys outside CDK).

**The deploy workflow itself is added at step 8** (when there are Lambda/Fargate targets to
deploy). Until then, only the OIDC role + CI exist. Template for that future workflow:

```yaml
# .github/workflows/deploy.yml  (added at step 8)
permissions: { id-token: write, contents: read }
jobs:
  deploy:
    environment: production
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ vars.AWS_DEPLOY_ROLE_ARN }}
          aws-region: ap-southeast-2
      - run: cd infra && pip install -r requirements.txt && npx aws-cdk@2 deploy --all --require-approval never
```

### 3.3 Blocked on admin creds (one-time)
Creating the OIDC provider + role needs `iam:*`, which `selom-dev` (PowerUser) lacks. The
owner runs the `infra/README.md` runbook once with admin/root creds: `cdk bootstrap` +
`cdk deploy SelomGithubOidc`, then sets the `AWS_DEPLOY_ROLE_ARN` repo variable. **After
that, the static `selom-dev` access key should be deactivated + deleted** (local dev → IAM
Identity Center SSO; CI → OIDC).

---

## 4. Edge C — Vercel → AWS (runtime)

The browser (or a `syd1` Vercel function) calls the AWS API directly over HTTPS.

- **Front door:** API Gateway **HTTP API** (1M req/mo free for year one, then ~$1/M) with a
  built-in **JWT authorizer** pointed at Clerk's issuer/JWKS. (Lambda Function URLs are the
  $0 fallback; **never ALB** — its ~$16/mo fixed cost alone exceeds the $10 budget.)
- **CORS — configure in ONE place** (the HTTP API), not also FastAPI's `CORSMiddleware`
  (double headers break preflight). `allow_origins` = the exact Vercel prod + preview
  domains (never `*`), `allow_headers: Authorization, Content-Type`, `allow_methods` per route.
- **S3 uploads:** the FE uses presigned POST straight to S3. **The S3 bucket CORS rule**
  (added when the FE upload path goes live) must allow `POST`/`PUT` from the Vercel origins,
  use the region endpoint, and *not* force `Content-Type` on the fetch (let the browser set
  the multipart boundary).
- **Latency rule:** keep data-heavy logic next to the data — call AWS from the browser, or
  pin the Vercel function to `syd1`. Don't run chatty data logic on a global edge function.

---

## 5. Clerk (shared identity)

Clerk issues the JWT the FE sends as `Authorization: Bearer`. AWS verifies it (HTTP API JWT
authorizer in prod; the backend's hand-rolled RS256-over-JWKS verifier already exists for
local/`dev` mode). The verified `sub` is the tenant key — never a caller-supplied param
(enforced by `auth/` + `TenantQuery`). Clerk owns ALL auth-identity email; Resend is
product/lifecycle only (see memory `selom-resend-email-decision`). Clerk's GitHub↔Vercel
hookup is just env vars (§6) + the Clerk dashboard allowed origins.

---

## 6. Environment variable inventory

| Where | Var | Value / source | Notes |
|---|---|---|---|
| **Vercel** (FE) | `API_PROXY_TARGET` | the HTTP API URL | the FE calls relative `/api/*`; `next.config.ts` rewrites them. **Today the destination is hardcoded `http://localhost:8000`** — at step 8 make it `process.env.API_PROXY_TARGET ?? "http://localhost:8000"` and set this on Vercel. (No `NEXT_PUBLIC_API_BASE_URL` exists in the FE.) |
| Vercel | `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk dashboard | public; only once Clerk is wired into the FE |
| Vercel | `CLERK_SECRET_KEY` | Clerk dashboard | secret (Vercel env, encrypted) |
| **GitHub** (Actions) | `AWS_DEPLOY_ROLE_ARN` | CDK output | repo **variable**, not a secret |
| **AWS** (backend, via Secrets Manager / SSM) | `SELOM_DATABASE_URL` | Aurora endpoint | Secrets Manager (rotation) |
| AWS | `SELOM_OBJECT_STORE=s3`, `SELOM_S3_BUCKET` | the prod bucket | SSM Parameter Store (free) |
| AWS | `SELOM_AUTH_MODE=clerk`, `SELOM_CLERK_ISSUER` | Clerk JWKS issuer | SSM Parameter Store |
| AWS | `SELOM_JOB_STORE=sql` | — | SSM Parameter Store |

**Secrets split (cost-optimal):** one Secrets Manager secret (the DB credential, for its
Aurora rotation, ~$0.40/mo) + free SSM Parameter Store for everything else; cache via the
Lambda Parameters-and-Secrets extension. No secret ever lands in the repo or a workflow file.

---

## 7. Status

| Item | State |
|---|---|
| Backend CI (`backend-ci.yml`) | ✅ added — works on push (no AWS) |
| Frontend CI (`frontend-ci.yml`) | ✅ added — lint/typecheck/test/build |
| CDK app + `SelomGithubOidc` stack | ✅ authored (`infra/`) — needs admin deploy |
| GitHub OIDC provider + deploy role | ⏳ **owner: run `infra/README.md` with admin creds** |
| `AWS_DEPLOY_ROLE_ARN` repo variable | ⏳ owner sets after the deploy |
| Vercel ↔ GitHub project + env + `syd1` | ⏳ owner: dashboard one-time |
| Kill the static `selom-dev` access key | ⏳ after OIDC + SSO work |
| Deploy workflow (`deploy.yml`) | 🔜 step 8 (targets don't exist yet) |
| HTTP API + JWT authorizer, S3 CORS | 🔜 step 8 |

**CI checks live immediately; everything that touches IAM/infra waits on the one-time admin
runbook, because `selom-dev` can't create IAM resources.**
