# Auto-drive regression fixtures (Slice 4)

Frozen cold-`reproduce()` snapshots of blessed dogfood papers. Each `<paper>.json` is a
`reproduction.fixtures.DriveSnapshot` — the **honest classification shape** a never-seen paper
auto-produces (per-panel status + skill + any driven metric values, plus `selom_defects` which must
stay `0`). They are the regression anchor that stops engine growth from silently undoing a paper's
win. See `docs/records/reproduction-dogfood/spec.md` (Slice 4, D5).

These complement, not replace, the four hand ledgers
(`tests/test_reproduction_{rpgrip1,jev,hani,dorgau}.py`): the hand ledger locks the *hand-authored
target* ("what the paper should grade to"); the snapshot locks the *cold auto-drive* ("how the
engine actually classifies this paper today, with no hand ledger").

## What's measured here (s55)

All three blessed papers cold-drive to **0 driven panels** — every panel is `no_golden` /
`data_unmatched` / `run_failed`. That is the Slice-0/1 strategic insight confirmed on the
hand-ledger papers: the binding constraint is data-availability + extractor recall, not the engine
(every panel is still classified honestly, 0 Selom defects). So today these fixtures lock the
**honest classification**; `metrics` are empty and will populate automatically as recall rises — no
fixture-code change. RPGRIP1's PDF is not staged on this machine, so it is a documented slot below.

## How they're checked (`tests/test_reproduction_fixtures.py`)

- **Framework unit tests** (CI, no data) — prove `snapshot` / `diff` / `assert_reproduces` and the
  s46 tolerance reuse on a synthetic drive (status flip → red; driven metric within its
  metric-type band → green; out-of-band → red).
- **Characterization tests** (CI, no data) — load every committed `*.json` and assert its honest
  shape (statuses honest, `summary` == tally, `selom_defects == 0`).
- **Opt-in real re-drive** (owner machine only) — `reproduce()` each paper and
  `assert_reproduces(committed_snapshot, result)`. Skips automatically where the PDF isn't staged,
  so CI stays green and the owner machine gets the genuine engine-regression guard.

## Refresh / bless a snapshot

Run on a machine where the paper is staged, review the JSON diff, commit:

```pwsh
# from app/backend, with the BE env (PY + PYTHONPATH — see CURRENT.md / [[selom-backend-python-exec]])
& $PY -m scripts.regen_reproduction_fixtures            # all staged papers
& $PY -m scripts.regen_reproduction_fixtures hani       # one paper
```

A snapshot only changes when the cold drive's classification changes — review whether that change is
an intended improvement (recall rose, a panel now drives) or a regression (an honest status flipped
to a misleading one) before committing.

## Add the next paper (copy-paste)

1. Stage the paper's PDF + tabular supplements.
2. Add one entry to `FIXTURE_PAPERS` in `scripts/regen_reproduction_fixtures.py`
   (`paper_id -> (main_pdf, [(supplement, "tables"), ...])`).
3. `& $PY -m scripts.regen_reproduction_fixtures <paper_id>` → commit the new `<paper_id>.json`.
4. The opt-in re-drive test picks it up automatically (it parametrizes over `FIXTURE_PAPERS`).

### RPGRIP1 — pending slot

`rpgrip1` has an entry in `FIXTURE_PAPERS` with no PDF path: the Loi 2025 PDF isn't staged on this
machine. When it is, set the path and run the regen — its snapshot drops in identically.
