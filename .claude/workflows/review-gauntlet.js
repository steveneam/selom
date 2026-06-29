export const meta = {
  name: 'review-gauntlet',
  description: 'Selom change-review gauntlet — parallel invariant lenses over a diff, each finding adversarially verified before it survives',
  whenToUse: 'Reviewing a diff before commit/PR. Surfaces only confirmed, Selom-invariant breaches.',
  phases: [
    { title: 'Review', detail: 'parallel Selom-specific lenses inspect the change' },
    { title: 'Verify', detail: 'adversarially refute each finding; drop the false positives' },
  ],
}

// Scope to review. Pass {scope: "..."} as args to target a commit range / PR; default = working tree.
const SCOPE = (args && args.scope)
  ? args.scope
  : 'the uncommitted working-tree changes (run: git -C "D:/selom" diff HEAD). If the tree is clean, review the latest commit (git -C "D:/selom" show HEAD).'

// Each lens is a declared custom subagent in .claude/agents/. Generic orchestration here — the
// lens-specific knowledge lives in the agent definition (the plug-in over the shared spine).
const LENSES = [
  { key: 'repro-integrity', agentType: 'repro-integrity-lens' },
  { key: 'spine-consistency', agentType: 'spine-consistency-lens' },
  { key: 'license', agentType: 'license-lens' },
  { key: 'design', agentType: 'design-lens' },
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

// Pipeline (no barrier): a lens's findings start verifying the moment that lens returns —
// the license lens doesn't wait for the slower spine-consistency lens.
phase('Review')
const reviewed = await pipeline(
  LENSES,
  (L) => agent(
    `You are the ${L.key} lens. Review ${SCOPE} through ONLY your lens. ` +
    `Use git (Bash), Read, and Grep to inspect the actual code. Return findings (an EMPTY list if ` +
    `nothing falls in your lens). Be specific: file:line, the invariant breached, severity, the fix.`,
    { label: `review:${L.key}`, phase: 'Review', agentType: L.agentType, schema: FINDINGS_SCHEMA },
  ),
  (review, L) => parallel(
    (((review && review.findings) || [])).map((f) => () =>
      agent(
        `Adversarially verify this ${L.key} finding — TRY TO REFUTE it. Read the actual code at ` +
        `${f.file}. Default real=false unless the breach is concrete and the code truly does it. ` +
        `Finding: ${JSON.stringify(f)}`,
        { label: `verify:${L.key}`, phase: 'Verify', schema: VERDICT_SCHEMA },
      ).then((v) => ({ ...f, lens: L.key, verdict: v })),
    ),
  ),
)

const all = reviewed.flat().filter(Boolean)
const confirmed = all
  .filter((f) => f.verdict && f.verdict.real)
  .sort((a, b) => ['blocker', 'high', 'medium', 'low'].indexOf(a.severity) - ['blocker', 'high', 'medium', 'low'].indexOf(b.severity))
log(`confirmed ${confirmed.length} / ${all.length} raw findings`)
return { confirmed, dropped: all.length - confirmed.length, scope: SCOPE }
