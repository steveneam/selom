# Live AI gateway wiring — Vercel AI Gateway + operator build-stand-in

_2026-06-30 · NEXT#1 (the gateway-on initiative). Owner surfaced an existing **Vercel AI
Gateway** (Groq → Bedrock failover, `meta/llama-3.3-70b`) already used by eamos. This wires
Selom's `ActionGateway` seam to that real, cheap, **provider-agnostic** gateway as the product
path, with the **operator** (Claude-as-gateway, recorded, zero-credit) as the build/optimize
stand-in so we don't spend credit while developing. Supersedes the "operator stand-in is the dev
default" framing in [[selom-claude-acts-as-ai-gateway]] / the resume's NEXT#1 — the live gateway is
now the intended runtime; the operator is the build-time substitute + the CI/showcase zero-spend
artifact._

## Forcing-Q decisions (owner, 2026-06-30)

1. **Gateway key** → mint a **separate** AI Gateway API key under the **same** Vercel team as
   eamos. Same credit/billing pool; per-app usage attribution + independent rotation; zero extra
   cost. (The Vercel AI Gateway is account/team-level — one endpoint `https://ai-gateway.vercel.sh/v1`,
   bearer `vck_…` key — so "another gateway" is never created; at most another key.)
2. **Operator vs live** → the **live gateway is the real target**; during **build & optimization**
   the **operator** stands in (recorded, Claude-authored, **no credit spent**). So: develop/tune on
   `operator` (free, deterministic), flip to `gateway` to verify real AI (minimal spend), ship on
   `gateway`. The operator recordings keep lasting value as (a) free build-time dev, (b) CI-safe
   deterministic tests, (c) a **zero-spend path for the finite public showcase** (3 known papers).
3. **Client implementation** → **port the eamos httpx client** (`AIGatewayEngine`), not PydanticAI.
   _Rationale (owner asked "which is better?"):_ the Vercel gateway and PydanticAI are **different
   layers** — the gateway is the serving endpoint (runs the model, bills, fails over); PydanticAI /
   the httpx client are just *clients* that call it. So **cost is identical** (same Llama tokens,
   same gateway bill, +$0 for either client) and **performance is a wash** (one HTTPS round-trip
   dominates). The decision is code-fit: the httpx port is lighter, proven against this exact
   gateway, needs no dependency churn, and Selom **already validates AI proposals server-side the
   same way it validates human input**, which makes PydanticAI's model-side schema-retry largely
   redundant. PydanticAI would only earn its weight if we wanted the *model itself* to guarantee the
   `ActionPlan` schema — we don't.

## Architecture — three gateway modes behind one seam

`routers/ai.py::get_action_gateway()` is the single selection point (already mirrors the
`OperatorVisionGateway` discipline). Extend it from `null | live` to:

| `SELOM_AI_GATEWAY` | Gateway | `source` of a real result | Role |
|---|---|---|---|
| `gateway` (+ `AI_GATEWAY_API_KEY`) | **`VercelAIGateway`** (new) | `"ai"` | **verify + production** — real Llama via the Vercel gateway |
| `operator` | **`OperatorActionGateway.from_recordings(path)`** | `"ai"` | **build/optimize default** — I author outputs, **no credit** |
| `live` (+ `ANTHROPIC_API_KEY`) | `PydanticAIGateway` (kept) | `"ai"` | alternative direct-Anthropic path (back-compat) |
| _unset / `null`_ | `NullActionGateway` (unchanged) | `"deterministic"` | degrade-clean fallback |

Selection precedence (first match wins): `gateway` → `operator` → `live` → `null`. A mode whose
credential is absent (`gateway` without a key) falls through to `null` (degrade-clean, never raises).

**Honesty (no change needed — already correct).** `routers/ai.py::explain` stamps
`source:"ai"` iff `gw` is not `NullActionGateway` **and** `text != _deterministic_explain(...)`.
- `VercelAIGateway` returns model text ≠ deterministic → `source:"ai"` → ✨. On error/timeout it
  degrades to the byte-identical `_deterministic_explain` → text == fallback → `source:"deterministic"`,
  **no false ✨**.
- `OperatorActionGateway` returns recorded text ≠ deterministic → `source:"ai"` → ✨ (the recording
  **is** genuinely AI-authored — by me). An unrecorded input → deterministic fallback → no ✨.

So flipping `operator`→`gateway` lights up the same surfaces with zero FE/handler edits, and ✨
never lies in either mode. (`propose`/`apply` already stamp `provenance.model_id` from
`gateway.model_id`, so the audit log records exactly which actor proposed — `meta/llama-3.3-70b`,
`operator`, or `null`.)

## A — `VercelAIGateway` (new, `ai/live/vercel_gateway.py`)

A thin port of eamos `app/services/ai_gateway/engine.py::AIGatewayEngine`, adapted to the
`ActionGateway` Protocol (`model_id` / `propose` / `explain`). OpenAI-compatible httpx client:

- `POST {base_url}/chat/completions`, `Authorization: Bearer {api_key}`,
  body `{model, messages, temperature, max_tokens, providerOptions:{gateway:{order:[…]}}}`.
- Retry on `{429,500,502,503,504}` with backoff + `Retry-After`; raise `GatewayError` on other 4xx.
- **`explain(request_type, data, goal)`** — system prompt = "explain/suggest from ONLY the
  structured data; never fabricate values; ≤120 words" (reuse the `PydanticAIGateway._explain_inner`
  prompt shape). Returns the completion text. Degrade-clean: any error → `_deterministic_explain`.
- **`propose(context, goal)`** — system prompt = the existing `_SYSTEM_PROMPT` (closed action
  vocabulary) + "Return ONLY JSON `{actions:[{type,target,payload,rationale}], notes}`." Parse the
  JSON, validate through the **existing `ProposedPlan` pydantic model** (reuses its `ActionType`
  Literal guard), map via `PydanticAIGateway._map_plan`. Degrade-clean: parse/validate/API error →
  empty `ActionPlan` (Null semantics). (Use OpenAI `response_format:{type:"json_object"}` when the
  chosen model supports it; otherwise rely on the JSON-only instruction + the `ProposedPlan` guard —
  the S1 spine re-validates every action regardless, so a malformed action can never execute.)
- `model_id` property → `settings.ai_gateway_model` (stamped into provenance).
- **Bounded prompt** — reuse `_build_prompt`'s discipline: param_spec names/constraints only, figure
  *shape* only (never plotted data arrays cross the wire).

Module is import-safe with no network; all network behind method calls. Mirrors the lazy/degrade
discipline of `PydanticAIGateway`.

## B — Operator recordings seam (extend `ai/gateway.py::OperatorActionGateway`)

The class already exists (replay by goal; `record` / `record_explanation`; deterministic fallback).
Two additions, **back-compatible** with the current goal-keyed test usage:

1. **`from_recordings(path: str | None) -> OperatorActionGateway`** classmethod — load a JSON file
   into `_explanations` (and optionally `_plans`). Missing/empty path or unreadable file → an empty
   operator (degrade-clean; behaves as Null until something is recorded). File schema:
   ```jsonc
   { "explanations": [
       { "request_type": "explain_score", "key": "rpgrip1", "text": "…AI-authored prose…" },
       { "request_type": "propose_sweep", "key": "deg",      "text": "…" } ],
     "plans": [] }   // plans optional; [] today
   ```
2. **Per-input keying** (the memory wrinkle — explain/propose_sweep vary by *input*, not `goal`).
   `explain` computes candidate lookup keys from `(request_type, data)` and returns the first hit,
   else the deterministic fallback:
   - `explain_score` → input key = `data["scorecard"].get("paper_id")` (the showcase slug;
     `rpgrip1` / `jev` / `hani`).
   - `propose_sweep` → input key = `data["sweep_space"].get("_skill_id")` or the caller's `skill_id`
     (passed via `goal` today; see FE note).
   - Candidate order: `f"{request_type}:{input_key}"` (recordings-file form), then the legacy
     `f"{request_type}:{goal}"` (the existing `record_explanation` test path). Both resolve; nothing
     breaks. `propose` keeps its goal-keyed lookup (unchanged).

   _Why input-keyed, not goal-keyed:_ the FE sends the same `goal` (or none) for every paper's
   "Explain this score"; only the `scorecard` differs. Keying on `paper_id` lets one recordings file
   light up each showcase paper distinctly.

## C — Selection wiring (`routers/ai.py::get_action_gateway`)

```python
mode = settings.ai_gateway.strip().lower()
if mode == "gateway" and settings.ai_gateway_api_key:
    from ai.live.vercel_gateway import VercelAIGateway
    return VercelAIGateway.from_settings(settings)        # reads key/model/order/caps
if mode == "operator":
    from ai.gateway import OperatorActionGateway
    return OperatorActionGateway.from_recordings(settings.ai_operator_recordings_path)
if mode == "live" and os.environ.get("ANTHROPIC_API_KEY"):
    from ai.live.pydantic_gateway import PydanticAIGateway
    return PydanticAIGateway(token_budget=settings.ai_token_budget, timeout_s=settings.ai_timeout_s)
return NullActionGateway()
```

## D — Config additions (`config.py`, mirror eamos field names)

```
ai_gateway: str  = "null"   # null | operator | gateway | live   (existing; widen the comment)
ai_gateway_api_key: str | None = None                 # AI_GATEWAY_API_KEY  (the new separate vck_ key)
ai_gateway_base_url: str = "https://ai-gateway.vercel.sh/v1"     # SELOM_AI_GATEWAY_BASE_URL
ai_gateway_model: str = "meta/llama-3.3-70b"          # SELOM_AI_GATEWAY_MODEL
ai_gateway_provider_order_raw: str = "groq,bedrock"   # SELOM_AI_GATEWAY_PROVIDER_ORDER
ai_gateway_temperature: float = 0.3
ai_gateway_max_tokens: int = 700
ai_operator_recordings_path: str | None = None        # SELOM_AI_OPERATOR_RECORDINGS (default = the bundled file)
```
Reuse the existing `ai_token_budget` / `ai_timeout_s`. `AI_GATEWAY_API_KEY` is the **bare** env name
(matches eamos) so the same shell/Render var name works; everything else is `SELOM_`-prefixed.

## E — Demo/product split (owner strategy, 2026-06-30) + spend protection

**There is no public/free access to the real product** (owner, 2026-06-30): no open free tier — a
**cheap basic tier**, with **promo-code beta gating** for targeted/free access. Prospects "try Selom"
via a **pseudo demo page** (deferred UI; no landing/hero yet) that runs **canned examples smoothly,
decoupled from the real backend** — a promo/branding surface, not the real product. [[selom-pricing-demo-strategy]]

This maps cleanly onto the two gateway modes (the operator path is promoted from "build stand-in" to
**the demo engine**):

| Surface | Gateway | Why |
|---|---|---|
| **Pseudo demo page** (the 3 papers; deferred UI) | **`operator`** (recorded) | canned, deterministic, **zero credit**, decoupled from real compute — always "wows", never fails |
| **Real product** (gated, paid, promo-beta) | **`gateway`** (live Llama) | real AI on real user data |

So **no anonymous spend exists** — the demo is canned by design. Remaining spend protection for the
**gated** live path:

- **Per-request token cap** — already enforced (`ai_gateway_max_tokens` + the bounded prompt).
- **Optional global daily cap** — port eamos's `ai_chat_dev_daily_cap_*` as
  `SELOM_AI_GATEWAY_DAILY_CAP*` (default OFF). **Deferred** to the production-exposure / billing
  launch-gate (not needed for build/verify); noted here so it isn't forgotten.

The demo page UI itself (scripted "watch it run" beat + "Request access" CTA) is **deferred** with the
landing/hero. This build delivers the *engine* (operator recordings for the 3 papers + the live
gateway); the demo UI assembles on top later.

## F — FE touch (small)

- `lib/ai/explain-inputs.ts::buildScorecardPayload` — add `paper_id` (from `ledger.scorecard.paper_id`
  / the ledger slug) to the payload so the operator can key on it. Backend `ExplainRequest.scorecard`
  is already a free `dict`; no schema change. The live gateway ignores `paper_id` (it reads the real
  scorecard fields); only the operator uses it.
- No other FE change — the explain/sweep surfaces (shipped in `a7d477c`) drive entirely off the
  response `source`, so they light up with zero edits when the gateway is on.

## G — Recordings file + the 3 showcase papers

Ship `ai/recordings/explain.json` (bundled; `ai_operator_recordings_path` defaults to it) with an
`explain_score` entry for **`rpgrip1` / `jev` / `hani`** — grounded prose I author from each ledger's
real scorecard (score/tier/confidence/findings). Optionally a `propose_sweep` entry for the common
`deg` sweep. Authoring stays grounded (never fabricates values beyond the scorecard) so it reads
identically to what the live gateway would produce. The demo: `SELOM_AI_GATEWAY=operator` → the 3
showcase papers' "Explain this score" → ✨AI, **zero credit**.

## H — Provider-agnostic launch swap (the owner's requirement)

The Vercel gateway **is** the provider-agnostic layer: swapping `meta/llama-3.3-70b` →
`openai/gpt-4o` → `anthropic/claude-…` → `google/…` → `mistral/…` is a **one-string change** to
`ai_gateway_model` (+ provider order), same endpoint, same key, **zero feature-code change**. Nothing
in Selom is Anthropic-locked (the `PydanticAIGateway` Anthropic path stays only as the optional `live`
mode). Using Claude as the build-time operator stand-in locks nothing.

## Test plan

- **BE** (`tests/test_ai_gateway_vercel.py`, new): `VercelAIGateway.explain` / `.propose` with a
  **stubbed httpx transport** (no network) — happy path returns parsed text / validated plan;
  malformed JSON / API error / timeout → degrade-clean (deterministic text / empty plan); retry on
  429; `model_id` == the configured model; the bounded prompt never includes plotted data arrays.
- **BE** (extend `tests/test_ai_s4.py` Part C): `OperatorActionGateway.from_recordings` loads the
  file; `explain_score` keyed by `paper_id` returns the recorded text for each of the 3 papers and
  the deterministic fallback for an unknown paper; legacy goal-keyed `record_explanation` still
  resolves; the not-a-mutation / no-gap invariants hold; the recordings file parses + every entry has
  a non-empty `request_type`/`key`/`text`.
- **BE** (`tests/test_ai_*` selection): `get_action_gateway()` returns the right class per
  `SELOM_AI_GATEWAY` value + credential presence (incl. `gateway` without a key → Null).
- **FE** (`lib/ai/explain-inputs.test.ts`): `buildScorecardPayload` carries `paper_id`.
- **Source-labelling** — covered by the existing `routers/ai.py::explain` tests (operator recorded →
  `source:"ai"`; operator unrecorded → `"deterministic"`; no new logic).

## Verify (real, [[full-app-smoke-test-before-handoff]] · [[verify-on-real-data-not-mock]])

1. **Operator (no spend):** `SELOM_AI_GATEWAY=operator` + uvicorn on a non-`:8000` port → curl
   `/ai/explain` `explain_score` for each showcase scorecard → recorded text, `source:"ai"`; unknown
   paper → deterministic, `source:"deterministic"`. In-browser: the 3 `/reproduction/<slug>` pages'
   "Explain this score" → ✨AI.
2. **Live gateway (minimal spend):** `SELOM_AI_GATEWAY=gateway AI_GATEWAY_API_KEY=<new vck_ key>` →
   curl `/ai/explain` for one showcase paper → **real Llama** prose, `source:"ai"`, grounded in the
   scorecard; one `propose_sweep`; confirm degrade-clean by pointing at a bad key → `source:"deterministic"`,
   no raise. Keep live calls to a handful (cost discipline).

## Out of scope / deferred

- Cross-stage AI entry points (`s5-followups` #0) — the gateway powers them; the FE composers are a
  separate Prism/pillars decision.
- The global daily spend-cap (E) — wire at production-exposure, not build.
- `propose`/`apply` live-gateway *prose* polish + the sweep live-AI prose line (`s5-followups` #10).
- **Live `explain` prompt tightening** — observed at verify: Llama 3.3 70B grounds in the passed
  numbers but paraphrases loosely (read `panel_count` as "reviewers"). Acceptable for the
  authenticated real-product path (the user has context) and the high-quality demo prose is the
  operator recordings; tighten the explain system prompt (label each field, forbid re-interpreting
  `panel_count`) when polishing the live path.
- Provenance stamping chokepoint ([[selom-provenance-stamping-chokepoint]]) — independent pre-launch gate.

## review-gauntlet (2026-06-30) — 2 low findings, both fixed in this commit

1. **LLM model-license launch gate** — added a `meta/llama-3.3-70b` "Built with Llama" attribution
   line to `LAUNCH-GATES.md` §1 (arms-length use → no GPL/AGPL on the Python path, but the model's
   own license binds at public-serve; verify the shipping model's terms at launch).
2. **Demo-recordings drift guard** — the operator serves recorded prose verbatim (ignoring the passed
   scorecard numbers), so a fixture edit could make the ✨AI text contradict the displayed score. New
   FE guard `lib/ai/demo-recordings-parity.test.ts` ties each recording's headline numbers
   (reproducibility + confidence) to `REPRO_LEDGERS[slug]`, failing CI on drift.

## Gates

BE fast gate (`pytest -m "not slow"`, the uv-3.12 PY + `PYTHONPATH=.venv/Lib/site-packages`
[[selom-backend-python-exec]]) + ruff; FE tsc + eslint + vitest. Review: **review-gauntlet**
(correctness) + **fe-review** (the `buildScorecardPayload` FE touch). Dep: the gateway client uses
**httpx** (already a backend dep) — **no `uv sync`/new install** [[selom-uv-sync-footgun]]. Commit:
named paths, no AI sign-off, owner pushes.
