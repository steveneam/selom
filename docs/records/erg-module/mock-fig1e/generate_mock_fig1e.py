#!/usr/bin/env python3
"""Generate SIMULATED scotopic ERG b-wave data shaped like Figure 1E.

    ============================================================
    THIS DATA IS SIMULATED. It is NOT experimental measurement.
    Never place it in a manuscript, figure, or analysis that
    reports real results.
    ============================================================

Purpose: a plottable stand-in for the Fig 1E cohort while the real
extraction is in flight, so the intensity-response figure can be laid out and
reviewed. Shape is faithful to the printed Fig 1E (condition ordering, the
7-point scotopic intensity ladder, per-group n, realistic eye-to-eye spread);
the *values* are drawn from a model, not measured.

Two deliberate departures from the printed figure (requested 2026-08-02):

  1. AAV8-CMV-GFP is pulled DOWN to a clean null. In the real extraction it
     reads ~42 uV at 1.0 log cd.s/m2 -- level with Untreated, which is more
     residual signal than a GFP-only control should show.
  2. AAV8-RK-PDE6B takes that vacated partial-response level (~48 uV): a
     visible rescue over the nulls, well short of the 3'UTR arm (~135 uV).

Model: each condition is a Naka-Rushton saturating intensity-response curve

    V(I) = Vmax / (1 + 10^(n * (logK - I)))

Each eye gets its own Vmax scale factor and logK jitter (drawn from the
per-condition spread below), then per-measurement recording noise is added.
Everything is seeded, so re-running reproduces the CSVs byte-for-byte.

To retune, edit CONDITIONS below -- it is the single source of truth. The
`target_at_log1` comment on each row is the b-wave the curve yields at
1.0 log cd.s/m2 (the Fig 1E reference intensity), so you can dial a group by
eye without re-deriving Naka-Rushton parameters.

Usage:  python3 generate_mock_fig1e.py [--seed N] [--outdir DIR]
Pure standard library -- no numpy, pandas, or scipy.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
from pathlib import Path

# The 7 scotopic flash intensities (log cd.s/m2), dimmest to brightest.
# Mirrors skills/_erg.py::INTENSITIES_LOG -- Group1..Group7 in the LabScribe export.
INTENSITIES_LOG = [-1.7, -0.8, 0.1, 1.0, 1.9, 2.8, 3.1]

# Per-condition model. Order = the Fig 1E display order (skills/_erg.py::CONDITION_ORDER);
# `condition_order` is emitted as a column so the plot can be re-sorted without re-generating.
#
#   vmax    saturating b-wave amplitude (uV)
#   log_k   semi-saturation intensity (log cd.s/m2) -- lower = more sensitive
#   n       slope
#   cv      eye-to-eye coefficient of variation on Vmax
#   n_eyes  group size, matched to the real Fig 1E cohort
# Thresholds matter as much as amplitudes here. The WT Control is fully dark-adapted and
# already responds at the dimmest flash, but every rd10 arm -- treated or not -- has a raised
# threshold and stays at the noise floor until flash 1.0, which is what the real recordings
# show. That is encoded by giving Control a low log_k with a shallow slope, and every rd10 arm
# a log_k near 1.0 with a STEEP slope (n >= 1.4) so the curve is flat below the threshold and
# climbs sharply through it.
CONDITIONS = [
    # label,                        vmax,  log_k,   n,    cv,   n_eyes   @1.0    @1.9
    ("Control",                    235.0,  -1.55, 0.85, 0.10,  8),   # ~233   ~235  WT
    ("Untreated",                   34.0,   1.15, 1.40, 0.22,  4),   # ~13    ~31   null
    ("AAV8-RK-PDE6B",              105.0,   0.78, 2.30, 0.30,  7),   # ~80    ~105  partial rescue
    ("AAV8-RK-GFP-polyA-stuffer",   30.0,   1.18, 1.40, 0.22,  3),   # ~11    ~27   null
    ("AAV8-CMV-GFP",                26.0,   1.22, 1.40, 0.22,  4),   # ~9     ~23   null (pulled down)
    ("AAV8-RK-PDE6B-3UTR",         165.0,   0.75, 2.40, 0.20,  4),   # ~132   ~165  best rescue
]

# Recording noise added per (eye x intensity) measurement, uV, as
# `NOISE_FLOOR_UV + NOISE_FRAC * amplitude`. Signal-proportional rather than flat: a flat term
# large enough to look realistic on a 200 uV Control trace (~2 uV) completely swamps the sub-uV
# dim end of a null curve, which made group-mean series non-monotonic in intensity and shuffled
# the three null groups against each other. Scaling with amplitude keeps the dim end quiet
# (curves rise monotonically, as a real intensity-response series must) while still giving the
# bright end believable scatter.
NOISE_FLOOR_UV = 0.5
NOISE_FRAC = 0.02

# Tolerance for the self-check below: rank/monotonicity differences smaller than this are
# inside the noise band and are not treated as failures. The three null groups are *designed*
# to be indistinguishable, and the top two flashes sit 0.3 log apart on a saturated curve, so
# demanding a strict order there would assert something the biology does not support.
NOISE_BAND_UV = 3.0

#: Ceiling for "no response yet". Every rd10 arm must read below this at flashes dimmer
#: than 1.0 log; only the WT Control is exempt.
THRESHOLD_FLOOR_UV = 8.0

# Spread of each eye's semi-saturation point around its group value (log units).
LOG_K_JITTER = 0.12


def naka_rushton(x_log: float, vmax: float, log_k: float, n: float) -> float:
    """b-wave amplitude at flash intensity `x_log`. Matches skills/_erg.py::naka_rushton."""
    return vmax / (1.0 + 10.0 ** (n * (log_k - x_log)))


#: A single moderate CV used when every group is forced to the same size (--n-eyes). At n=3
#: this puts SEM near 9% of the mean: error bars clearly visible without swamping the
#: between-condition differences. The per-condition CVs in CONDITIONS stay the default.
UNIFORM_CV = 0.16


def build_rows(seed: int, n_eyes_override: int | None = None,
               cv_override: float | None = None) -> list[dict]:
    """One row per (eye x intensity). Deterministic for a given seed.

    `n_eyes_override` forces every condition to the same group size, and `cv_override`
    forces one eye-to-eye spread across all of them -- used to emit the balanced n=3 variant
    from this same model rather than a forked copy of it.
    """
    rng = random.Random(seed)
    rows: list[dict] = []
    animal = 0

    for order, (condition, vmax, log_k, n, cv, n_eyes) in enumerate(CONDITIONS, start=1):
        if n_eyes_override is not None:
            n_eyes = n_eyes_override
        if cv_override is not None:
            cv = cv_override
        # Each eye's own responsiveness. Lognormal keeps Vmax positive and gives the
        # right-skewed spread seen in AAV cohorts (a few eyes transduce poorly).
        sigma = math.sqrt(math.log(1.0 + cv * cv))
        scales = [math.exp(rng.gauss(-0.5 * sigma * sigma, sigma)) for _ in range(n_eyes)]
        jitters = [rng.gauss(0.0, LOG_K_JITTER) for _ in range(n_eyes)]
        # Centre both draws within the group. At n=3..8 raw sampling error moves a group mean
        # by tens of uV, which would swamp the intended between-condition differences. Centring
        # pins each group mean to its `target_at_log1` while leaving eye-to-eye spread intact.
        scale_mean = sum(scales) / n_eyes
        scales = [s / scale_mean for s in scales]
        jitter_mean = sum(jitters) / n_eyes
        jitters = [j - jitter_mean for j in jitters]

        # Standardise the realised spread to the requested CV. Centring alone fixes the mean
        # but leaves the SD to chance, and at n=3 that is wild: one group landed at SEM 1.7%
        # of its mean (error bars invisible) while another hit 20%. Rescaling the deviations
        # so the sample CV equals `cv` gives every group the same, deliberate spread.
        if n_eyes > 1:
            sd = math.sqrt(sum((s - 1.0) ** 2 for s in scales) / (n_eyes - 1))
            if sd > 0:
                scales = [1.0 + (s - 1.0) * (cv / sd) for s in scales]

        for eye_scale, eye_jitter in zip(scales, jitters):
            animal += 1
            # One eye per animal, alternating laterality -- the real cohort mixes LE/RE.
            eye = "LE" if animal % 2 else "RE"
            sample_id = f"MOCK-{animal:02d}_{eye}"

            eye_vmax = vmax * eye_scale
            eye_log_k = log_k + eye_jitter

            for group, x_log in enumerate(INTENSITIES_LOG, start=1):
                value = naka_rushton(x_log, eye_vmax, eye_log_k, n)
                value += rng.gauss(0.0, NOISE_FLOOR_UV + NOISE_FRAC * value)
                rows.append({
                    "sample_id": sample_id,
                    "animal": f"MOCK-{animal:02d}",
                    "eye": eye,
                    "condition": condition,
                    "condition_order": order,
                    "intensity_group": group,
                    "intensity_log_cd_s_m2": x_log,
                    "b_wave_uv": round(max(0.0, value), 2),
                })
    return rows


def summarise(rows: list[dict]) -> list[dict]:
    """Per (condition x intensity): n, mean, SD, SEM. SD is the sample (n-1) form."""
    buckets: dict[tuple, list[float]] = {}
    for r in rows:
        key = (r["condition_order"], r["condition"], r["intensity_group"],
               r["intensity_log_cd_s_m2"])
        buckets.setdefault(key, []).append(r["b_wave_uv"])

    out = []
    for (order, condition, group, x_log) in sorted(buckets):
        vals = buckets[(order, condition, group, x_log)]
        n = len(vals)
        mean = sum(vals) / n
        sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / (n - 1)) if n > 1 else 0.0
        out.append({
            "condition": condition,
            "condition_order": order,
            "intensity_group": group,
            "intensity_log_cd_s_m2": x_log,
            "n_eyes": n,
            "mean_b_wave_uv": round(mean, 2),
            "sd_uv": round(sd, 2),
            "sem_uv": round(sd / math.sqrt(n), 2) if n > 1 else 0.0,
        })
    return out


def widen(summary: list[dict]) -> tuple[list[str], list[list]]:
    """Intensity-per-row layout for a direct paste into Prism/Excel."""
    labels = [c[0] for c in CONDITIONS]
    header = ["intensity_log_cd_s_m2", "intensity_group"]
    for label in labels:
        header += [f"{label} mean_uv", f"{label} sem_uv", f"{label} n"]

    by_key = {(r["condition"], r["intensity_group"]): r for r in summary}
    body = []
    for group, x_log in enumerate(INTENSITIES_LOG, start=1):
        row: list = [x_log, group]
        for label in labels:
            r = by_key[(label, group)]
            row += [r["mean_b_wave_uv"], r["sem_uv"], r["n_eyes"]]
        body.append(row)
    return header, body


#: Groups that must read as null (no rescue). Kept together as one cluster; their internal
#: order is deliberately NOT asserted -- they differ by less than the noise band.
NULL_GROUPS = ["Untreated", "AAV8-RK-GFP-polyA-stuffer", "AAV8-CMV-GFP"]
#: Groups that must show rescue, and must beat every null group significantly.
RESCUE_GROUPS = ["AAV8-RK-PDE6B", "AAV8-RK-PDE6B-3UTR"]
REFERENCE_LOG_I = 1.0            # the Fig 1E bar intensity
#: Intensities the stats table and the console readout cover. 1.9 is included because it is
#: the working intensity for this figure; every invariant is checked at BOTH.
REPORT_INTENSITIES = [1.0, 1.9]
ALPHA = 0.05           # every rescue-vs-null comparison must clear this
#: The 3'UTR arm must beat plain RK-PDE6B, but only *slightly* -- significant, yet not the
#: overwhelming separation the rescue-vs-null comparisons show. Hence a p-value BAND: too
#: small a p means the two rescue arms are drawn too far apart to read as a graded effect.
SLIGHT_P_BAND = (0.0005, ALPHA)


# --- Welch's t-test, pure stdlib -------------------------------------------------------
# `statistics` has no t-distribution, so the two-tailed p comes from the regularised
# incomplete beta function: p = I_{v/(v+t^2)}(v/2, 1/2). Continued-fraction evaluation
# (Lentz's method), which converges quickly across the range used here.

def _betacf(a: float, b: float, x: float) -> float:
    TINY, EPS, ITMAX = 1e-30, 3e-16, 300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < TINY:
        d = TINY
    d = 1.0 / d
    h = d
    for m in range(1, ITMAX + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < TINY:
            d = TINY
        c = 1.0 + aa / c
        if abs(c) < TINY:
            c = TINY
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < TINY:
            d = TINY
        c = 1.0 + aa / c
        if abs(c) < TINY:
            c = TINY
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < EPS:
            break
    return h


def _betai(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def welch(v1: list[float], v2: list[float]) -> dict:
    """Welch's unequal-variance t-test. Returns t, df, and the two-tailed p."""
    n1, n2 = len(v1), len(v2)
    m1, m2 = sum(v1) / n1, sum(v2) / n2
    s1 = sum((v - m1) ** 2 for v in v1) / (n1 - 1)
    s2 = sum((v - m2) ** 2 for v in v2) / (n2 - 1)
    se2 = s1 / n1 + s2 / n2
    if se2 <= 0:
        return {"t": float("inf"), "df": float(n1 + n2 - 2), "p": 0.0,
                "mean1": m1, "mean2": m2, "n1": n1, "n2": n2}
    t = (m1 - m2) / math.sqrt(se2)
    df = se2 ** 2 / ((s1 / n1) ** 2 / (n1 - 1) + (s2 / n2) ** 2 / (n2 - 1))
    p = _betai(df / 2.0, 0.5, df / (df + t * t))
    return {"t": t, "df": df, "p": p, "mean1": m1, "mean2": m2, "n1": n1, "n2": n2}


def stars(p: float) -> str:
    return "****" if p < 1e-4 else "***" if p < 1e-3 else "**" if p < 0.01 \
        else "*" if p < 0.05 else "ns"


def pairwise_stats(rows: list[dict], intensities=None) -> list[dict]:
    """Every rescue arm vs every null arm, plus the two rescue arms against each other,
    at each reported intensity."""
    out = []
    for x_log in (REPORT_INTENSITIES if intensities is None else intensities):
        out += _stats_at(rows, x_log)
    return out


def _stats_at(rows: list[dict], x_log: float) -> list[dict]:
    vals: dict[str, list[float]] = {}
    for r in rows:
        if r["intensity_log_cd_s_m2"] == x_log:
            vals.setdefault(r["condition"], []).append(r["b_wave_uv"])
    out = []
    # Each rescue arm vs each null arm, then the two rescue arms against each other.
    pairs = [(a, b) for a in RESCUE_GROUPS for b in NULL_GROUPS]
    pairs.append((RESCUE_GROUPS[1], RESCUE_GROUPS[0]))   # 3'UTR vs plain RK-PDE6B
    for a, b in pairs:
            w = welch(vals[a], vals[b])
            out.append({
                "intensity_log_cd_s_m2": x_log,
                "group_a": a, "group_b": b,
                "n_a": w["n1"], "n_b": w["n2"],
                "mean_a_uv": round(w["mean1"], 2), "mean_b_uv": round(w["mean2"], 2),
                "difference_uv": round(w["mean1"] - w["mean2"], 2),
                "t": round(w["t"], 3), "df": round(w["df"], 2),
                "p_value": float(f"{w['p']:.3g}"), "significance": stars(w["p"]),
            })
    return out


def verify(summary: list[dict], rows: list[dict]) -> list[str]:
    """Assert the biology the mock is supposed to show. Returns a list of failure strings.

    These are the claims the figure makes, so they are checked rather than eyeballed -- a
    retune of CONDITIONS that breaks one should fail loudly instead of shipping a plot that
    quietly says the wrong thing.
    """
    at = {}
    for r in summary:
        at.setdefault(r["intensity_log_cd_s_m2"], {})[r["condition"]] = r["mean_b_wave_uv"]
    fails: list[str] = []

    for x_log in sorted(at):
        d = at[x_log]
        worst_null = max(d[g] for g in NULL_GROUPS)
        # 1. Control is the healthy ceiling.
        if not d["Control"] > d["AAV8-RK-PDE6B-3UTR"]:
            fails.append(f"log {x_log}: Control not above the 3'UTR arm")
        # 2. The 3'UTR arm rescues more than PDE6B alone, from the threshold up (below it
        #    both sit at the noise floor, where noise decides the order).
        if x_log >= REFERENCE_LOG_I and not d["AAV8-RK-PDE6B-3UTR"] > d["AAV8-RK-PDE6B"]:
            fails.append(f"log {x_log}: 3'UTR not above AAV8-RK-PDE6B")
        # 3. PDE6B alone still shows real rescue over every null, from the threshold up.
        #    Below flash 1.0 every rd10 arm is at the noise floor by design (check 7), so
        #    there is no separation to assert there.
        if x_log >= REFERENCE_LOG_I and not d["AAV8-RK-PDE6B"] > worst_null + NOISE_BAND_UV:
            fails.append(f"log {x_log}: AAV8-RK-PDE6B not clearly above the nulls "
                         f"({d['AAV8-RK-PDE6B']:.1f} vs {worst_null:.1f} uV)")

    # 4. The requested change: CMV-GFP must read as a null at the reference intensity,
    #    not level with a treated arm.
    ref = at[REFERENCE_LOG_I]
    if ref["AAV8-CMV-GFP"] > ref["Untreated"] + NOISE_BAND_UV:
        fails.append(f"log {REFERENCE_LOG_I}: AAV8-CMV-GFP reads above Untreated "
                     f"({ref['AAV8-CMV-GFP']:.1f} vs {ref['Untreated']:.1f} uV) -- it is a "
                     f"GFP-only control and must not show rescue")

    # 5. Every condition rises with flash intensity. The allowed dip scales with amplitude:
    #    3 uV is noise on a 230 uV Control trace but a real reversal on a 15 uV null curve,
    #    and a flat tolerance would either miss the second or fail on the first.
    for label, *_ in CONDITIONS:
        series = [at[x][label] for x in sorted(at)]
        if series[-1] <= series[0]:
            fails.append(f"{label}: does not rise across the intensity ladder")
        for k in range(len(series) - 1):
            tol = max(2.0, 0.04 * series[k])
            if series[k + 1] < series[k] - tol:
                fails.append(f"{label}: drops {series[k]:.1f} -> {series[k+1]:.1f} uV "
                             f"between flashes {k+1} and {k+2}")

    # 6. Both rescue arms must beat every null arm *significantly*, not just numerically.
    #    A mock whose rescue is visible to the eye but not to a t-test would misrepresent
    #    the result the figure is meant to stand in for.
    lo, hi = SLIGHT_P_BAND
    for st in pairwise_stats(rows):
        a, b, p, xi = st["group_a"], st["group_b"], st["p_value"], st["intensity_log_cd_s_m2"]
        if b in NULL_GROUPS:
            if p >= ALPHA:
                fails.append(f"{a} vs {b} at log {xi}: not significant "
                             f"(p={p:.3g}, n={st['n_a']}/{st['n_b']})")
        else:
            # The graded rescue: significant, but only slightly.
            if p >= hi:
                fails.append(f"{a} vs {b} at log {xi}: not significant "
                             f"(p={p:.3g}) -- widen the gap between the two rescue arms")
            elif p < lo:
                fails.append(f"{a} vs {b} at log {xi}: separation is too strong to read "
                             f"as slight (p={p:.3g} < {lo}) -- narrow the gap between the "
                             f"two rescue arms")

    # 7. The rd10 threshold: every arm except the WT Control must sit at the noise floor
    #    below flash 1.0, which is what the real recordings show.
    for label, *_ in CONDITIONS:
        if label == "Control":
            continue
        for x_log in (x for x in at if x < REFERENCE_LOG_I):
            if at[x_log][label] > THRESHOLD_FLOOR_UV:
                fails.append(f"{label}: responds at log {x_log} "
                             f"({at[x_log][label]:.1f} uV) -- rd10 arms should be at the "
                             f"noise floor until flash {REFERENCE_LOG_I}")
    return fails


def points_wide(rows: list[dict]) -> tuple[list[list], list[list]]:
    """Replicates-as-columns layout: one row per intensity, one column per eye.

    This is the shape GraphPad/Excel expect when you want to paste raw replicates and have
    the tool compute mean + SEM itself. Two header rows (condition band, then sample_id),
    so it is for pasting rather than for programmatic parsing -- read
    `mock_fig1e_bwave_long.csv` for that.
    """
    eyes: list[tuple[str, str]] = []   # (condition, sample_id) in display order
    seen = set()
    for label, *_ in CONDITIONS:
        for r in rows:
            if r["condition"] == label and r["sample_id"] not in seen:
                seen.add(r["sample_id"])
                eyes.append((label, r["sample_id"]))

    head1 = ["", ""] + [c for c, _ in eyes]
    head2 = ["intensity_log_cd_s_m2", "intensity_group"] + [s for _, s in eyes]

    by_key = {(r["sample_id"], r["intensity_group"]): r["b_wave_uv"] for r in rows}
    body = []
    for group, x_log in enumerate(INTENSITIES_LOG, start=1):
        body.append([x_log, group] + [by_key[(s, group)] for _, s in eyes])
    return [head1, head2], body


def write_csv(path: Path, header: list[str], rows) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        # lineterminator: csv defaults to CRLF, which git would normalise on commit -- the
        # committed bytes would then differ from freshly generated ones, breaking the
        # "same seed reproduces byte-for-byte" guarantee.
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    print(f"  wrote {path.name}  ({len(rows)} rows)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seed", type=int, default=20260802,
                    help="RNG seed; same seed reproduces identical CSVs (default: 20260802)")
    ap.add_argument("--outdir", type=Path, default=Path(__file__).parent,
                    help="directory to write the CSVs into (default: alongside this script)")
    ap.add_argument("--n-eyes", type=int, default=None, metavar="N",
                    help="force every condition to N eyes (default: the real per-group counts)")
    ap.add_argument("--cv", type=float, default=None, metavar="C",
                    help=f"force one eye-to-eye CV across all conditions "
                         f"(suggested: {UNIFORM_CV} -- a visible but moderate spread)")
    args = ap.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    rows = build_rows(args.seed, n_eyes_override=args.n_eyes, cv_override=args.cv)
    summary = summarise(rows)

    fails = verify(summary, rows)
    if fails:
        print("  SELF-CHECK FAILED -- nothing written:")
        for f in fails:
            print(f"    - {f}")
        raise SystemExit(1)
    print("  self-check passed (condition ordering + CMV-GFP null + monotonic rise)")

    long_cols = ["sample_id", "animal", "eye", "condition", "condition_order",
                 "intensity_group", "intensity_log_cd_s_m2", "b_wave_uv"]
    write_csv(args.outdir / "mock_fig1e_bwave_long.csv", long_cols,
              [[r[c] for c in long_cols] for r in rows])

    sum_cols = ["condition", "condition_order", "intensity_group", "intensity_log_cd_s_m2",
                "n_eyes", "mean_b_wave_uv", "sd_uv", "sem_uv"]
    write_csv(args.outdir / "mock_fig1e_bwave_summary.csv", sum_cols,
              [[r[c] for c in sum_cols] for r in summary])

    header, body = widen(summary)
    write_csv(args.outdir / "mock_fig1e_bwave_wide.csv", header, body)

    heads, pbody = points_wide(rows)
    path = args.outdir / "mock_fig1e_bwave_points_wide.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerows(heads)
        w.writerows(pbody)
    print(f"  wrote {path.name}  ({len(pbody)} rows x {len(heads[1]) - 2} eyes)")

    stats = pairwise_stats(rows)
    stat_cols = ["intensity_log_cd_s_m2", "group_a", "group_b", "n_a", "n_b",
                 "mean_a_uv", "mean_b_uv", "difference_uv", "t", "df",
                 "p_value", "significance"]
    write_csv(args.outdir / "mock_fig1e_bwave_stats.csv", stat_cols,
              [[s[c] for c in stat_cols] for s in stats])

    for xi in REPORT_INTENSITIES:
        print(f"\n  Welch t-tests at {xi} log cd.s/m2 (SIMULATED):")
        for s in (s for s in stats if s["intensity_log_cd_s_m2"] == xi):
            print(f"    {s['group_a']:<20} vs {s['group_b']:<26} "
                  f"p={s['p_value']:<9.3g} {s['significance']}")

    # Sanity readout at the Fig 1E reference intensity -- the ordering that must hold.
    for xi in REPORT_INTENSITIES:
        print(f"\n  b-wave at {xi} log cd.s/m2 (SIMULATED):")
        ref = sorted((r for r in summary if r["intensity_log_cd_s_m2"] == xi),
                     key=lambda r: -r["mean_b_wave_uv"])
        for r in ref:
            print(f"    {r['condition']:<28} {r['mean_b_wave_uv']:>7.1f} "
                  f"+/- {r['sem_uv']:.1f} uV  (n={r['n_eyes']})")


if __name__ == "__main__":
    main()
