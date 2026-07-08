#!/usr/bin/env node
// guard-worktree-install.mjs -- refuse `npm install` inside a git worktree (eng-practices port, M-005).
//
// A lane worktree shares the MAIN checkout's node_modules via a junction (scripts/worktree-setup.ps1),
// so an `npm install`/`npm ci` there writes THROUGH the junction and clobbers the main tree's deps.
// This preinstall hook aborts the install when the enclosing checkout is a worktree -- detected by its
// `.git` being a FILE (`gitdir: ...` pointer) rather than a directory. The MAIN checkout (`.git` is a
// directory) and a normal CI clone are unaffected. Escape hatch: SELOM_WORKTREE_INSTALL_OK=1.

import { existsSync, statSync } from "node:fs";
import { dirname, join } from "node:path";

if (process.env.SELOM_WORKTREE_INSTALL_OK === "1") process.exit(0);

// Walk up from cwd to the enclosing checkout's `.git` entry.
let dir = process.cwd();
let gitPath = null;
for (;;) {
  const candidate = join(dir, ".git");
  if (existsSync(candidate)) {
    gitPath = candidate;
    break;
  }
  const parent = dirname(dir);
  if (parent === dir) break; // reached the filesystem root
  dir = parent;
}

if (gitPath && statSync(gitPath).isFile()) {
  process.stderr.write(
    "\n[worktree guard] Refusing `npm install` inside a git worktree.\n" +
      "A lane worktree shares the MAIN checkout's node_modules via a junction; installing here would\n" +
      "clobber the main tree. Install once in the MAIN checkout, then run scripts/worktree-setup.ps1\n" +
      "to junction node_modules into the lane. Override (rarely needed): SELOM_WORKTREE_INSTALL_OK=1.\n\n",
  );
  process.exit(1);
}

process.exit(0);
