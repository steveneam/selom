export const meta = {
  name: 'retro',
  description: 'Selom reflect pipeline — synthesize recently shipped work + the open gap/deferred backlogs into a ranked "what to improve next" and the lessons that should be Ratcheted',
  whenToUse: 'End of a work phase or ~weekly. Surfaces the next spine improvements + uncaptured durable lessons.',
  phases: [
    { title: 'Gather', detail: 'recent commits + CURRENT.md + the gap/deferred backlogs + a documented-command execution pass' },
    { title: 'Synthesize', detail: 'rank the next improvements + flag lessons to capture' },
  ],
}

// Window to reflect over. Pass {window: "the last 30 commits" | "since 2026-06-25"} as args.
// Defensive: args may arrive as an object, a JSON string, or a bare window string.
const _A = (typeof args === 'string')
  ? (() => { try { return JSON.parse(args) } catch { return { window: args } } })()
  : (args || {})
const WINDOW = _A.window ? String(_A.window) : 'the most recent work (≈ the last 25 commits)'
// Run git from the workflow's cwd (the repo root) — no hardcoded checkout path.
const GIT = 'git'

const WORK_SCHEMA = {
  type: 'object',
  required: ['shipped'],
  properties: {
    shipped: {
      type: 'array',
      items: {
        type: 'object', required: ['what'],
        properties: { what: { type: 'string' }, sha: { type: 'string' } },
      },
    },
    in_flight: { type: 'array', items: { type: 'string' } },
    deferred: { type: 'array', items: { type: 'string' } },
  },
}

const BACKLOG_SCHEMA = {
  type: 'object',
  required: ['items'],
  properties: {
    items: {
      type: 'array',
      items: {
        type: 'object', required: ['title', 'source', 'rationale'],
        properties: {
          title: { type: 'string' },
          source: { type: 'string', description: 'the file the item came from' },
          rationale: { type: 'string' },
          kind: { type: 'string', description: 'e.g. skill-gap | deferred-spec | open-question | todo | capability-gap' },
        },
      },
    },
  },
}

// Documented-command execution pass (repo-hygiene ratchet ported from thalon, 2026-07-19): a
// DOCUMENTARY ratchet rots silently. Every retro run EXECUTES the documented commands and flags the
// ones that no longer run — the executable half of the ratchet ladder.
const DOC_COMMANDS_SCHEMA = {
  type: 'object',
  required: ['checked'],
  properties: {
    checked: {
      type: 'array',
      items: {
        type: 'object', required: ['command', 'status'],
        properties: {
          command: { type: 'string' },
          source: { type: 'string', description: 'the doc file the command is documented in' },
          status: { type: 'string', enum: ['ok', 'rotted', 'skipped'] },
          note: { type: 'string', description: 'for rotted/skipped: why (stale path/flag; or has side effects, so not run)' },
        },
      },
    },
  },
}

const RETRO_SCHEMA = {
  type: 'object',
  required: ['ranked_next'],
  properties: {
    ranked_next: {
      type: 'array',
      items: {
        type: 'object', required: ['title', 'leverage', 'why'],
        properties: {
          title: { type: 'string' },
          leverage: { type: 'string', enum: ['high', 'medium', 'low'] },
          why: { type: 'string' },
          source: { type: 'string' },
        },
      },
    },
    lessons_to_capture: {
      type: 'array',
      items: {
        type: 'object', required: ['lesson', 'home'],
        properties: {
          lesson: { type: 'string' },
          home: { type: 'string', description: 'the durable home: test | script | handoff-note | memory-rule | code-boundary' },
        },
      },
    },
    health_notes: { type: 'array', items: { type: 'string' } },
  },
}

log(`retro over: ${WINDOW}`)

phase('Gather')
const [work, backlog, docCommands] = await parallel([
  () => agent(
    `Summarize the Selom work shipped over ${WINDOW}. Use \`${GIT} log --oneline -25\` (and ` +
    `\`${GIT} show --stat <sha>\` for any commit you need detail on) and read ` +
    `agent_handoff/CURRENT.md (the SESSIONS table + the LIVE / NEXT / DEFERRED slots). Return what ` +
    `shipped (with shas), what's in flight, and what's flagged DEFERRED/NEXT.`,
    { label: 'gather:work', phase: 'Gather', schema: WORK_SCHEMA },
  ),
  () => agent(
    `Collect Selom's OPEN backlog of candidate improvements. Read docs/skill-gaps.md (the committed ` +
    `buildable-gap backlog), and grep the specs under docs/ for "DEFERRED", "Open questions", and ` +
    `"TODO". Note: the AI-Helpers CapabilityGap backlog will be a persisted source once S4 lands; ` +
    `for now docs/skill-gaps.md is the committed gap source. Return a deduped list of candidate ` +
    `improvements, each with its source file + a one-line rationale.`,
    { label: 'gather:backlog', phase: 'Gather', schema: BACKLOG_SCHEMA },
  ),
  () => agent(
    `Documented-command execution pass (a repo-hygiene ratchet: a documentary ratchet rots silently — ` +
    `e.g. thalon's "npm run guard" was broken for 3 buckets before anyone ran it). Find the commands ` +
    `DOCUMENTED in Selom's canonical docs — CLAUDE.md + CODEX.md (Development / dev-command sections), ` +
    `README.md quickstart, and the ENV / fast-gate commands — and EXECUTE a representative, ` +
    `SIDE-EFFECT-FREE subset verbatim (lint / typecheck / test-collection / the hygiene guard / a ` +
    `build check). NEVER run anything that pushes, deploys, deletes, rotates a secret, or starts a ` +
    `long-lived server — mark those 'skipped' and name them, do not run them. For each command report ` +
    `ok / rotted (documented but fails, or its path/flag is stale) / skipped. A documented command ` +
    `that no longer runs is a rotted ratchet to fix or delete.`,
    { label: 'gather:doc-commands', phase: 'Gather', schema: DOC_COMMANDS_SCHEMA },
  ),
])

phase('Synthesize')
const retro = await agent(
  `You are running a Selom retrospective. Shipped work: ${JSON.stringify(work)}. ` +
  `Open backlog: ${JSON.stringify(backlog)}. ` +
  `Documented-command execution pass: ${JSON.stringify(docCommands)}.\n\n` +
  `Produce: (1) ranked_next — the highest-leverage next spine improvements first, each with WHY + ` +
  `its source; (2) lessons_to_capture — lessons from the shipped work that should become DURABLE ` +
  `artifacts (the Ratchet) but may not be captured yet, each with its right home ` +
  `(test | script | handoff-note | memory-rule | code-boundary); (3) health_notes — recurring ` +
  `friction or deferred items that are aging. **Any command reported 'rotted' in the ` +
  `documented-command pass MUST surface** — as a health_note, or a lessons_to_capture item whose ` +
  `home is test/script (fix or delete the rotted ratchet). Be concrete, cite sources, and prefer a ` +
  `few high-signal items over a long list.`,
  { label: 'synthesize', phase: 'Synthesize', schema: RETRO_SCHEMA },
)

return retro
