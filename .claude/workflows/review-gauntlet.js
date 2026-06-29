export const meta = {
  name: 'review-gauntlet',
  description: 'Selom change-review gauntlet — parallel invariant lenses over a diff, each finding adversarially verified before it survives',
  whenToUse: 'Reviewing a diff before commit/PR. Surfaces only confirmed, Selom-invariant breaches.',
  phases: [
    { title: 'Review', detail: 'parallel Selom-specific lenses inspect the change' },
    { title: 'Verify', detail: 'adversarially refute each finding; drop the false positives' },
  ],
}

// What to review. Pass {scope: "commit <sha>" | "the working tree" | "PR #N"} as args. Defensive:
// args may arrive as an object, a JSON string, or a bare scope string — normalise all three.
const _A = (typeof args === 'string')
  ? (() => { try { return JSON.parse(args) } catch { return { scope: args } } })()
  : (args || {})
const SCOPE = _A.scope ? String(_A.scope)
  : 'the uncommitted working-tree changes; if the tree is clean, the latest commit (HEAD)'

const GIT = 'git -C "D:/selom"'

// Lenses are defined INLINE here, on purpose: the .claude/agents registry only loads at SESSION
// START, so a workflow that depends on a freshly-added custom agentType can't run in the same
// session (dogfood lesson 2026-06-29). Inlining the briefs + using the default agent makes the
// gauntlet runnable in ANY session via scriptPath — no dependency on registration timing.
const LENSES = [
  {
    key: 'repro-integrity',
    brief:
      'Selom is a multi-omics figure-REPRODUCTION product; results must be honestly, ' +
      'deterministically reproducible. Flag: AI on the score\'s critical path (AI may SUGGEST, ' +
      'never BE a recorded value — re-running from recorded params/provenance must reproduce the ' +
      'figure with zero AI in the loop, "AI compiles away"); an AI-driven change not actor-tagged ' +
      'in the provenance bundle; conflating the reproducibility axis with the Selom-confidence ' +
      'axis (keep them separate); digitized / non-engine-computed numbers feeding the score ' +
      '(digitize != reproduce); silent filters/caps instead of honest verdicts ' +
      '(data_unmatched/needs_recipe/run_failed); a printed-vs-computed golden mismatch hidden ' +
      'under "pass".',
  },
  {
    key: 'spine-consistency',
    brief:
      'Architecture = ONE shared deterministic engine spine; bespoke surfaces ride it as DECLARED ' +
      'plug-ins, and generic code reads declared flags/registries, never branches on an ' +
      'instance/skill id. Flag: a PARALLEL VALIDATION PATH (new logic instead of reusing ' +
      'skills.contract.validate_param_ranges / engine.frame_schema.check_skill_input / ' +
      'engine.compat.fit); `if skill_id == ...` branching instead of a registry + thin plug-in; ' +
      'package drift (route handlers outside routers/<domain>.py — main.py only include_router; a ' +
      'flat reproduction_*.py vs reproduction/; a flat methods/legends/provenance/guardrails.py vs ' +
      'companions/; a new src/; FE flat lib/*-api.ts, a barrel index.ts, a heavy/WebGL import not ' +
      'behind dynamic(ssr:false)); a refactor that breaks a frozen external contract instead of ' +
      'freezing it; a guardrail that raises and breaks a previously-valid run instead of failing ' +
      'soft; a new convention/boundary with no guard test that fails when it drifts.',
  },
  {
    key: 'license',
    brief:
      'Commercial SaaS — license is a hard gate; verify the CURRENT license of any newly-used dep ' +
      'at decision time, don\'t assume. Flag: AGPL on ANY path (network clause blocks SaaS — ' +
      'PyMuPDF/fitz, eggNOG, RAxML-NG, ASTER; OmicVerse is GPL-3) → use a license-clean alt ' +
      '(pypdf/BSD); GPL on the SHIPPED path (a GPL CLI run arms-length as a separate process = ' +
      'mere aggregation, OK, don\'t bundle; the Harmony lineage is GPL-3 → use clean-room Melody, ' +
      'don\'t read the GPL repo); DATA-license gates (MSigDB commercial, ARCHS4 non-commercial) → ' +
      'tag with a commercial-restriction marker or use GO/Reactome; missing attribution or a false ' +
      'clean-room claim.',
  },
  {
    key: 'design',
    brief:
      'FE only (Next.js + React + Plotly), Selom is DESKTOP-ONLY. If the diff is backend-only, ' +
      'return an EMPTY findings list. Flag: generic "AI slop" aesthetic / weak hierarchy / default ' +
      'spacing / low contrast; figure-edit UX violations (cosmetic = LIVE client-side; ' +
      'data-recompute = STAGED behind ONE explicit re-run with a prominent TOP "pending changes" ' +
      'banner, not per-control chips; colour axes amber=data / cyan=styling / violet star=AI, ' +
      'orthogonal; never colour-only); needless mobile/responsive complexity; accessibility ' +
      '(colour-only signalling, missing labels/focus states); icon drift (prefer Phosphor).',
  },
]

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
          detail: { type: 'string', description: 'the invariant breached + the evidence' },
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
    real: { type: 'boolean', description: 'true ONLY if the breach is concrete and survives an honest refutation' },
    reason: { type: 'string' },
  },
}

log(`review-gauntlet over: ${SCOPE}`)

// Pipeline (no barrier): a lens's findings start verifying the moment that lens returns.
phase('Review')
const reviewed = await pipeline(
  LENSES,
  (L) => agent(
    `You are the ${L.key} review lens for Selom. ${L.brief}\n\n` +
    `Review ONLY this change scope: ${SCOPE}. Inspect the ACTUAL code with ${GIT} ` +
    `(e.g. \`${GIT} show <sha>\` for a commit, or \`${GIT} diff HEAD\` for the working tree), ` +
    `plus Read/Grep for context. Return findings — an EMPTY list if nothing falls in YOUR lens. ` +
    `Be specific: file:line, the invariant breached, severity, the concrete fix. Do NOT edit anything.`,
    { label: `review:${L.key}`, phase: 'Review', schema: FINDINGS_SCHEMA },
  ),
  (review, L) => parallel(
    (((review && review.findings) || [])).map((f) => () =>
      agent(
        `Adversarially verify this ${L.key} finding — TRY TO REFUTE it. Read the actual code at ` +
        `${f.file} with ${GIT}. Default real=false unless the breach is concrete and the code truly ` +
        `does it. Finding: ${JSON.stringify(f)}`,
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
log(`confirmed ${confirmed.length} / ${all.length} raw findings`)
return { confirmed, dropped: all.length - confirmed.length, scope: SCOPE }
