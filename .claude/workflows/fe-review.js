export const meta = {
  name: 'fe-review',
  description: 'Selom FE-interaction review — the front-end peer of review-gauntlet: a user-task walkthrough, the V·R·D·A·R·N mutation-lifecycle lens fanned out + adversarially verified, and a rendered-in-context gate',
  whenToUse: 'Reviewing an FE diff before commit. The interaction/layout/affordance axis (gauntlet covers correctness/invariants). Surfaces missing affordances + confirmed interaction breaches.',
  phases: [
    { title: 'Tasks', detail: 'G1 — user-task walkthrough; mark which JTBD have an affordance vs a gap' },
    { title: 'Review', detail: 'V·R·D·A·R·N lenses inspect the change in parallel' },
    { title: 'Verify', detail: 'adversarially refute each finding; drop false positives' },
    { title: 'Render', detail: 'G2 — rendered-in-context at real widths (or emit the required inline gate)' },
  ],
}

// What to review. Pass {scope: "commit <sha>" | "the working tree" | "PR #N"} as args. Defensive:
// args may arrive as an object, a JSON string, or a bare scope string — normalise all three (same
// shape as review-gauntlet.js).
const _A = (typeof args === 'string')
  ? (() => { try { return JSON.parse(args) } catch { return { scope: args } } })()
  : (args || {})
const SCOPE = _A.scope ? String(_A.scope)
  : 'the uncommitted working-tree changes; if the tree is clean, the latest commit (HEAD)'

// Run git from the workflow's cwd (the repo root) — no hardcoded checkout path.
const GIT = 'git'

// Selom grounding shared by every lens prompt — keep the checks specific to OUR system, not generic.
const SELOM = (
  'Selom = a no-code multi-omics figure SaaS, Next.js + React + Plotly, DESKTOP-ONLY (verify at ' +
  'desktop widths only). Design system: stage tokens in app/frontend/app/globals.css — ' +
  '--stage-figuredata (amber, the figure-data / "pending changes" axis) · --stage-figure (cyan) · ' +
  '--stage-skill (violet) · --stage-ai (fuchsia, AI attribution) · --stage-data (blue) · ' +
  '--stage-publish (green); the TintChip tinted-pill vocabulary (color-mix 12% surface / 40% ' +
  'border / 80% text over --foreground). Fixed 360px right docks (the figure-data dock, the AI ' +
  'panel). Figure-edit UX: cosmetic = LIVE client-side; data-recompute = STAGED behind ONE explicit ' +
  're-run with a prominent TOP "pending changes" banner. Provenance model: a committed run records ' +
  'provenance.params (the resolved config) + provenance.actions[] (actor-tagged AI) via the one ' +
  'gated _execute_skill_run — "AI compiles away" (re-run from params with no gateway reproduces it).'
)

// The V·R·D·A·R·N mutation-lifecycle lens. Each letter maps 1:1 to a real interaction gap the static
// audit missed (AI-Helpers S5, 2026-06-30). Each lens names the impeccable MODE to reason in.
const LENSES = [
  {
    key: 'V-visible',
    brief:
      'VISIBLE (impeccable critique). Every user- or AI-initiated state change must have a visible ' +
      'cue AT the control, not only in a banner. Flag: a changed input with no highlight (a touched ' +
      'figure-data control should ring/tint — amber --stage-figuredata for a user edit, fuchsia ' +
      '--stage-ai for an accepted AI value); a staged change invisible until you open a panel; a ' +
      '"pending" state with no surfaced count. (S5 miss: changed-control highlight was absent.)',
  },
  {
    key: 'R-reversible',
    brief:
      'REVERSIBLE (impeccable critique). The user can undo every change. Flag: a staged edit with no ' +
      'path back to base — no per-change revert AND no global "Reset to previous values"; a revert ' +
      'that does not decrement/clear the pending state; an accepted AI proposal with no un-accept. ' +
      '(S5 miss: no Reset-to-previous affordance existed.)',
  },
  {
    key: 'D-discoverable',
    brief:
      'DISCOVERABLE (impeccable critique). Interactive controls must LOOK interactive. Flag: a ' +
      'clickable row/header with no hover state + no cursor affordance (reads as static → "doesn\'t ' +
      'do anything"); an icon-only control with no tooltip/label; a disclosure/toggle whose state is ' +
      'ambiguous. (S5 miss: the data-check header toggled but had no hover, so it read as dead.)',
  },
  {
    key: 'A-attributable',
    brief:
      'ATTRIBUTABLE (impeccable audit + critique). A change must say WHO made it, never by colour ' +
      'alone. Flag: an AI-touched control/row without the ✨ --stage-ai marker; attribution carried ' +
      'by colour with no glyph + text/tooltip (colourblind/SR unsafe); provenance detail (model, ' +
      'approved-at) only in a mouse `title` and not the accessible name. (S5: the ✨ marker is the ' +
      'pattern; its aria-label must carry the tag.)',
  },
  {
    key: 'R-recorded',
    brief:
      'RECORDED (impeccable audit + the provenance model). A COMMITTED change must be reproducibly ' +
      'recorded; PRE-COMMIT working state must NOT be persisted. Flag: a committed figure change ' +
      'whose config is not in provenance.params, or an AI-assisted run whose actions are not in ' +
      'provenance.actions[] (must flow through _execute_skill_run); conversely, a transient ' +
      'staged/preview/discard state wrongly written to the backend. (S5: verify the actor-tagged ' +
      'log + params round-trip; pre-commit highlights/Reset/proposals correctly have NO backend.)',
  },
  {
    key: 'N-nonbreaking',
    brief:
      'NON-BREAKING (impeccable critique, rendered-aware). A change must not regress a neighbour. ' +
      'Flag: a new button/label added to a flex row in a fixed 360px dock that crowds neighbouring ' +
      'text into a cramped column (stack instead of squeeze); a fixed-position panel/dock with no ' +
      'content offset that overlays the primary action (reserve its width); a control added without ' +
      'co-located state (label/value) so a row loses meaning. These are often only fully confirmable ' +
      'rendered (G2). (S5 misses: Reset cramped the helper text; the AI panel overlaid Re-run.)',
  },
]

const JTBD_SCHEMA = {
  type: 'object',
  required: ['tasks'],
  properties: {
    tasks: {
      type: 'array',
      items: {
        type: 'object',
        required: ['task', 'affordance', 'status'],
        properties: {
          task: { type: 'string', description: "a user job-to-be-done for this surface" },
          affordance: { type: 'string', description: 'the UI element that serves it, or "—" if none' },
          status: { type: 'string', enum: ['present', 'gap'] },
          note: { type: 'string' },
        },
      },
    },
  },
}

const FINDINGS_SCHEMA = {
  type: 'object',
  required: ['findings'],
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        required: ['title', 'file', 'severity', 'detail', 'fix'],
        properties: {
          title: { type: 'string' },
          file: { type: 'string', description: 'file:line if known' },
          severity: { type: 'string', enum: ['blocker', 'high', 'medium', 'low'] },
          detail: { type: 'string', description: 'the lens check breached + the evidence' },
          fix: { type: 'string' },
        },
      },
    },
  },
}

const VERDICT_SCHEMA = {
  type: 'object',
  required: ['real', 'reason'],
  properties: {
    real: { type: 'boolean', description: 'true ONLY if the gap is concrete and survives honest refutation' },
    reason: { type: 'string' },
  },
}

const RENDER_SCHEMA = {
  type: 'object',
  required: ['server_reachable', 'surfaces', 'gate_note'],
  properties: {
    server_reachable: { type: 'boolean' },
    surfaces: {
      type: 'array',
      items: {
        type: 'object',
        required: ['name', 'verified', 'note'],
        properties: {
          name: { type: 'string' },
          width: { type: 'string' },
          verified: { type: 'boolean' },
          note: { type: 'string' },
          screenshot: { type: 'string' },
        },
      },
    },
    gate_note: { type: 'string', description: 'when not verified, the exact surfaces+widths the main loop must render-check inline' },
  },
}

log(`fe-review over: ${SCOPE}`)

// G1 — user-task walkthrough (the gate that finds MISSING affordances; no audit of existing code can).
phase('Tasks')
const jtbd = await agent(
  `You are the user-task (jobs-to-be-done) lens for an FE review. ${SELOM}\n\n` +
  `For the change scope: ${SCOPE} — inspect the diff with ${GIT} (e.g. \`${GIT} diff HEAD\`) + ` +
  `Read/Grep for the touched surfaces. Enumerate the concrete things a USER wants to do on those ` +
  `surfaces (e.g. "see which input I changed", "undo a change", "reset to previous values", ` +
  `"tell what the AI changed"). For each, name the affordance that serves it, or mark it a GAP if ` +
  `the surface is missing it. Focus on MISSING affordances — the point is to find what should exist ` +
  `but doesn't. Do NOT edit anything.`,
  { label: 'jtbd', phase: 'Tasks', schema: JTBD_SCHEMA },
)
const gaps = ((jtbd && jtbd.tasks) || []).filter((t) => t.status === 'gap')
log(`G1: ${gaps.length} affordance gap(s) of ${((jtbd && jtbd.tasks) || []).length} user tasks`)

// V·R·D·A·R·N — pipeline (no barrier): each lens's findings start verifying the moment it returns.
phase('Review')
const reviewed = await pipeline(
  LENSES,
  (L) => agent(
    `You are the ${L.key} FE-review lens for Selom. ${SELOM}\n\n${L.brief}\n\n` +
    `Review ONLY this change scope: ${SCOPE}. Inspect the ACTUAL code with ${GIT} ` +
    `(\`${GIT} diff HEAD\`, \`${GIT} show <sha>\`) + Read/Grep for context. Return findings — an ` +
    `EMPTY list if nothing falls in YOUR lens. Be specific: file:line, the check breached, severity, ` +
    `the concrete fix. Do NOT edit anything.`,
    { label: `review:${L.key}`, phase: 'Review', schema: FINDINGS_SCHEMA },
  ),
  (review, L) => parallel(
    (((review && review.findings) || [])).map((f) => () =>
      agent(
        `Adversarially verify this ${L.key} FE finding — TRY TO REFUTE it. Read the actual code at ` +
        `${f.file} with ${GIT}. Default real=false unless the gap is concrete and the code truly has ` +
        `it. Finding: ${JSON.stringify(f)}`,
        { label: `verify:${L.key}`, phase: 'Verify', schema: VERDICT_SCHEMA },
      ).then((v) => ({ ...f, lens: L.key, verdict: v })),
    ),
  ),
)

const RANK = ['blocker', 'high', 'medium', 'low']
const all = reviewed.flat().filter(Boolean)
const confirmed = all
  .filter((f) => f.verdict && f.verdict.real)
  .sort((a, b) => RANK.indexOf(a.severity) - RANK.indexOf(b.severity))
log(`V·R·D·A·R·N: confirmed ${confirmed.length} / ${all.length} raw findings`)

// G2 — rendered-in-context: confirm layout/affordance at REAL widths with REAL neighbours. Drives the
// browser when a dev server is reachable; else emits the required inline gate (never silently skipped).
phase('Render')
const render = await agent(
  `You are the rendered-in-context (G2) gate for an FE review. ${SELOM}\n\n` +
  `From the change scope: ${SCOPE}, identify the changed FE SURFACES (e.g. the figure-data dock, the ` +
  `AI panel, the pending-changes banner) and the REAL container widths they live in (the 360px ` +
  `docks, the full workspace). Check whether a Selom dev server is up: try \`curl -s -o /dev/null ` +
  `-w "%{http_code}" http://localhost:3007/\` then :3000. IF reachable, load it via the ` +
  `chrome-devtools tools (find them with ToolSearch "chrome-devtools navigate snapshot screenshot"), ` +
  `open each changed surface at its real width, screenshot it, and confirm: no cramped/overflowing ` +
  `text, no fixed panel overlaying a primary action, the changed-state cues render. IF no server is ` +
  `reachable, set server_reachable=false and return gate_note = the exact list of surfaces + widths ` +
  `the main loop MUST render-verify inline before commit (this gate is mandatory, never skipped). Do ` +
  `NOT edit anything.`,
  { label: 'render-gate', phase: 'Render', schema: RENDER_SCHEMA },
)

return {
  scope: SCOPE,
  jtbd: (jtbd && jtbd.tasks) || [],
  affordance_gaps: gaps,
  confirmed,
  dropped: all.length - confirmed.length,
  render,
}
