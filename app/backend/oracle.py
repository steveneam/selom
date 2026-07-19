"""Reproduction Engine — the gated R validation oracle (build-plan R3, loop stage 7).

The **blame instrument**: it recapitulates the authors' *actual* tool (edgeR / fgsea) on
the same data to disambiguate ``engine-delta`` vs ``upstream-delta`` vs
``paper-irreproducible`` (spec §Validation & Blame; the dogfood pattern from
``<scratch-dir>/{fig5,fig6}-real/*_oracle.R``). It is **validation-only (ADR 0002), gated, and
NEVER on the shipped path** — disabled by default, so the product profile degrades blame to
``delta-unmeasured`` honestly (config ``SELOM_ORACLE``; spec D9/D12).

The split that keeps the fast suite green and env-independent: **running** R is gated +
isolated in :func:`run_r`; **parsing** the oracle's ``result.json`` (:func:`read_result`)
and **turning it into a verdict** (:func:`build_oracle_result`, via
:func:`reproduction.oracle_agreement`) are pure and unit-tested on captured fixtures. The
live R subprocess is exercised only by the dev CLI / a skip-guarded integration test.
"""

from __future__ import annotations

import json
import pathlib
import subprocess

from reproduction import OracleResult, oracle_agreement

TEMPLATES = pathlib.Path(__file__).parent / "oracle_templates"


class OracleUnavailable(RuntimeError):
    """The oracle is disabled (``SELOM_ORACLE=off``) or no Rscript could be resolved.

    Callers catch this and degrade blame to ``delta-unmeasured`` rather than crash
    (spec Error Behavior); never raised on the shipped path because the oracle never runs
    there."""


def resolve_rscript() -> str:
    """Locate Rscript — config first, then the known local install — or raise.

    R 4.6 is not on PATH (memory ``selom-r-validation-oracle``); ``SELOM_R_ORACLE_BIN``
    pins it explicitly. Raises :class:`OracleUnavailable` when the oracle is disabled
    (the default) so the gate is enforced in one place."""
    from config import settings

    if not settings.oracle_enabled:
        raise OracleUnavailable(
            "oracle disabled (set SELOM_ORACLE=r to enable; validation-only, ADR 0002)"
        )
    if settings.r_oracle_bin and pathlib.Path(settings.r_oracle_bin).exists():
        return settings.r_oracle_bin
    import os

    localappdata = os.environ.get("LOCALAPPDATA", "")
    if localappdata:
        for rdir in sorted((pathlib.Path(localappdata) / "Programs" / "R").glob("R-*"), reverse=True):
            cand = rdir / "bin" / "Rscript.exe"
            if cand.exists():
                return str(cand)
    raise OracleUnavailable(
        "Rscript not found; set SELOM_R_ORACLE_BIN to the R 4.6 Rscript(.exe)"
    )


def run_r(template: str, args: list[str], *, workdir: pathlib.Path | str, timeout: int = 1800) -> str:
    """Run a bundled R template under the gate; return the combined log text.

    Output is captured and written to ``<workdir>/<template>.log`` (guard 9: the Windows
    console chokes on R's ∩/− under non-utf-8; never let it reach stdout). Raises on a
    non-zero exit so a broken oracle is a loud failure, not a silent wrong blame."""
    rscript = resolve_rscript()
    script = TEMPLATES / template
    if not script.exists():
        raise OracleUnavailable(f"oracle template missing: {script}")
    workdir = pathlib.Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [rscript, str(script), *args],
        capture_output=True,
        timeout=timeout,
        cwd=str(workdir),
    )
    log = (proc.stdout or b"").decode("utf-8", "replace") + (proc.stderr or b"").decode("utf-8", "replace")
    (workdir / f"{pathlib.Path(template).stem}.log").write_text(log, encoding="utf-8")
    if proc.returncode != 0:
        raise OracleUnavailable(f"{template} failed (exit {proc.returncode}); see {workdir}")
    return log


def read_result(workdir: pathlib.Path | str) -> dict:
    """Parse the ``result.json`` an oracle template wrote → ``{tool, version, metrics}``."""
    path = pathlib.Path(workdir) / "result.json"
    return json.loads(path.read_text(encoding="utf-8"))


# --- the gated runners (compose run_r + read_result) --------------------------


def run_edger_signature(
    counts_path: str, universe_path: str, ref: str, treat: str,
    treat2: str | None = None, *, workdir: pathlib.Path | str,
) -> dict:
    """edgeR signature-count oracle for a bulk DE panel (RPGRIP1 Fig 5). Gated."""
    args = [counts_path, universe_path, str(workdir), ref, treat]
    if treat2:
        args.append(treat2)
    run_r("edger_signature.R", args, workdir=workdir)
    return read_result(workdir)


def run_fgsea_terms(
    gmt_path: str, rnk_dir: str, rods: list[str], *, workdir: pathlib.Path | str,
) -> dict:
    """fgsea enriched-term-count oracle for a GSEA panel (RPGRIP1 Fig 6E). Gated."""
    run_r("fgsea_terms.R", [gmt_path, rnk_dir, str(workdir), *rods], workdir=workdir)
    return read_result(workdir)


# --- the pure verdict step (no R; the blame hinge) ----------------------------


def build_oracle_result(
    tool: str,
    ran_on: str,
    oracle_value,
    golden,
    computed,
    *,
    rel_tol: float = 0.01,
    close_tol: float = 0.25,
    ints_exact: bool = True,
    direction_close: bool = False,
    version: str = "",
    note: str = "",
) -> OracleResult:
    """Turn one oracle value into the :class:`OracleResult` that :func:`assign_blame` reads.

    ``ran_on`` is the hinge: ``DEPOSITED_RAW`` (authors' full method on the deposited data —
    a miss vs golden ⇒ paper-irreproducible) vs ``SELOM_INTERMEDIATE`` (the right engine on
    Selom's upstream output — splits engine-delta from upstream-delta). Agreement reuses the
    metric's declared band (D4): wide-band counts (GSEA, RISKS #10) read "comparable" as
    agreement; ID-sets stay strict."""
    agrees_paper, agrees_selom = oracle_agreement(
        oracle_value, golden, computed,
        rel_tol=rel_tol, close_tol=close_tol,
        ints_exact=ints_exact, direction_close=direction_close,
    )
    return OracleResult(
        tool=tool, version=version, ran_on=ran_on,
        agrees_with_paper=agrees_paper, agrees_with_selom=agrees_selom, note=note,
    )


# --- dev CLI (ADR 0002 — validation only, not a product endpoint) -------------

if __name__ == "__main__":  # pragma: no cover — dev/validation harness
    import argparse

    p = argparse.ArgumentParser(description="Reproduction-engine R oracle (validation-only, ADR 0002)")
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("edger", help="edgeR signature-count oracle")
    e.add_argument("--counts", required=True)
    e.add_argument("--universe", required=True)
    e.add_argument("--ref", required=True)
    e.add_argument("--treat", required=True)
    e.add_argument("--treat2", default=None)
    e.add_argument("--workdir", required=True)
    f = sub.add_parser("fgsea", help="fgsea term-count oracle")
    f.add_argument("--gmt", required=True)
    f.add_argument("--rnk-dir", required=True)
    f.add_argument("--rods", nargs="+", required=True)
    f.add_argument("--workdir", required=True)
    args = p.parse_args()
    if args.cmd == "edger":
        out = run_edger_signature(args.counts, args.universe, args.ref, args.treat,
                                  args.treat2, workdir=args.workdir)
    else:
        out = run_fgsea_terms(args.gmt, args.rnk_dir, args.rods, workdir=args.workdir)
    print(json.dumps(out, indent=2))
