# Paper outputs — the Write-up stage

Written 2026-08-03 03:44 +1000 (Sydney). Closes `R-01` + `R-03` of `docs/reachability/backlog.md`:
the lit-synthesizer and every paper-level output ship working and have **zero FE call sites**.

Scope is the **IA placement decision** plus the surface that follows from it. Backend is read-only —
`/methods/compose`, `/citations/*` and `/papers/{slug}/{methods,legends,scorecard}` already answer.

---

## 1. The home — decided before building, because moving it later is expensive

**Decision: a fourth stage in the existing Paper shell — `/paper/[id]?stage=write-up`.**
No new top-level route, no second home.

### Why not the Workspace Library

The kickoff asks whether the Library's Methods/legend slot *is* the intended home. It is not — and
`docs/workspace-library/spec.md` §11 already says so in the sentence that reserved the slot:

> **FE surface** — a "Methods & legend" panel **after a run** (Reproduction view now; own-data run later)

The Library (`/library`) is the account-level index of *assets that outlive a project* — saved papers,
gene sets, skill installs. It is deliberately project- and data-agnostic. A Methods section is the
opposite: it is derived from **one paper's one reproduction run**, and it changes when that run
changes. Putting it in the Library would separate the output from the run that justifies it, and
would need the run's ledger in a surface that has no concept of a run.

§11's own-data half is already shipped exactly this way (s49): the run response's `figure_legend` is
rendered by `PublishConfidence` **next to the figure it describes**, not in a library. This spec is
the *paper*-scale instantiation of the same rule — same engine, same placement discipline.

### Why the Paper shell

`docs/workspace-library/umbrella-shell.md` already folded `/skill-match/[id]` and
`/reproduction/paper/[id]` into one route (`/paper/[id]`) with a URL-driven stage pipeline. The paper
workflow is a pipeline that produces something, and today it stops at the grade:

```
Skill Match  →  Reproduce  →  Score  →  Write-up      ← new
 what skills    run them      how did    what you paste
 does it need   on your data  we do      into the manuscript
```

The Write-up stage is the pipeline's terminal output. It inherits the shell's persistent chrome
(Library back-link, pipeline nav, paper metadata header) for free, and it is already reachable — both
`/library` and the Reproduction index's "Your papers" strip link into `/paper/[id]`.

`/reproduction/[slug]` (the published showcase gallery) is **untouched**. It stays the graded-proof
surface; it is not a paper *workspace* and gains no write-up of its own.

---

## 2. What the stage shows

Four sections, in the order a manuscript needs them:

| Section | Content | Route |
|---|---|---|
| **Methods** | One paste-ready Methods section: modality-aware intro, per-skill prose in figure order, one Selom attribution sentence. | `POST /methods/compose` · `GET /papers/{slug}/methods` |
| **Figure legends** | One paste-ready caption per in-scope analysis panel, labelled `Figure 4e.` from the ledger's own numbering. | `GET /papers/{slug}/legends` |
| **References** | The deduped tool citations the Methods section carries, plus **Cite this paper** (the paper's own DOI → a structured record) and **Find related literature** (topical PubMed). | `GET /citations/by-doi` · `GET /citations/search` |
| **Reproducibility statement** | A paste-ready sentence stating what was computationally reproduced, with the Reproducibility Score, tier and panel coverage. | `GET /papers/{slug}/scorecard` |

### Two sources, one surface

The stage resolves its content from whichever source the paper has. This is a source *resolver*
(`lib/litsynth/source.ts`), not two surfaces:

- **`run` — your own reproduction** (`paper.reproductionRunId` → `GET /reproduction-runs/{id}`).
  Methods come from `POST /methods/compose`, fed with the ledger's in-scope analysis panels
  (`skill_id` + `params`, deduped, in figure order — the same selection
  `litsynth/from_ledger.ledger_skill_runs` makes server-side). The score comes from the run's own
  ledger scorecard.
- **`reference` — a published reproduction** (`rpgrip1` · `jev` · `hani`). All four sections come
  from the paper-level routes directly.

**Why the empty state is a live reference, not a skeleton.** The Score stage renders a dimmed ghost
when there is no run (U6, "mirrors the real layout so it doesn't reflow"). A write-up ghost would
teach nothing — the whole value is *the prose*, and grey bars have none. So the no-run state renders
a **real** write-up from a paper Selom has already reproduced, clearly labelled as an example, with a
three-paper switcher and a link to that paper's graded page. It is honest (it is real output from a
real reproduction), and it answers "what will I actually get?" the way a skeleton cannot.

### The `/papers/{slug}/scorecard` question

`GET /papers/{slug}` already embeds the scorecard, so a surface that wants panels *and* score fetches
the whole ledger — which is why the standalone route went unread. The Write-up stage is the caller
that genuinely wants **only** the scorecard: the reproducibility statement needs `score`, `tier`,
`n_in_scope` and `findings`, and none of `panels`, `validations` or `golden`. Fetching the full
ledger (~67 KB of panel/golden/validation data) to render one sentence is the wrong call.

### Known backend gap — legends for your own run

`/papers/{slug}/legends` is slug-only; there is no run-scoped legend route, so **figure legends are
available for reference reproductions but not yet for a user's own run**. The stage says this
plainly rather than hiding the section. Backend is read-only in this lane, so this is recorded as a
follow-up, not edited here: a `GET /reproduction-runs/{run_id}/legends` (or a `legends` field on the
run payload) would close it — `compose_ledger_legends(ledger)` already does the work and the run
already has the ledger.

---

## 3. Mobbin — the comparison pass (standing rule, owner-directed 2026-08-02)

A comparison instrument, not a template. What it ruled **out** matters more than what it confirmed.

### Rejected

- **Export-configuration modals** — [Notion](https://mobbin.com/screens/8aff7e5c-7473-4965-807f-92cb8d55eba2)
  (format · database views · page content · include-subpages), [Coda](https://mobbin.com/screens/f5c64d21-bf07-4525-a9b9-c76ecc16943b)
  (pages · layout · paper size), [ClickUp](https://mobbin.com/screens/76d8f7eb-14ed-416e-b0e0-7add15c67b48)
  (this-page vs entire-doc, PDF/HTML/Markdown/Print), [Skiff](https://mobbin.com/screens/d413a6a7-3f02-48e4-a5ba-5b758512facc).
  **Why rejected:** these are *whole-document* exports where the configuration is the point. Selom's
  write-up is four short generated blocks whose destination is a manuscript the user is already
  editing. The action is **copy this block**, and a modal asking about paper size between the user
  and a paragraph is pure ceremony. Per-section `Copy` inline, as `PublishConfidence` already does.
- **"Improve your score" framing** — [Contra Discovery score](https://mobbin.com/screens/fee097dc-6ca9-4c8d-ae5b-daeb67e81bbe)
  ("Build your foundation — strengthen your score", factors tagged HIGH IMPACT),
  [Lovable](https://mobbin.com/screens/8165137a-b9f5-4c23-b36f-f6b8ebf5a6bf) (Current 7.5 → Potential 9.5).
  **This is the most important rejection.** Those are *performance* scores the user is expected to
  raise. Reproducibility is a property of **the paper and its data** — a user cannot raise it, and a
  low score is frequently a **discovery**, not a failure (`lib/reproduction/types.ts`: attribution
  exists "so a low score never reads as accusatory"). Importing the improve-your-score idiom would
  misrepresent the metric and blame the user for someone else's paper.
- **Radar / spider breakdown** — [Uxcel skill graph](https://mobbin.com/screens/3653e9d6-56f3-45ac-a647-96bda6073a95).
  A radar implies commensurable axes that compose into one competence. Selom keeps **two axes
  deliberately separate and non-summable** (reproducibility vs Selom confidence) — their *divergence*
  is the signal. A radar would erase exactly the thing worth reading.
- **Score-in-a-modal** — [Whop financial health](https://mobbin.com/screens/03413816-d3ca-4486-b76a-395028847517).
  Its *structure* is the closest analogue found (score cards → "What impacts your score?" factor list
  → a plain-language "Understanding your scores" footnote), but as an interstitial. Selom's score is
  primary content of a stage, not an interruption. Structure taken, modal rejected.

### Taken

- **[Elicit research report](https://mobbin.com/screens/00c13c4c-e8c3-4638-8911-a77ba160421f)** — the
  closest true peer (a generated research document with a REFERENCES section). Confirms: references
  as a plain hanging-indent list at the end of the document, and the export as **plain
  format-specific actions sitting at the end of the list** (Download BIB / RIS / TXT) rather than a
  configured dialog. Selom ships `Copy` per section + `Copy all` on the reference list.
- **[15Five MEI](https://mobbin.com/screens/ec1806bc-076b-4f49-8854-5199a7eb761f)** — a big `84/100`
  paired with an explicit **"How is the MEI calculated?"** link. Confirms the existing `showExplain`
  affordance on `ScoreReport` and that the write-up's score line should link back to the Score stage
  rather than restate the method.
- **[Qatalog](https://mobbin.com/screens/5ce42aea-3a38-44c2-acc9-a3d8567f77a4)** — a generated answer
  with `Copy` inline and references behind a compact count pill. Confirms keeping the reference list
  collapsed-by-count when long, so the prose stays the focus.

---

## 4. Files

```
app/frontend/lib/litsynth/api.ts        typed client for the six routes
app/frontend/lib/litsynth/source.ts     ledger → SkillRunRef[]; the run|reference resolver
app/frontend/lib/litsynth/*.test.ts     unit tests for both
app/frontend/components/methods/        the paste-ready prose primitives (ProseBlock, ReferenceList)
app/frontend/components/paper/stages/write-up-stage.tsx
app/frontend/components/paper/pipeline.tsx        + the "write-up" stage
app/frontend/components/paper/paper-shell.tsx     + the stage mount
```

## 5. Done

- `/paper/[id]?stage=write-up` reachable from the pipeline on every stage of a paper opened from
  `/library` or the Reproduction index.
- All six `R-01`/`R-03` routes have a real FE call site; their waivers are deleted from
  `app/backend/tests/test_reachability_guard.py` and `test_no_stale_waivers` passes.
- `bash scripts/verify.sh --fast` green (fe-build is train-only in a worktree).
