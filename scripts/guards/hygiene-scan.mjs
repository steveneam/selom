#!/usr/bin/env node
// hygiene-scan.mjs -- repo-hygiene ratchet scanner (eng-practices port, M-001).
//
// Flags SIX classes of defect over the tracked set (never the ignored tree):
//   1. merge-conflict markers  (repo-wide)   -- a `;`-chained rebase --continue can commit these
//   2. forbidden tokens        (repo-wide)   -- leaked secrets/keys + a do-not-commit marker
//   3. trailing-newline hygiene (board files) -- append-prone COORDINATION/CURRENT must end in one \n
//   4. ci.yml paths-filter invariants        -- the two event-specific grants that each shipped
//        missing (see .github/workflows/README.md): `pull-requests: read` (PR listFiles API) and
//        `fetch-depth: 0` (push-event git-diff under persist-credentials:false). The PR gate cannot
//        self-catch a stripped `fetch-depth: 0` -- the pull_request path never exercises it -- so a
//        regression only breaks post-merge on push-to-main. This guard catches it at the gate instead.
//   5. drive-path              (code globs) -- no absolute drive-letter path (the Windows drive
//        shape: a single letter, colon, slash) in tracked code; hardcoded checkout/data paths broke
//        portability on the host move. Scoped to .py/.ts/.tsx/.js/.mjs/.json this pass; prose
//        (docs/handoff) widening is a later change. A single letter NOT preceded by another letter,
//        so URL schemes (`http:`, `data:`) never match.
//   6. swallowed-gate          (scripts)    -- no tracked script may pipe a gate into tail/head/grep/wc:
//        a pipeline returns the FILTER's exit code, so the gate's failure is discarded. Cost a peer box
//        two incidents (forbidden content reaching origin behind a swallowed guard; a red suite read as
//        green). Comment lines are skipped, so a script may still EXPLAIN the hazard.
//
// Ratchet-ladder note: this executable check replaces graphify's documentary wiring signal.
// The patterns are ASSEMBLED FROM FRAGMENTS at runtime so this scanner passes its own scan.
//
// Modes:
//   --all      scan `git ls-files` (CI semantics: exactly the committed bytes)
//   --staged   scan the staged blobs (pre-commit hook semantics)
// Exit: 0 = clean, 1 = one or more hits, 2 = usage/error. Per-hit lines are `file:line: [class] msg`.

import { execFileSync } from 'node:child_process';

const argv = process.argv.slice(2);
const MODE = argv.includes('--staged') ? 'staged' : argv.includes('--all') ? 'all' : null;
if (!MODE) {
  process.stderr.write('usage: hygiene-scan.mjs --all | --staged\n');
  process.exit(2);
}

// --- fragment-assembled patterns (so this file never matches itself) -------------------
const OPEN = '<'.repeat(7); // conflict "ours" marker
const MID = '='.repeat(7); // conflict divider (only a hit when the file also holds OPEN/CLOSE)
const CLOSE = '>'.repeat(7); // conflict "theirs" marker

// Forbidden tokens: [label, regex]. Patterns match the REAL secret shape (not a bare prefix that
// over-matches prose like "the old AKIA... key"); each is assembled from fragments so this file,
// once tracked, passes its own scan.
const FORBIDDEN = [
  ['aws-access-key-id', new RegExp('AK' + 'IA' + '[0-9A-Z]{16}')],
  ['anthropic-api-key', new RegExp('sk-' + 'ant-api' + '[0-9A-Za-z_-]{8,}')],
  ['openai-api-key', new RegExp('sk-' + 'proj-' + '[0-9A-Za-z_-]{8,}')],
  ['private-key-block', new RegExp('-----BEGIN ' + '(RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----')],
  ['do-not-commit-marker', new RegExp('NO' + 'COMMIT')],
];

// Trailing-newline hygiene is enforced only on append-prone board files (the source ratchet's scope).
const BOARD_FILES = new Set(['COORDINATION.md', 'agent_handoff/CURRENT.md']);

// ci.yml paths-filter invariants: if the consolidated workflow uses dorny/paths-filter, it MUST keep
// both event-specific grants (assembled from fragments so this scanner never trips its own check).
const CI_WORKFLOW = '.github/workflows/ci.yml';
const CI_PATHS_FILTER = 'dorny/' + 'paths-filter';
const CI_REQUIRES = ['pull-' + 'requests: read', 'fetch-' + 'depth: 0'];

// Drive-path invariant (class 5): forbid an absolute drive-letter path in tracked CODE. Assembled
// from fragments (and applied only to code globs) so this scanner passes its own scan. The pattern
// is a single letter, NOT preceded by another letter (start-of-line or a non-letter), then a colon
// then a slash -- which matches the Windows drive shape but never a multi-letter URL scheme.
const CODE_EXTS = new Set(['py', 'ts', 'tsx', 'js', 'mjs', 'json']);
const DRIVE_PATH = new RegExp('(^|[^A-Za-z])' + '[A-Za-z]' + ':' + '[\\\\/]');

// Swallowed-gate invariant (class 6): a tracked SCRIPT must never pipe a gate's output into
// tail/head/grep/wc. A pipeline returns the LAST command's status, so the gate's failing exit code is
// discarded and the failure summary can be truncated away with it. This is not theoretical -- it cost a
// peer box two real incidents: a guard failure swallowed (forbidden content reached `origin`; history
// rewrite required) and a red suite read as green at a session close. CLAUDE.md's ratchet ladder already
// states the principle ("gated on its exit code, never a `;`-chain that ignores failure"); this makes it
// executable for the scripts where it does damage.
//
// Scope is deliberately NARROW -- tracked scripts only, and COMMENT LINES ARE SKIPPED so a script that
// *explains* the hazard (scripts/verify.sh does) is not flagged for describing it. Interactive shell use
// is out of reach of any repo guard and stays a habit; see the memory note. Assembled from fragments so
// this scanner passes its own scan.
const SCRIPT_EXTS = new Set(['sh', 'mjs', 'yml', 'yaml']);
const GATE_TOOLS = ['py' + 'test', 'ru' + 'ff', 'esl' + 'int', 'ts' + 'c', 'vi' + 'test',
  'hygiene-' + 'scan', 'verify' + '.sh'];
const SWALLOW = new RegExp('(' + GATE_TOOLS.join('|') + ')[^|;]*\\|\\s*(tail|head|grep|wc)\\b');

// --- file list per mode ---------------------------------------------------------------
function git(args) {
  return execFileSync('git', args, { cwd: process.cwd(), maxBuffer: 64 * 1024 * 1024 });
}
function listFiles() {
  if (MODE === 'all') {
    return git(['ls-files', '-z']).toString('utf8').split('\0').filter(Boolean);
  }
  // staged: added/copied/modified in the index
  return git(['diff', '--cached', '--name-only', '-z', '--diff-filter=ACM'])
    .toString('utf8').split('\0').filter(Boolean);
}
function readFileBytes(path) {
  // Read the exact bytes that will be committed: the index blob in --staged, HEAD-agnostic in --all.
  if (MODE === 'staged') return git(['show', `:${path}`]);
  return git(['show', `:${path}`]); // ':path' is the index copy; for --all it equals the tracked content
}

const files = listFiles();
const hits = [];
const counts = { 'conflict-marker': 0, forbidden: 0, 'trailing-newline': 0, 'workflow-invariant': 0, 'drive-path': 0, 'swallowed-gate': 0 };

for (const path of files) {
  let buf;
  try {
    buf = readFileBytes(path);
  } catch {
    continue; // unreadable (e.g. deleted-from-index race); skip
  }
  if (buf.includes(0)) continue; // binary file -- skip
  const text = buf.toString('utf8');
  const lines = text.split('\n');
  const hasOpen = text.includes(OPEN);
  const hasClose = text.includes(CLOSE);
  const ext = path.includes('.') ? path.slice(path.lastIndexOf('.') + 1).toLowerCase() : '';
  const isCode = CODE_EXTS.has(ext);
  const isScript = SCRIPT_EXTS.has(ext) || path.startsWith('.githooks/') || path.startsWith('scripts/');

  lines.forEach((line, i) => {
    const ln = i + 1;
    // 1. conflict markers
    if (line.startsWith(OPEN + ' ') || line === OPEN) {
      hits.push(`${path}:${ln}: [conflict-marker] '<<<<<<<' merge marker`);
      counts['conflict-marker']++;
    } else if (line.startsWith(CLOSE + ' ') || line === CLOSE) {
      hits.push(`${path}:${ln}: [conflict-marker] '>>>>>>>' merge marker`);
      counts['conflict-marker']++;
    } else if (line === MID && (hasOpen || hasClose)) {
      hits.push(`${path}:${ln}: [conflict-marker] '=======' divider (file has open/close markers)`);
      counts['conflict-marker']++;
    }
    // 2. forbidden tokens
    for (const [label, re] of FORBIDDEN) {
      if (re.test(line)) {
        hits.push(`${path}:${ln}: [forbidden] ${label}`);
        counts.forbidden++;
      }
    }
    // 5. drive-path (tracked code globs only; prose widening deferred)
    if (isCode && DRIVE_PATH.test(line)) {
      hits.push(`${path}:${ln}: [drive-path] absolute drive-letter path in tracked code`);
      counts['drive-path']++;
    }
    // 6. swallowed-gate (tracked scripts only; comments skipped -- explaining the hazard is fine)
    if (isScript && !/^\s*(#|\/\/)/.test(line) && SWALLOW.test(line)) {
      hits.push(`${path}:${ln}: [swallowed-gate] gate piped into tail/head/grep/wc -- the pipeline returns the FILTER's exit code, so the gate's failure is discarded. Run it raw, or capture to a file and test $? BEFORE filtering.`);
      counts['swallowed-gate']++;
    }
  });

  // 3. trailing-newline hygiene (board files only)
  if (BOARD_FILES.has(path) && text.length > 0) {
    if (!text.endsWith('\n')) {
      hits.push(`${path}: [trailing-newline] no trailing newline`);
      counts['trailing-newline']++;
    } else if (text.endsWith('\n\n')) {
      hits.push(`${path}: [trailing-newline] multiple trailing newlines`);
      counts['trailing-newline']++;
    }
  }

  // 4. ci.yml paths-filter invariants (only when the workflow actually uses paths-filter)
  if (path === CI_WORKFLOW && text.includes(CI_PATHS_FILTER)) {
    for (const need of CI_REQUIRES) {
      if (!text.includes(need)) {
        hits.push(`${path}: [workflow-invariant] paths-filter requires '${need}' -- see .github/workflows/README.md`);
        counts['workflow-invariant']++;
      }
    }
  }
}

for (const h of hits) process.stdout.write(h + '\n');
process.stdout.write(
  `\nhygiene-scan (${MODE}): scanned ${files.length} tracked file(s); ` +
    `conflict-marker=${counts['conflict-marker']} forbidden=${counts.forbidden} ` +
    `trailing-newline=${counts['trailing-newline']} workflow-invariant=${counts['workflow-invariant']} ` +
    `drive-path=${counts['drive-path']} swallowed-gate=${counts['swallowed-gate']} ` +
    `=> ${hits.length} hit(s)\n`,
);
process.exit(hits.length > 0 ? 1 : 0);
