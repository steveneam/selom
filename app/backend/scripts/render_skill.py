"""Render ANY skill on real corpus data and look at it — the dogfood loop, as one command.

A Plotly spec can be valid JSON, pass every assertion in the suite, and still encode a lie. That is
not a hypothesis: `enrichment` shipped dots 1-3 PIXELS across, `heatmap` laid 17 clusters on a
linear axis, `regression`'s `group` knob painted every point one colour, the strip mode rendered a
completely empty panel, and `confusion`'s cell labels landed on the wrong cells and one clean off
the plot. Every one of those passed its tests. Every one was found by rendering it and LOOKING.

So this is the loop, and it exists as a script because it had been hand-rolled inline once per
defect:

    uv run python scripts/render_skill.py confusion
    uv run python scripts/render_skill.py boxplot --params '{"style":"strip"}'
    uv run python scripts/render_skill.py lollipop slope ridge --out /tmp/look

**What it refuses to do is the point.** It calls :func:`skills.smoke.pin_process` first, so:

* a stub figure can never wear a real skill's name — the engine selectors must already be pinned,
  and a missing dependency raises instead of fabricating a plausible figure;
* the C1 compute and render caches are disabled, so an edit is actually re-run. A cache hit
  returns the PREVIOUS figure in 0.00 s, which during this session silently served the pre-fix
  `confusion` twice and looked exactly like the fix not working.

Related but different: ``render_parity.py`` renders five named plot types at a fixed physical
canvas so they can be measured against cnsplots. This one renders anything at a normal viewing
size so a human can see whether it is right.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

# Default canvas: a plausible on-screen figure, not the parity audit's measuring canvas. `scale`
# doubles the raster so text is legible when the PNG is viewed at 1:1.
WIDTH = 900
HEIGHT = 560
SCALE = 2


def _resolve_case(skill_id: str, smoke, datasets: pathlib.Path, override: dict, tmpdir: str):
    """(data path, params) for one skill — from the declared smoke case, so the corpus mapping
    lives in exactly one place and this tool can never drift onto data the matrix does not gate.

    Declared adapters (``celeris``, ``membership``) run through ``smoke._adapt``, the same
    conversion the matrix applies, rather than a lookalike that could quietly diverge from it.
    """
    entry = smoke.CASES.get(skill_id)
    if entry is None:
        raise SystemExit(
            f"{skill_id}: no smoke case declared. Add one to skills/smoke.py CASES "
            "(§5 point 4 requires it anyway), or pass --data and --params."
        )
    if not isinstance(entry, smoke.Case):
        raise SystemExit(f"{skill_id}: declared unsmokable — {getattr(entry, 'reason', '?')}")
    path = datasets / entry.dataset
    if entry.adapter:
        path = smoke._adapt(entry.adapter, path, tmpdir)
    return pathlib.Path(path), {**entry.params, **override}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("skills", nargs="+", help="skill id(s) to render")
    ap.add_argument("--out", default="", help="output directory (default: a temp dir, path printed)")
    ap.add_argument("--params", default="", help="JSON object merged over the smoke case's params")
    ap.add_argument("--data", default="", help="override the corpus file (path or relative to SELOM_DATASETS_DIR)")
    ap.add_argument("--style", default="selom", help="style pack to theme with")
    ap.add_argument("--width", type=int, default=WIDTH)
    ap.add_argument("--height", type=int, default=HEIGHT)
    args = ap.parse_args(argv)

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
    from skills import smoke

    # Refuses unless the engines are pinned AND turns the caches off. Both are load-bearing —
    # see the module docstring.
    smoke.pin_process()

    from skills.contract import run_skill_with_table

    import plotly.graph_objects as go

    # Via smoke's own accessor, which reads `config.datasets_dir` — the ONE typed env home
    # (structure guard M-002). Reading the env var directly here would be a second source of truth.
    corpus = smoke._corpus()
    if corpus is None:
        raise SystemExit("SELOM_DATASETS_DIR is unset — there is no real corpus to render against")
    datasets = pathlib.Path(corpus)
    override = json.loads(args.params) if args.params else {}
    import tempfile as _tempfile

    out = pathlib.Path(args.out) if args.out else pathlib.Path(
        _tempfile.mkdtemp(prefix="selom-render-"))
    out.mkdir(parents=True, exist_ok=True)

    import tempfile

    failures = 0
    tmpdir = tempfile.mkdtemp(prefix="selom-render-src-")
    for skill_id in args.skills:
        try:
            if args.data:
                candidate = pathlib.Path(args.data)
                path = candidate if candidate.exists() else datasets / args.data
                params = override
            else:
                path, params = _resolve_case(skill_id, smoke, datasets, override, tmpdir)
            if not path.exists():
                raise SystemExit(f"{skill_id}: corpus file not found: {path}")

            figure, table = run_skill_with_table(skill_id, str(path), params)
            # The same standing invariants the smoke matrix gates on — reported HERE too, so a
            # look-at-it run never shows a picture the gate would have rejected.
            reason = smoke.check_figure(figure)
            target = out / f"{skill_id}.png"
            go.Figure(figure).write_image(str(target), width=args.width, height=args.height,
                                          scale=SCALE)
            status = "OK " if not reason else "BAD"
            print(f"[{status}] {skill_id}  ->  {target}")
            if reason:
                failures += 1
                print(f"        check_figure: {reason}")
            if table:
                print(f"        table: {table.get('title', '(untitled)')} "
                      f"[{len(table.get('rows', []))} rows]")
        except SystemExit:
            raise
        except Exception as exc:  # a broken skill is the OUTPUT here, not a crash
            failures += 1
            print(f"[ERR] {skill_id}: {type(exc).__name__}: {exc}")

    print(f"\n{len(args.skills)} rendered into {out}" + (f" — {failures} problem(s)" if failures else ""))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
