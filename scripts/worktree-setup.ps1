<#
worktree-setup.ps1 -- provision a Selom parallel-lane git worktree (eng-practices port, M-005).

Junctions the single MAIN-checkout node_modules (app/frontend) and BE .venv into a lane worktree so
a lane shares deps without a multi-GB reinstall, copies the .worktreeinclude files, and verifies the
toolchain. Idempotent (re-running is a no-op). Pure ASCII.

Usage (from anywhere):
    powershell -ExecutionPolicy Bypass -File scripts\worktree-setup.ps1 -Worktree D:\selom-eng

TEARDOWN -- READ THIS. Delete a lane worktree with:
    git worktree remove D:\selom-eng        # preferred; or, if it refuses:
    cmd /c 'rmdir /s /q D:\selom-eng'
NEVER use PowerShell `Remove-Item -Recurse` on a worktree: it FOLLOWS the node_modules / .venv
junctions and wipes the MAIN checkout's node_modules and .venv (data loss). This script snapshots the
main node_modules file-count before and after and fails loudly if it changed.

A dev server started in a lane is killed by its PORT LISTENER, not a harness task-stop:
    Get-NetTCPConnection -LocalPort 8011 -State Listen | ForEach-Object { taskkill /PID $_.OwningProcess /F }
#>
param(
  [Parameter(Mandatory = $true)][string]$Worktree,
  [string]$Main = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "[worktree-setup] $msg" }

$Main = (Resolve-Path $Main).Path
if (-not (Test-Path $Worktree)) {
  throw "Worktree path does not exist: $Worktree. Create it first with: git worktree add $Worktree <branch>"
}
$Worktree = (Resolve-Path $Worktree).Path
if ($Worktree -eq $Main) { throw "Worktree equals the main checkout ($Main) -- refusing." }

# A worktree's .git is a FILE (gitdir pointer); the main checkout's is a directory.
$wtGit = Join-Path $Worktree ".git"
if ((Test-Path $wtGit) -and (Get-Item $wtGit).PSIsContainer) {
  throw "$Worktree looks like a main checkout (.git is a directory), not a worktree -- refusing."
}

# Junction pairs: (target in MAIN, link in WORKTREE). Junctions need no admin (unlike symlinks).
$pairs = @(
  @{ Target = (Join-Path $Main "app\frontend\node_modules"); Link = (Join-Path $Worktree "app\frontend\node_modules") },
  @{ Target = (Join-Path $Main "app\backend\.venv");         Link = (Join-Path $Worktree "app\backend\.venv") }
)

# Snapshot MAIN node_modules file count (teardown-safety guard).
$mainNodeModules = $pairs[0].Target
$beforeCount = 0
if (Test-Path $mainNodeModules) {
  $beforeCount = (Get-ChildItem -LiteralPath $mainNodeModules -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object).Count
}
Write-Step "main node_modules file count (before): $beforeCount"

foreach ($p in $pairs) {
  $target = $p.Target
  $link = $p.Link
  if (-not (Test-Path $target)) {
    Write-Step "SKIP (no main target yet -- install it in the MAIN checkout first): $target"
    continue
  }
  if (Test-Path $link) {
    $item = Get-Item $link -Force
    $isJunction = ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0
    if ($isJunction) {
      Write-Step "OK (already junctioned): $link"
      continue
    }
    throw "Refusing to replace a REAL directory with a junction: $link. Remove it first with cmd /c 'rmdir /s /q ...' (never Remove-Item -Recurse)."
  }
  $parent = Split-Path -Parent $link
  if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
  New-Item -ItemType Junction -Path $link -Target $target | Out-Null
  Write-Step "junctioned: $link -> $target"
}

# Copy .worktreeinclude files (gitignored context the checkout does not carry).
$include = Join-Path $Main ".worktreeinclude"
if (Test-Path $include) {
  foreach ($line in Get-Content $include) {
    $pat = $line.Trim()
    if ($pat -eq "" -or $pat.StartsWith("#") -or $pat.StartsWith("**")) { continue }
    $src = Join-Path $Main $pat
    if (Test-Path $src -PathType Leaf) {
      $dst = Join-Path $Worktree $pat
      $dstDir = Split-Path -Parent $dst
      if (-not (Test-Path $dstDir)) { New-Item -ItemType Directory -Path $dstDir -Force | Out-Null }
      Copy-Item -LiteralPath $src -Destination $dst -Force
      Write-Step "copied: $pat"
    }
  }
}

# Verify the toolchain end-to-end.
Write-Step "verifying toolchain..."
$feNodeModules = $pairs[0].Link
if (-not (Test-Path (Join-Path $feNodeModules "next"))) {
  throw "FE node_modules junction does not resolve 'next' -- is the MAIN checkout installed (npm install --legacy-peer-deps)?"
}
$beVenvPy = Join-Path $Worktree "app\backend\.venv\Scripts\python.exe"
if (-not (Test-Path $beVenvPy)) {
  Write-Step "NOTE: BE .venv not junctioned (no main .venv yet) -- run 'uv sync' in the MAIN app/backend first."
}

# Teardown-safety: the MAIN node_modules count must be unchanged.
$afterCount = 0
if (Test-Path $mainNodeModules) {
  $afterCount = (Get-ChildItem -LiteralPath $mainNodeModules -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object).Count
}
Write-Step "main node_modules file count (after): $afterCount"
if ($beforeCount -ne $afterCount) {
  throw "MAIN node_modules file count changed ($beforeCount -> $afterCount) -- provisioning must never touch the main tree. Investigate before proceeding."
}

Write-Step "done. Lane ready: $Worktree"
Write-Step "Remember: offset ports (BE :801X, FE :300X; :8000 = eamos, never bind), set API_PROXY_TARGET per lane, keep the Vercel git-email."
