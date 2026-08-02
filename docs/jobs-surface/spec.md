# Job status surface — the reader half of the async job pipeline

Closes reachability waivers **R-02** (five routes: the async job API had no FE consumer at all) and
**R-06** (the reproduction progress stream had no consumer). Built 2026-08-03.

This is deliberately the **reader**. `OH-01` (arq + Redis job store) is the *producer* and ships
after it: shipping the store first would ship it with no consumer, which is exactly the trap R-02
records. So everything here is built against the job contract **as it stands today**, and §4 states
what the producer has to meet.

---

## 1. The problem, stated honestly

Two separate things were true, and only one of them was a wiring gap:

1. **Nothing in the frontend read a job.** `GET /jobs/{id}`, `/jobs/{id}/events`,
   `/jobs/{id}/result`, `POST /skills/{id}/jobs` and `/skills/{id}/jobs-dataset` all answered, and
   no FE surface called any of them. A long skill run showed the user nothing but a disabled
   button.
2. **The default queue mode cannot produce progress anyway.** `SELOM_QUEUE=inline` (the default,
   `app/backend/config.py`) runs the job to completion *inside the submit request*. The same is
   true of a reproduction drive. So the server has no job id to hand out until the work is already
   over — there is no server-side progress to poll while the user waits.

(2) is why this surface is built on a **client-side activity record** that a server handle is bound
*onto*, rather than on a server query. The record exists from the instant the user clicks Run — the
only moment that is true today — and the follower streams real server transitions onto it the
moment the queue moves off-request. Nothing in the FE changes when that happens.

---

## 2. The shape, and what was ruled OUT

Mobbin consulted first (`search_flows`, "a long-running background job showing progress and a
completion state", web). It is a comparison instrument, so the useful output is mostly the
rejections.

**Adopted — [FLORA · View tasks](https://mobbin.com/flows/f654a845-0d97-4d1b-b301-ac4bc358e68c).**
A collapsed bottom-right pill carrying a live count, expanding to a list of rows, each with its own
state, and terminal rows that stay listed until cleared. It is the closest analogue: a canvas tool
where the long job is a side-effect of the work you are already looking at.

**REJECTED — Drive's always-expanded bottom-right progress card.** Adopt its anchoring, collapse
and dismiss; reject *expanded by default*. Drive's card is sized for many concurrent file uploads
with a row each. Selom's normal case is exactly **one** run at a time — `useFigureRun` holds a
single `running` skill id and the launch controls disable while it is set — so an always-expanded
multi-row panel would sit mostly empty on top of a figure canvas. One line of text is the whole
story here.

**REJECTED — FLORA's "3 seconds remaining" countdown.** This is the most important rejection and it
came directly from reading the contract next to the screen. FLORA can predict its generation time;
Selom cannot — a UMAP on 60k cells has no honest estimate — and more decisively, **the job wire
shape carries nothing to build one from**: `Job.public()` is `{id, skill_id, status, result_url,
error, created_at, updated_at}`. No percentage, no step count, no ETA. A countdown would be
fabricated data ([[mock-fallback-never-fabricates-data]]). **Adopted instead: elapsed time counting
up**, which is true, plus the reproduction stream's server-authored `progress` line shown verbatim
where one exists.

**REJECTED — [Customer.io · Task list](https://mobbin.com/flows/b7830ca7-d10e-43a8-ba9e-c4a233ffd790)**
(header notification tray + a full Tasks page with TASK/DETAIL/UPDATED/STATUS and expandable
timing rows). It is built on a durable server-side task history. Selom's default job store is an
**in-process dict** (`jobs/store.py` `JobStore`), so a Tasks page would be empty after any restart
and blank on a second browser tab — a surface that looks like history and is not.
**Precondition, not a no:** revisit once `SELOM_JOB_STORE=sql` or the OH-01 Redis store is the
default and job rows outlive the process.

**REJECTED — [Wellfound · Applications](https://mobbin.com/flows/d3bf1b51-18cf-47ef-b681-9681151a7139)**
(a destination page listing submitted things with "Pending · less than a minute ago"). A run's
payoff in Selom is the **figure**, which already has a durable home in the project's figure list. A
second list of "runs" would be a parallel index of the same objects.

**REJECTED — [Basecamp · Updating progress](https://mobbin.com/flows/03cb0aea-d7e1-42a1-9bb6-789cc436d900).**
Wrong genre entirely: human-authored status ("How far along are we?"), not machine progress.

**REJECTED (for this lane) — [Laravel Cloud · Adding a background process](https://mobbin.com/flows/b20af9b9-8513-4d0b-afb8-f745f1be7988)**
(queue-worker config: connection, `--timeout`, `--tries`, process count). That is the *producer's*
admin surface — OH-01's territory if anyone's — and exposing worker tuning to a bench scientist is
off-product.

### Resulting rules

- Mounted **once in the app shell**, beside `<UndoToast/>`. Inline progress at the launch point
  would be unmounted mid-flight: a finished reproduction pushes to `?stage=score`, a finished skill
  run swaps the workspace view.
- **Collapsed pill by default**, expanding to the list.
- **Elapsed counts up. No percentage, no ETA, ever.**
- A finished run stays visible. **Successes auto-clear after 6s** (the figure is the real
  confirmation); **failures never auto-clear** — an error nobody saw was not reported.
- The live region announces the **summary only**, never the ticking clock.

---

## 3. What was built

| File | Role |
|---|---|
| `lib/jobs/activity.ts` | The activity store. External store (the `lib/workspace/undo.ts` pattern), read via `useSyncExternalStore`. |
| `lib/jobs/sse.ts` | `followRun` — a **fetch-based** SSE reader with a polling floor. |
| `lib/jobs/api.ts` | The job contract: submit (both routes), status, events URL, result. |
| `lib/jobs/run-skill.ts` | The tracked run wrappers + the heavy-lane hand-off. |
| `lib/reproduction/progress.ts` | The consumer for `GET /reproduction-runs/{id}/events` (R-06). |
| `components/jobs/activity-dock.tsx` | The dock. |

### Why `fetch` and not `EventSource`

Three reasons, all load-bearing:

1. **Auth.** `EventSource` cannot set request headers, so it can never carry the
   `Authorization: Bearer` the backend's `clerk` auth mode requires (`auth/context.py`). Every
   subscription would 401 the moment P-E turns real auth on. Today's `dev` mode needs no header, so
   an `EventSource` would have worked *until* auth landed and then broken silently.
2. **`event: error` is ambiguous under `EventSource`.** `routers/jobs.py` emits a real
   `event: error` frame for an unknown job, but `EventSource` delivers *transport* failures on that
   same listener. Here they are different code paths — `RunGoneError` vs. degrade-to-polling.
3. **Reconnect.** `EventSource` auto-reconnects when the server closes the stream, which is exactly
   what both streams do on reaching terminal — it would restart the server-side poll loop forever.

It is also the only version that is testable: `EventSource` does not exist in the vitest node
environment.

### Why there is a polling floor

Both streams cap themselves at ~5 minutes (600 ticks × 0.5s) and then simply stop emitting. A
reader that trusted the stream alone would leave a long run pinned at "running" forever. The stream
is the fast path; `GET /jobs/{id}` / `GET /reproduction-runs/{id}` is the floor.

### The heavy lane

The synchronous run path is killed at `SELOM_SKILL_TIMEOUT_S` — **120s by default** — and answers
504 `skill_timeout` with "try a smaller input or a lighter analysis". For a real scRNA integration
or a pyDESeq2 contrast that is a dead end today. The async job path runs under **no timeout at
all**, and `routers/skills.py` says so in as many words ("Heavy skills should use POST
/skills/{id}/jobs"). So `runSkillTracked` resubmits a timed-out run to the job lane and follows it
to completion.

This is safe precisely because it happens **after** the synchronous attempt already passed every
pre-run gate — QC, the D1 data contract, D2 frame validation all ran and let the run through, and
only the clock stopped it. The hand-off therefore trades three read-only panels (§4) for a figure
the user would otherwise not get at all. It is a fallback, never the default path: an ordinary run
still goes through `/run` and keeps its full bundle.

`parseSkillRunResponse` now stamps the taxonomy code (`detail.error`) onto the thrown `Error`, so
this branches on `skill_timeout` rather than pattern-matching a user-facing sentence.

The AI-assisted path (`/ai/apply`) is tracked but has **no** heavy lane: the job routes carry no AI
actions, so falling back would produce a figure with no `provenance.actions[]` — silently stripping
the AI attribution the chokepoint exists to stamp.

---

## 4. The contract `OH-01` has to meet

Both are real gaps found by building the reader. Neither is fixable from this lane
(`jobs/queue.py` is outside its glob).

**4.1 — The job bundle is a strict subset of the `/run` bundle.** `execute_job` stores
`{figure, provenance, methods, guardrails, table}`. `_execute_skill_run` returns those **plus**
`figure_legend`, `data_check` (the is-my-data-clean verdict + cleaning plan) and `data_fit`, and it
runs the QC / D1 / D2 gates first. Every extra field is optional in `SkillRunResponse`, so the
figure renders and the extra panels simply have nothing to show — acceptable for a
post-timeout fallback, **not** acceptable if the job path is ever made the primary run path.
**OH-01 should route the worker through `_execute_skill_run`** (or hoist its body) so the two
cannot drift, exactly as `run` and `run-dataset` already share it.

**4.2 — `Job.public()` carries no progress.** No percentage, no step, no message. The dock can only
show elapsed time for a skill job, while a reproduction run — whose payload *does* carry a
`progress` string — gets a real line. Adding a `progress: str` field to `Job.public()` is enough;
`lib/jobs/api.ts` and the dock already have the slot for it (`Activity.detail`), so it becomes
visible with no FE change.

**4.3 — SSE and bearer auth.** When P-E turns on `auth_mode=clerk`, the job stream needs the
`Authorization` header. The reader is `fetch`-based so it *can* send one, but
`lib/api/client.ts` (frozen this sprint) exposes only `setAuthHeader` and no getter, so
`lib/jobs/sse.ts` cannot read the configured header. **P-E should export a `getAuthHeader()`** and
this module should pass it into `followRun`. Until then the stream will 401 under clerk mode and
the polling floor will too. This is a P-E task, not an OH-01 one.

---

## 5. Verification

- `bash scripts/verify.sh --fast`, run raw. `fe-build` and browser checks are train-only
  (Turbopack cannot run in a worktree).
- 46 unit tests across `lib/jobs/*.test.ts` and `lib/reproduction/progress.test.ts`, covering frame
  parsing, chunk-split payloads, the stream→poll degradation, the ~5-minute ceiling, `RunGoneError`,
  the timeout→job-lane hand-off on both submit routes, and a failed background job.
- `test_reachability_guard.py` — the R-02 and R-06 waivers are deleted, and its
  `test_no_stale_waivers` half proves the six routes are genuinely reached from real FE source
  (mocks and tests are excluded from that scan by design).
