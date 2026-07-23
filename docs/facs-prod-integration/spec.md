# FACS `facs_gating` — Production Integration Spec

_Status: DECISION-READY (design only; no code written). Date-stamped 2026-07-23._
_Owner-facing decisions are collected in §9. Backend lane (Codex/Claude BE). FE lane: no change required._

Closes the two blockers in `agent_handoff/RISKS.md` #12 (FlowKit ⊥ pandas 3.0) and the honesty
gap it exposes in #11 (WS1.1). The `facs_gating` skill is built + verified as a dev artifact and
**HELD** from shipping; this spec is the plan to un-hold it.

---

## 1. Objective

Ship the `facs_gating` real (FlowKit) path in production by moving its compute **out of the main
`pandas>=3` interpreter into an isolated `pandas<3` worker**, called over a thin RPC boundary; and
make the skill **stamp its own honest engine posture** so a stub FACS figure carries the WS1.1
"example data — not your results" banner even in a global-`real` deployment.

**In scope:** the isolation mechanism + its build/deploy; the RPC/protocol and error propagation;
the generic per-skill provenance mechanism (closing the WS1.1 find_spec-gated gap, not just for
FACS); the file-level change plan; tests/ratchets.

**Out of scope:** any change to the flow science itself (`run_real.py` compute, `_flow.py`
builders, `_stub_figure`, `skill.json`, gate/transform semantics) — these are frozen and reused
verbatim. No FE change (the banner already reads `provenance.environment.engine_policy`). Not a
new host — "this box first."

---

## 2. Problem recap (grounding)

- **`skills/facs_gating/run.py`** routes real-vs-stub on a **local** `find_spec("flowkit")` (the
  `skills/umap_scrna/run.py` per-skill pattern), because FlowKit hard-pins `pandas<3,>=2.2` and
  **cannot** co-resolve with this backend's `pandas>=3.0`. FlowKit is deliberately **out** of
  `REQUIRED_ENGINE_MODULES` (`skills/_engine.py`) — as a required module it would drag the whole
  engine to `stub` on every box and refuse prod boot.
- **Consequence 1 (isolation):** with flowkit never importable in the main venv, the real path can
  never run in-process in prod. The compute in `run_real.py` must move to an isolated env.
- **Consequence 2 (honesty gap):** provenance is stamped by
  `companions/provenance.py::environment_snapshot()` → `skills/_engine.resolve_engine_policy()`,
  which is a **global** decision keyed only on `REQUIRED_ENGINE_MODULES`. In a global-`real`
  context (full science stack present) it returns `"real"` — even when `facs_gating` actually fell
  back to its stub because flowkit isn't importable. The FE banner
  (`app/frontend/components/project/stub-engine-banner.tsx` +
  `lib/skills/engine-policy.ts::isStubEngineFigure`) fires only on
  `environment.engine_policy === "stub"`, so a FACS stub currently ships mislabelled `"real"` — a
  direct breach of the WS1.1 "no black box" promise (`tests/test_engine_policy_guard.py` /
  `config._validate_backend_combos`, which only guard the global set).

Both are the exact class of problem RISKS #9 (OmicVerse) and #2 (Kaleido/Chromium) already solved
out-of-process; #12 says the fix is (a) an out-of-process FlowKit worker + (b) per-skill honest
provenance.

---

## 3. Decision — isolation mechanism: **sidecar venv + subprocess worker** (Docker rejected for v1)

**Decision:** run FlowKit in a **second `uv`/`pip` virtualenv pinned to `pandas>=2.2,<3` +
`flowkit`/`flowio`/`flowutils`**, invoked as a **spawn-per-call subprocess** with its own Python
interpreter, communicating over a **JSON line protocol on stdin/stdout**. The FCS is passed **by
path** (shared filesystem), the worker returns `{plotly_spec, table}` JSON. Reserve Docker as a
documented later hardening ratchet.

**Rationale (why venv, not container):**

1. **The blocker is purely a Python-pin conflict.** FlowKit ⊥ pandas is a dependency-resolution
   problem; a second venv *fully* resolves it (isolated site-packages, its own interpreter). That
   is the entire requirement — a container would solve the same pin problem plus extras we don't
   yet need. "Smallest change that satisfies the goal" (CLAUDE.md coding guidelines) points at the
   venv.
2. **Small, permissive, first-party surface — unlike OmicVerse.** RISKS #9 reached for a container
   partly because OmicVerse is GPL-3.0 + 50 transitive deps. FlowKit/FlowIO/FlowUtils are **BSD-3**
   with a tiny closure (numpy, pandas<3, scipy) and the worker is **our own code** calling a small
   library — no license/SCA reason to sandbox it in a container.
3. **Dev/CI stay trivial.** A venv is buildable with the already-blessed `uv pip install flowkit
   flowio flowutils` (the `flow` extra note in `pyproject.toml` already prescribes exactly this
   imperative install) with **no Docker daemon dependency** to run or test the real FACS path
   locally. A container would make the real path un-runnable on any dev box without Docker up.
4. **Shared filesystem = pass-by-path.** Same box, same user → the worker reads the temp FCS the
   router already wrote. No bind-mount, no piping a binary upload across a container boundary.
5. **A true-kill timeout falls out for free.** `config.py` explicitly laments that the current
   thread-based `skill_timeout_s` "can't kill a hung run — a true kill needs a subprocess worker —
   deferred infra." `subprocess.run(timeout=…)` gives FACS the first real kill-able timeout.

**Rejected alternative — Docker container (compose service, the `deploy/nango/` precedent):**
Docker is installed and `deploy/nango/docker-compose.yaml` is a working precedent (127.0.0.1-bound
services + healthchecks). It gives **stronger isolation** (own filesystem, droppable caps,
read-only rootfs, mem/CPU limits, no-network) which matters for parsing untrusted uploads at
multi-tenant scale. It loses on: an image build + a running daemon as a hard dependency for dev/CI
and the deploy; a long-lived service needs lifecycle/health management; passing the FCS needs a
bind-mount or byte-pipe. **Verdict:** the added isolation isn't yet worth the operational weight
for a single-tenant "this box first" deploy of a first-party BSD worker. The design keeps a
**transport seam** (§4) so the venv→container swap is a *client-only* change if/when Selom moves to
hostile multi-tenant prod. That condition (multi-tenant, hostile uploads) is the single trigger
that flips this decision — surfaced in §9.

**Why spawn-per-call, not a persistent worker service:** FACS runs are user-initiated figure
generations (not high QPS), already bounded by `skill_timeout_s` (120s). A per-call spawn pays a
~1–3s cold numpy+flowkit import but buys **crash isolation** (no wedged-worker failure mode), **zero
lifecycle code**, and a clean `subprocess.run` timeout. A persistent stdin/stdout or socket service
is the documented upgrade if profiling shows the import cost hurts (surfaced in §9).

---

## 4. RPC / protocol design

### 4.1 Transport (v1: subprocess, JSON line protocol)

```
main interpreter (pandas 3)                worker interpreter (pandas<3, flowkit)
──────────────────────────                 ─────────────────────────────────────
worker_client.run(data_path, params)
  → subprocess.run(
        [WORKER_PY, "-m", "…_worker_main"], ── stdin  ⇒ {"fcs_path","params","limits"}
        timeout=skill_timeout_s,
        env={PYTHONPATH=app/backend, …})    ── stdout ⇐ {"ok":true,"figure":{data,layout,table}}
                                                       or {"ok":false,"error":{category,code,message,fix}}
```

- **Request:** `{"fcs_path": str, "params": {…}, "limits": {"as_bytes":…, "cpu_s":…}}` written to
  the worker's **stdin** as one JSON line. `params` is the already range-validated
  (`validate_param_ranges`) skill param dict.
- **FCS handoff = by path.** The worker opens `fcs_path` directly (shared FS). No bytes over the
  pipe — FCS files are large; only the small param dict travels on stdin.
- **Response:** the worker prints one JSON object to **stdout** and exits 0. On success,
  `figure` is exactly the current `run_real.run` return shape — `{data, layout, table}` (table
  nested) — so `skills/contract.py::_execute` pops `table` and themes/caches the figure with **zero
  contract change**. The result is bounded by the existing `max_events` cap (≤50k×2 floats), i.e. a
  few MB of JSON on a pipe — acceptable.
- **JSON only, never pickle** — the worker executes only the declared `params` + a fixed compute;
  no caller-supplied code crosses the boundary.

**The isolation boundary is orthogonal to inline-vs-arq.** `jobs/queue.py`'s arq worker runs in the
**main** venv (pandas 3) and cannot host flowkit either, so whether `facs_gating` runs inline
(`/run`) or as an arq job, `run()` dispatches to the subprocess worker the same way. The job queue
is **not** the isolation seam; the subprocess is a nested boundary inside the runner. (This is why
the queue is not the chosen RPC.)

### 4.2 Error propagation → `routers/_errors.py::RunError` taxonomy

The worker classifies failures and the client maps them into the existing envelope with **no new
router branch for the happy taxonomy**, reusing the run-path's existing `ValueError → RunError.bad_input`:

| Failure | Worker signal | Client raises | Router maps to |
|---|---|---|---|
| Unresolvable x/y channels, malformed comp matrix, empty events (today's `run_real` `ValueError`s) | `{"ok":false,"error":{"category":"bad_input",…}}`, exit 0 | `ValueError(message)` | existing `except ValueError` in `routers/_run.py::_execute_skill_run` → **400** `skill_run_failed` (self-framed message preserved) |
| Worker not configured / interpreter missing | (client detects before spawn) | `WorkerError(...)` | new `except WorkerError` → `RunError.internal("facs_worker_unavailable", …, status_code=503)` |
| Worker crash / non-zero exit / unparseable stdout | non-zero exit or bad JSON | `WorkerError(...)` | → `RunError.internal(…, 503)` |
| Timeout (hung compute) | `subprocess.TimeoutExpired` → child killed | `WorkerError(...)` | → `RunError.internal("facs_worker_timeout", …, status_code=504)` |

- `WorkerError` is a **plain, HTTP-agnostic exception** defined in the skills layer
  (`skills/facs_gating/worker_client.py`), so the skill layer never imports FastAPI. `routers/_run.py`
  gains **one** `except WorkerError` arm (before the bare-Exception fall-through) mapping it to
  `RunError.internal`. The **job path** (`jobs/queue.py::execute_job`) already wraps in
  `except Exception → status=FAILED, error=str(exc)`, so a `WorkerError` there records a clean
  FAILED job with no code change.
- The bad_input class is deliberately funnelled through `ValueError` so the **already-tested**
  `except ValueError` mapping (a data problem is a fixable 400, not a 5xx) is reused unchanged.

### 4.3 Security / limits (worker reads an untrusted user FCS)

FlowIO is pure-Python BSD (no C parse of attacker memory — lower risk than a C parser), but this is
a SaaS reading user uploads, so the subprocess is contained:

- **Wall-clock kill:** `subprocess.run(timeout = settings.skill_timeout_s)` — a *real* kill of the
  child (the outer `asyncio.wait_for` only abandons the thread; the subprocess timeout is what
  actually terminates the compute). Set ≤ the outer ceiling so it fires first.
- **Resource caps:** the worker **self-applies** `resource.setrlimit(RLIMIT_AS, …)` (memory) and
  `RLIMIT_CPU` at startup from the `limits` in the request (thread-safe; preferred over a parent
  `preexec_fn`). Budget from new config (`SELOM_FACS_WORKER_MEM_MB`, default e.g. 2048).
- **Scoped cwd + no network needed:** the compute is local; run the child in a temp cwd. (Network
  namespace isolation is a Docker-mode upgrade, not v1.)
- **No secrets in env:** pass only `PYTHONPATH` + the limit budget; do not inherit AWS/DB creds.

---

## 5. Honest per-skill provenance — closing the WS1.1 gap **generically**

The mechanism must be reusable for **any** skill whose real engine is gated outside
`REQUIRED_ENGINE_MODULES` (today: `facs_gating`; the pattern also protects a future find_spec-gated
skill), not a FACS special-case.

### 5.1 Design principle — availability = **configured**, not live-healthy

Mirror the existing global engine philosophy exactly (`resolve_engine_policy` docstring: installed →
real; missing → stub; forced-real-but-broken → honest **error**, never a mislabelled stub):

- **Engine posture (provenance label) is a function of DEPLOY CONFIG**, not per-request health:
  `"real"` iff the FACS worker is **configured/installed** on this box; `"stub"` otherwise.
- **Health is a runtime concern.** A *configured* worker that fails at call time → `RunError.internal`
  (an honest 5xx), **never** a silent stub. So a configured deployment can never fabricate a FACS
  figure; the stub only serves where the worker was never configured (dev/demo), and there the
  banner fires.

This choice has a critical property: the posture is **stable within a deploy**, so it is **cheap to
recompute** (an env read + `os.path.exists`, no worker spawn) at provenance time and **cannot drift**
from what `run()` routed on — both call the same resolver. (It also sidesteps a result-cache
mislabel: because posture is deploy-stable, a cached figure's posture equals the recomputed stamp
within a deploy. Optional hardening — folding posture into the `_result_cache` key — is noted in §8
but not required for v1.)

### 5.2 The generic mechanism

**`skills/_engine.py`** gains a per-skill override registry + resolver, peer to the global one:

```
_SKILL_ENGINE_POLICY: dict[str, Callable[[str | None], str]] = {}   # skill_id → resolver(engine)

def register_skill_engine_policy(skill_id, resolver): _SKILL_ENGINE_POLICY[skill_id] = resolver

def resolve_skill_engine_policy(skill_id, engine=None) -> str:
    override = _SKILL_ENGINE_POLICY.get(skill_id)
    return override(engine) if override else resolve_engine_policy(engine)   # global fallback
```

A skill whose real path depends only on `REQUIRED_ENGINE_MODULES` needs **nothing** — it inherits
the global policy. A skill gated on a non-required module registers a resolver.

**`skills/facs_gating/engine.py`** (NEW, light — never imports flowkit) is the **single source of
truth** for "is the FACS real engine available?", used by **both** `run()` routing and provenance:

```
def facs_worker_available() -> bool:
    py = settings.facs_worker_python()          # SELOM_FACS_WORKER_PYTHON
    return bool(py) and pathlib.Path(py).exists()

def facs_engine_policy(engine=None) -> str:     # mirrors resolve_engine_policy, swapping the probe
    e = (engine or settings.skills_engine()).lower()
    if e == "stub": return "stub"
    if e in ("real", "scanpy"): return "real"   # forced-real → "real"; run() errors if unconfigured
    return "real" if facs_worker_available() else "stub"      # auto
# register at import: register_skill_engine_policy("facs_gating", facs_engine_policy)
```

**`companions/provenance.py`** — `build()` (which already receives `spec`) resolves the per-skill
posture and passes it down; `environment_snapshot` accepts an optional override, defaulting to the
global (so its other caller, `tests/test_provenance.py`, and every non-FACS skill are unchanged):

```
def environment_snapshot(engine_policy: str | None = None) -> dict:
    from skills._engine import resolve_engine_policy
    return {..., "engine_policy": engine_policy or resolve_engine_policy(), ...}

# in build():  policy = resolve_skill_engine_policy(spec.id)
#              "environment": environment_snapshot(engine_policy=policy)
```

Because **all four** `provenance.build` callers (`routers/_run.py`, `jobs/queue.py`,
`ai/execute.py`, `reproduction/core.py`) pass `spec` positionally, this is a **one-site change** that
makes every FACS run — synchronous, job, AI-assisted, or reproduction — stamp honest provenance with
**no caller edits**. The FE (`engine-policy.ts`, `stub-engine-banner.tsx`) reads the same
`environment.engine_policy` field and needs **no change** — the value simply becomes truthful.

### 5.3 `run.py` routing after the change

```
policy = resolve_skill_engine_policy("facs_gating")
if policy == "real":
    from skills.facs_gating.worker_client import run as run_worker
    return run_worker(data_path, params)     # WorkerError if configured-but-unhealthy or unconfigured-forced-real
return _stub_figure(params)                  # honest stub → provenance stamps "stub" → banner fires
```

The direct `find_spec("flowkit")` and the in-process `from …run_real import run` are removed from
`run.py`. `_stub_figure` is unchanged.

---

## 6. File-level change plan

**New**

| Path | Role |
|---|---|
| `skills/facs_gating/engine.py` | Light (no flowkit). `facs_worker_available()` + `facs_engine_policy()`; registers into `_SKILL_ENGINE_POLICY`. Single source of truth for FACS real-availability. |
| `skills/facs_gating/worker_client.py` | Main-side RPC client. Builds the subprocess (worker python + `_worker_main`), writes request JSON to stdin, enforces `subprocess.run(timeout)`, parses stdout, maps errors (`ValueError` for bad_input, `WorkerError` for internal). Defines `WorkerError`. Light. |
| `skills/facs_gating/_worker_main.py` | Subprocess **entrypoint**, runs under the worker interpreter. Self-applies rlimits; reads stdin JSON; calls the frozen compute; catches its `ValueError`s → `{"ok":false,"error":{category:"bad_input",…}}`; writes stdout JSON. Imports flowkit — never imported by the main interpreter. |
| `deploy/facs-worker/requirements.txt` | The worker venv pins: `pandas>=2.2,<3`, `flowkit>=1.3`, `flowio>=1.4`, `flowutils>=1.1`, `numpy`, `scipy`. **Not** a main-project extra (would wedge `uv`). |
| `deploy/facs-worker/build.sh` + `README.md` | `uv venv .venv-facs && uv pip install -r requirements.txt`; prints the interpreter path to set as `SELOM_FACS_WORKER_PYTHON`. Documents the isolation rationale + the container-upgrade path. |
| `tests/test_facs_provenance.py` | E2E honesty: worker **unconfigured** → a real-context run stamps `engine_policy == "stub"` (the banner-reachability assertion); worker **configured** (mocked resolver) → `"real"`. The proof the WS1.1 gap is closed for FACS. |
| `tests/test_facs_worker_client.py` | Client error mapping against a **fake worker script** (a stdlib python printing canned JSON / hanging / non-zero exit): bad_input → `ValueError`; crash/timeout/unconfigured → `WorkerError`; timeout truly kills the child. No flowkit needed. |

**Modified**

| Path | Change |
|---|---|
| `skills/facs_gating/run.py` | Route via `resolve_skill_engine_policy("facs_gating")` → `worker_client.run` or `_stub_figure`. Drop the `find_spec("flowkit")` + in-process `run_real` import. Update the module docstring/comment. |
| `skills/_engine.py` | Add `_SKILL_ENGINE_POLICY`, `register_skill_engine_policy`, `resolve_skill_engine_policy`. Update the flowkit comment (routes on the worker, not `find_spec`). `REQUIRED_ENGINE_MODULES` unchanged (flowkit stays out). |
| `companions/provenance.py` | `environment_snapshot(engine_policy=None)`; `build()` computes `resolve_skill_engine_policy(spec.id)` and passes it. Backward-compatible default. |
| `config.py` | Add `SELOM_FACS_WORKER_PYTHON` (path) + `SELOM_FACS_WORKER_MEM_MB` (rlimit budget) fields + a live `facs_worker_python()` accessor (single-env-reader ratchet home). Optional soft **startup log** when unset + `is_production` ("facs_gating worker not configured; FACS serves labelled example data here"). |
| `routers/_run.py` | One `except WorkerError → RunError.internal(status 503/504)` arm in `_execute_skill_run`, before the bare-Exception fall-through. |
| `tests/test_engine_policy_guard.py` | Add: (a) FACS honesty — with the global stack present but the FACS worker unconfigured, `resolve_skill_engine_policy("facs_gating") == "stub"` while the global `resolve_engine_policy() == "real"` (proves the override diverges honestly); (b) a generic structural ratchet — any `skills/**/run.py` still containing a bare `find_spec("<module ∉ REQUIRED_ENGINE_MODULES>")` **routing** token must be registered in `_SKILL_ENGINE_POLICY` (catches the next skill copying the old FACS pattern). |
| `tests/test_flow_smoke.py` | Split: keep a **compute-unit** test (`importorskip flowkit`, call the frozen `run_real.run` directly — the science) + add a **boundary** test gated on the worker venv (`SELOM_FACS_WORKER_PYTHON` set) that spawns the real subprocess end-to-end. |
| `pyproject.toml` | Amend the `flow` extra comment: these pins install into the **sidecar worker venv** (`deploy/facs-worker/`), never the main env. |
| `agent_handoff/RISKS.md` #12 | On completion: mark the prod-integration done; note the worker + per-skill provenance shipped. |

**Frozen / reused verbatim (no change):** `skills/facs_gating/run_real.py` (the compute — the worker
imports and calls it; the existing importorskip test still covers it), `skills/_flow.py`,
`skills/facs_gating/skill.json` (background/references/methods basis), `_stub_figure`,
`skills/_plotly.py::jsonable` (numpy-only; worker-safe), `companions/methods.py`, the FE banner +
`engine-policy.ts`.

> Note on the prompt's `contract.py` question: the provenance stamp lives in
> `companions/provenance.py` (+ the per-skill resolver in `skills/_engine.py`), **not**
> `skills/contract.py`. `contract.py::_execute` needs **no change** — the worker returns the same
> `{data, layout, table}` shape it already pops/themes/caches. (The only reason to touch caching
> would be the optional posture-in-cache-key hardening in §8, which lands in `skills/_result_cache.py`
> + `jobs/queue.py`, not `contract.py`.)

---

## 7. Milestones (dependency-ordered; each ends at a verifiable state)

1. **M1 — Per-skill provenance mechanism (honesty first, no worker yet).**
   `resolve_skill_engine_policy` + registry in `_engine.py`; `facs_gating/engine.py` with
   `facs_engine_policy` (worker "available" == config path set + exists); wire
   `provenance.build`/`environment_snapshot`; config field + accessor.
   **Verify:** `test_facs_provenance.py` + the extended `test_engine_policy_guard.py` green — a
   global-`real` FACS run with no worker configured stamps `engine_policy="stub"`; the FE banner
   fires in a manual dev run. *(This slice alone closes the WS1.1 gap even before the worker exists.)*
2. **M2 — Worker script + client, subprocess boundary.**
   `_worker_main.py` (imports flowkit; wraps the frozen `run_real.run`; rlimits; error JSON);
   `worker_client.py` (spawn, timeout, parse, `WorkerError`); `run.py` routes to the client on
   `policy=="real"`. `routers/_run.py` `except WorkerError` arm.
   **Verify:** `test_facs_worker_client.py` green against a fake worker (bad_input→400 shape,
   crash/timeout→internal, true child kill). Contract/golden tests unaffected (stub path unchanged).
3. **M3 — Worker env build + real boundary test.**
   `deploy/facs-worker/{requirements.txt,build.sh,README.md}`; build the venv; set
   `SELOM_FACS_WORKER_PYTHON`.
   **Verify:** the boundary test in `test_flow_smoke.py` runs the real subprocess on the synthetic
   FCS end-to-end (density + rectangle gate + quadrant + each transform/plot + operator
   compensation) and matches the current in-process assertions; a live `/run` on a real `.fcs`
   returns a real figure with `engine_policy="real"` and **no** banner.
4. **M4 — Deploy wiring + CI + docs.**
   CI step builds the worker venv (small BSD install) and exports `SELOM_FACS_WORKER_PYTHON` so the
   boundary test actually runs; deploy runbook documents the build + the env var; RISKS #12 updated;
   un-hold FACS.
   **Verify:** CI green with the boundary test active; a prod-shaped boot (`SELOM_ENV=prod`, full
   stack, worker configured) serves a real FACS figure; the same boot **without** the worker either
   serves a labelled stub or an honest "unavailable" per the §9 decision.

---

## 8. Risks & rollback

- **Cold-import latency (~1–3s/run).** Bounded by `skill_timeout_s`; acceptable for user-initiated
  figures. *Watch:* p95 FACS run time. *Mitigation/upgrade:* persistent worker service or Docker
  sidecar behind the same `worker_client` seam (transport-only change).
- **Result-cache posture drift (low, deploy-boundary only).** Posture is deploy-stable, so within a
  deploy a cached figure's stamp matches. If an admin **adds/removes** the worker without bumping
  the skill version, an LRU-cached figure could carry the prior posture. *Mitigation:* on a
  worker-config change, cold the FACS cache; **optional hardening** — fold the effective per-skill
  posture into the `skills/_result_cache.cache_key` (+ `jobs/queue._content_keys`) so real/stub
  results are distinct cache entries. Deferred from v1; flagged.
- **Worker/main figure-shape divergence.** The worker must return byte-identical `{data,layout,table}`.
  *Guard:* the boundary test asserts the same shape the in-process test asserted today; the frozen
  `run_real.run` is the shared compute, so divergence can only come from serialization — covered by
  `jsonable` (already used).
- **PYTHONPATH/import skew.** The worker needs `skills._flow`/`_plotly`/`_table` (pure) importable
  under its interpreter. *Guard:* the boundary test exercises the exact spawn env; `build.sh`
  documents `PYTHONPATH=app/backend`.
- **Forced `SELOM_SKILLS_ENGINE=real` with no worker.** Policy `"real"` → `run()` calls the client →
  `WorkerError` → honest 503 (never a mislabelled stub) — matches the global forced-real semantic
  (`test_forced_real_resolves_real_even_if_deps_missing`).
- **Rollback:** the change is additive + behind the per-skill resolver. Reverting `run.py` to the
  in-process `find_spec("flowkit")` restores the prior HELD dev-artifact behaviour; M1 (provenance)
  can stand alone even if M2–M4 are reverted, leaving FACS honest-but-stub.

---

## 9. Open decisions for the owner

1. **Isolation mechanism — confirm sidecar venv (recommended) vs Docker now.** Recommend venv for
   v1 (§3). The **one** condition that flips it: a move to **hostile multi-tenant prod** where a
   container's stronger sandbox (no-network, read-only rootfs, caps/mem limits) is warranted for
   parsing untrusted uploads. Confirm we are "single-tenant this-box" for now.
2. **Prod behaviour when the worker is absent.** Recommended: FACS is an **optional** health-checked
   service — **not** a hard `REQUIRED_ENGINE_MODULE`, so prod boot does **not** fail if it's missing.
   Sub-choice for a FACS run with no worker in prod:
   (a) serve a **labelled example stub** (banner fires — consistent with WS1.1 dev/demo semantics), or
   (b) return an honest **"flow cytometry isn't available on this deployment"** (`RunError.unsupported`)
   so a prod user never sees fabricated FACS numbers even behind a banner.
   *Recommendation:* (b) in prod (fuller "no fake science in prod" promise), (a) in dev/demo. This is
   a small `is_production` branch in `run()`; call it, or accept (a) everywhere for v1.
3. **Worker lifecycle — confirm spawn-per-call** (recommended) is acceptable given ~1–3s/run, vs
   invest in a persistent worker now.
4. **CI cost — build the worker venv in CI** (recommended, ~1 min + a small BSD install) so the RPC
   boundary is actually exercised, vs keep the boundary test skip-gated and rely on the compute-unit
   test only.

---

## 10. v1 Acceptance checklist

- [ ] With the full science stack present and **no** FACS worker configured, a `facs_gating` run
      (`/run`, job, AI, and reproduction paths) stamps `provenance.environment.engine_policy == "stub"`,
      and the FE renders the "Example data — not your results" banner. *(WS1.1 gap closed.)*
- [ ] `resolve_skill_engine_policy("facs_gating")` returns `"stub"` when the worker is unconfigured
      even though the global `resolve_engine_policy()` returns `"real"`; returns `"real"` when
      configured; returns `"stub"` under forced `SELOM_SKILLS_ENGINE=stub`.
- [ ] With the worker venv built + `SELOM_FACS_WORKER_PYTHON` set, a real `.fcs` `/run` returns a
      genuine FlowKit figure (`engine_policy=="real"`, **no** banner), matching every current
      `test_flow_smoke.py` assertion (density+rect gate, quadrant=4 pops, all transforms/plots,
      operator compensation) — now via the subprocess boundary.
- [ ] flowkit never imports in the main interpreter; `uv sync`/`uv lock` are unaffected; the prod
      boot guard still passes with the full stack and does **not** require flowkit.
- [ ] Error mapping: a channel/compensation/empty-data failure → **400** (`skill_run_failed`,
      self-framed message); worker crash/unreachable → **503**; hung compute → **504** with the child
      process actually killed.
- [ ] The generic ratchet in `test_engine_policy_guard.py` fails if a future `run.py` routes on a
      `find_spec("<non-required>")` without registering a per-skill policy.
- [ ] Contract/golden tests and every non-FACS skill are byte-unchanged; the FE has no code change.
- [ ] `agent_handoff/RISKS.md` #12 updated to "prod-integration shipped"; FACS un-held.

---

## 11. Grounding (files read)

`skills/facs_gating/{run.py,run_real.py,skill.json}` · `skills/_flow.py` · `skills/_plotly.py` ·
`skills/_engine.py` · `skills/contract.py` · `skills/umap_scrna/run.py` (per-skill find_spec
precedent) · `companions/provenance.py` · `config.py` (`_validate_backend_combos`, `is_production`,
live accessors, subprocess-kill note) · `routers/_run.py` · `routers/_errors.py` · `jobs/queue.py`
(inline/arq boundary) · `pyproject.toml` (`flow` extra + the OmicVerse note) ·
`tests/test_engine_policy_guard.py` · `tests/test_flow_smoke.py` · `tests/test_provenance.py`
(environment_snapshot caller) · `app/frontend/components/project/stub-engine-banner.tsx` ·
`app/frontend/lib/skills/engine-policy.ts` · `agent_handoff/RISKS.md` #2/#9/#11/#12 ·
`deploy/nango/docker-compose.yaml` (container precedent).
