#!/usr/bin/env node
// hygiene-scan.mjs -- repo-hygiene ratchet scanner (eng-practices port, M-001).
//
// Flags four classes of defect over the tracked set (never the ignored tree):
//   1. merge-conflict markers  (repo-wide)   -- a `;`-chained rebase --continue can commit these
//   2. forbidden tokens        (repo-wide)   -- leaked secrets/keys + a do-not-commit marker
//   3. trailing-newline hygiene (board files) -- append-prone COORDINATION/CURRENT must end in one \n
//   4. ci.yml paths-filter invariants        -- the two event-specific grants that each shipped
//        missing (see .github/workflows/README.md): `pull-requests: read` (PR listFiles API) and
//        `fetch-depth: 0` (push-event git-diff under persist-credentials:false). The PR gate cannot
//        self-catch a stripped `fetch-depth: 0` -- the pull_request path never exercises it -- so a
//        regression only breaks post-merge on push-to-main. This guard catches it at the gate instead.
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
const counts = { 'conflict-marker': 0, forbidden: 0, 'trailing-newline': 0, 'workflow-invariant': 0 };

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
    `=> ${hits.length} hit(s)\n`,
);
process.exit(hits.length > 0 ? 1 : 0);
