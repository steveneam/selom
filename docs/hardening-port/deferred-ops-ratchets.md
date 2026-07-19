# Deferred ops ratchets (M-008) — recorded, not built

_Port work-package W-003 / M-008. Documentation-only, **ungated**. Date-stamped 2026-07-19._

The engineering-practices port (W-001…W-003) brought the **build-time** ratchets into Selom now:
repo-hygiene scan, single-env-reader boundary, the consolidated `ci` gate, worktree tooling, the
lean-handoff model, and the graphify wiring-retirement. Six further ratchets from the source ops
playbook are **deploy-time** — they only have something to protect once Selom has a live cloud
backend. Building them against a backend that does not yet exist would be machinery guarding nothing.

So they are **recorded here, not built.** Each entry states the **principle ported**, the **machinery
deliberately skipped** (and why the source's shape does not transfer), and the **build trigger**. The
common trigger is: **the AWS backend deploy going live** (Fargate + Aurora + S3 per
`docs/aws-materialization/plan.md`; the frontend already ships on Vercel). Selom's target is a managed
cloud stack (Vercel + Fargate/Aurora/S3), **not** the source's single-VPS shape — several source
mechanisms are replaced by managed-platform equivalents rather than ported verbatim.

> **When any of these is built, it graduates from this file into a real ratchet** (a CI check, an
> IaC assertion, an executable restore drill) and its row here is replaced by a pointer to that
> ratchet. Until then, this file is the record that the gap is known and intentional — not forgotten.

---

## 1. OIDC deploy — never a static key

- **Principle ported:** CI deploys to the cloud by assuming a role via short-lived OIDC-federated
  credentials; no long-lived cloud access key ever lives in a CI secret or a repo.
- **Machinery skipped:** the source's role/trust-policy wiring is VPS/registry-shaped. Selom's is
  GitHub-Actions → AWS: a GitHub OIDC identity provider + an IAM role with a trust policy scoped to
  this repo + ref, assumed by `aws-actions/configure-aws-credentials` with no `aws-access-key-id`.
- **Build trigger:** the first CI job that touches AWS (push image to ECR / update the Fargate
  service / run a migration). **Until then:** the local dev static key stays out of the repo (it is
  in `~/.aws/`, gitignored), and rotating it to OIDC is an open item on the owner queue — the static
  key is *replaced*, never re-minted.

## 2. Content-verified restore drill — a backup you have not restored is not a backup

- **Principle ported:** every stateful store has a backup **and** an automated, content-verifying
  restore drill — restore into a scratch target and assert the restored content matches a known
  digest/row-count, not merely that the restore command exited 0.
- **Machinery skipped:** the source drills a self-hosted Postgres + a filesystem blob store. Selom's
  stores are **Aurora** (automated snapshots / PITR) and **S3** (versioning + lifecycle). The drill
  becomes: restore an Aurora snapshot to a throwaway cluster and assert a canary
  table's checksum; re-fetch a set of S3 object versions and assert their SHA-256. The "did it exit
  0" trap is the same on managed storage — a green snapshot job proves storage, not restorability.
- **Build trigger:** first real user data in Aurora/S3. **Until then:** the reproduction corpora are
  regenerable/deposited (not user data), so there is nothing yet whose loss is unrecoverable.

## 3. External dead-man ping on any cron

- **Principle ported:** every scheduled job pings an **external** dead-man monitor on success; the
  monitor alerts when a ping is *missing*. A cron that silently stops firing is the failure mode a
  self-hosted "is it running?" check cannot catch — the same class as the graphify hook that went
  silently stale (M-007's lesson).
- **Machinery skipped:** the source uses a specific external monitor + systemd-timer shape. Selom's
  scheduled work will be EventBridge → Fargate/Lambda (e.g. the pending-upload sweeper, any
  reindex/rebuild job); the ping target is a hosted dead-man service (or an SNS-backed equivalent).
  The invariant, not the vendor, is what ports.
- **Build trigger:** the first deployed cron/scheduled task. **Until then:** no scheduled job runs in
  production; the local sweeper runs inline.

## 4. Migration / seed idempotency

- **Principle ported:** schema migrations and seed steps are **idempotent** — re-running the deploy,
  or a retried/duplicated invocation, converges to the same state and never double-applies. Proven by
  an executable test that runs the migration twice against a scratch DB and asserts equality.
- **Machinery skipped:** the source's migration runner differs; Selom uses Alembic against Aurora
  (dev/test on SQLite — `SELOM_DB_AUTO_CREATE` auto-creates in dev, prod applies the migration). The
  idempotency proof is an Alembic upgrade→upgrade (no-op second pass) + a seed re-run assertion.
  (Note: job-level idempotency already exists in-app — `SELOM_JOB_IDEMPOTENCY`, config.py — this
  ratchet is the *deploy/migration* peer of that.)
- **Build trigger:** the first Alembic migration shipped to Aurora. **Until then:** the dev path
  auto-creates tables from the schema; there are no migrations to double-apply.

## 5. Post-deploy posture re-assertion

- **Principle ported:** after every deploy, an automated check **re-asserts** the security/config
  posture — the deploy is not "done" until the posture is confirmed, so drift or a forgotten toggle
  fails the deploy loudly instead of surfacing later. This is the deploy-time peer of the in-app
  `is_production` honesty guard (`config._validate_backend_combos`), which already fails a prod boot
  that would serve the fabricated stub.
- **Machinery skipped:** the source re-asserts host-level firewall/service posture on a VPS. Selom's
  posture is managed-cloud: S3 bucket is private + SSE-on, the Fargate task role is least-privilege,
  auth is real Clerk (not dev mode), the skills engine is `real` (not stub). The check runs
  post-deploy (smoke job) and asserts each, rather than re-running host hardening.
- **Build trigger:** the AWS backend deploy. **Until then:** `is_production` enforces the critical
  subset (no stub in prod, S3/Clerk imply prod) at application boot.

## 6. Self-arming rot latch

- **Principle ported:** long-lived automation carries a **self-arming rot latch** — if it has not
  successfully run within an expected window, it flips a visible, blocking state instead of decaying
  silently. The archetypal rot this session cleaned up: the graphify hook stopped rebuilding on
  2026-06-21 and *nothing noticed* because staleness was invisible (M-007). A rot latch makes "this
  has not run in N days" a loud, arming condition.
- **Machinery skipped:** the source's latch is tied to its cron+monitor shape (overlaps #3 but is
  distinct: #3 catches a job that stopped firing; #6 catches automation whose *output* silently went
  stale while the job still "ran"). Selom's latch attaches to whatever long-lived rebuild/refresh
  automation exists post-launch (e.g. a periodic gene-set/reference rebuild), asserting freshness of
  the *artifact*, not liveness of the *job*.
- **Build trigger:** the first long-lived scheduled automation whose output is consumed by the
  product. **Until then:** no such automation runs; the executable ratchets are checked on every CI
  run (they cannot silently rot — a stale guard fails visibly).

---

### Closure

With M-007 (graphify wiring-retirement) landed and these six deploy-time ratchets recorded, **W-003
is complete** and with it the whole engineering-practices port (W-001…W-003). The build-time ratchets
are live in CI now; the deploy-time ratchets are recorded here and will be built at the AWS backend
deploy. See `docs/hardening-port/gate-ledger.md` (W-003 — COMPLETE) and `docs/eng-practices-port/plan.md`.
