# Data for Steven

Shortcuts to files made for you, so you don't have to remember where they live in the tree.

**The subfolders here are symlinks, not copies** — open one and you're in the real folder. Nothing
is duplicated, so these can never drift out of date, and editing a file here edits the real file.

---

## ERG Fig 1E — mock scotopic b-wave data + trace grid

Made 2026-08-02. Two variants, same six conditions and the same 7-point intensity ladder:

| Folder | What it is |
|---|---|
| **`ERG Fig 1E (mock, n=5)`** | The main set — realistic per-group n (3–8 eyes) and eye-to-eye spread. **Start here.** |
| **`ERG Fig 1E (mock, n=3)`** | The balanced variant — every group at n = 3, one uniform spread. |

> ### ⚠️ This is MOCK data
> The b-wave numbers are **simulated**. The trace figure uses **real waveform shapes**, but their
> assignment to conditions follows the simulated table — so the figure as a whole is **not
> experimental measurement** either. It is for laying out and reviewing the figure, and none of it
> may appear in a manuscript or in anything that reports real results.

### The four files you probably want

| File | Why |
|---|---|
| `mock_fig1e_traces.jpg` | The rendered trace grid — just look at it. |
| `mock_fig1e_bwave_points_wide.csv` | **Pastes straight into GraphPad/Excel** (replicates in columns) so the tool computes mean + SEM itself. |
| `mock_fig1e_bwave_long.csv` | Every individual data point, one row per eye × intensity — the canonical file. |
| `mock_fig1e_bwave_summary.csv` | n / mean / SD / SEM already computed, if you'd rather not. |

Plus `mock_fig1e_awave_summary.csv` — the **a-wave** per condition × intensity, if you want it.
It is measured off the drawn traces rather than simulated per eye, so it has no n or SEM; the
folder's own README explains what it is and is not before you plot it. All of it is **scotopic**.

The full manifest, what differs from the printed Fig 1E, the significance tables, and how to
regenerate any of it are in **`ERG Fig 1E (mock, n=5)/README.md`** — which documents both variants,
including the n = 3 tables. (The `n=3` folder holds only data files, no README of its own.)

---

**Real location:** `docs/records/erg-module/mock-fig1e/` (and its `n3/` subfolder). This folder is
only a signpost — if a symlink ever looks broken, the files themselves are still there.

To have something else surfaced here, just say so.
