"""Real slope engine — a long-form table → one line per subject between two conditions.

Needs four things and guesses none of the ones that would change the meaning: a ``subject`` column
(what makes two rows the same individual), a ``condition`` column with exactly two levels drawn, a
numeric ``value``, and optionally a ``group`` column that clusters subjects along x.

**Incomplete pairs are dropped, counted, and named** rather than imputed or silently ignored.
cnsplots raises on the first subject that lacks one condition, which is correct for a curated
dataframe and useless on a real export where a handful of animals were not measured at both time
points. The count reaches the reader in the figure's caption, so "n=18 pairs" is never quietly
"n=30 subjects".
"""

from skills._stats import parse_list
from skills.slope.run import slope_spec


def run(data_path: str, params: dict) -> dict:
    import pandas as pd

    low = str(data_path).lower()
    if low.endswith((".xlsx", ".xls")):
        df = pd.read_excel(data_path)
    else:
        df = pd.read_csv(data_path, sep="\t" if low.endswith(".tsv") else ",")

    subject_col = _required(df, params.get("subject"), "subject")
    condition_col = _required(df, params.get("condition"), "condition")
    value_col = _value_column(df, params, exclude=(subject_col, condition_col))
    group_col = _optional(df, params.get("group"))

    sub = pd.DataFrame({
        "s": df[subject_col].astype(str),
        "c": df[condition_col].astype(str),
        "v": pd.to_numeric(df[value_col], errors="coerce"),
        "g": (df[group_col].astype(str) if group_col else ""),
    }).dropna(subset=["v"])
    if sub.empty:
        raise ValueError(f"slope: no rows with a numeric {value_col!r}")

    levels = _levels(sub, params, condition_col)
    sub = sub[sub["c"].isin(levels)]

    # A subject measured twice at the SAME condition is not a pair — it is a replicate, and there
    # is no defensible way to pick which of the two the line should start at. Averaging them would
    # silently turn a replicated design into a paired one, so it is refused by name.
    duplicated = sub.duplicated(subset=["s", "c"]).any()
    if duplicated:
        raise ValueError(
            f"slope: some {subject_col!r} values appear more than once at the same "
            f"{condition_col!r} level. A slope chart needs ONE value per subject per condition — "
            "aggregate the replicates first, or pick the column that identifies a single measurement."
        )

    wide = sub.pivot(index="s", columns="c", values="v")
    group_of = dict(zip(sub["s"], sub["g"])) if group_col else {}

    paired: dict = {}
    complete = incomplete = 0
    for subject, row in wide.iterrows():
        before, after = row.get(levels[0]), row.get(levels[1])
        if _missing(before) or _missing(after):
            incomplete += 1
            continue
        key = group_of.get(subject, "") if group_col else "all"
        paired.setdefault(str(key), {})[str(subject)] = (float(before), float(after))
        complete += 1
    if not complete:
        raise ValueError(
            f"slope: no {subject_col!r} has a value at both {levels[0]!r} and {levels[1]!r} — "
            "nothing is paired"
        )

    title = f"{value_col}: {levels[0]} to {levels[1]}"
    if incomplete:
        title += f" ({complete} paired, {incomplete} incomplete excluded)"
    spec = slope_spec(paired, levels, {**params, "_grouped": bool(group_col)},
                      str(value_col), str(group_col or ""), title)
    return spec


def _missing(v) -> bool:
    return v is None or v != v      # NaN is the only value not equal to itself


def _levels(sub, params: dict, condition_col: str) -> list:
    """The two condition levels to draw, in order. Explicit ``levels`` wins; otherwise the first two
    in order of appearance — and more than two present is REPORTED, never silently truncated, since
    which two got picked determines the entire figure."""
    observed = list(dict.fromkeys(sub["c"].tolist()))
    requested = parse_list(params.get("levels"))
    if requested:
        missing = [level for level in requested if level not in observed]
        if missing:
            raise ValueError(
                f"slope: {condition_col!r} has no level(s) {', '.join(map(repr, missing))} "
                f"(available: {', '.join(observed)})"
            )
        if len(requested) != 2:
            raise ValueError(
                f"slope: `levels` must name exactly two conditions, got {len(requested)}"
            )
        return requested[:2]
    if len(observed) < 2:
        raise ValueError(
            f"slope: {condition_col!r} has only {len(observed)} level(s); a paired chart needs two"
        )
    if len(observed) > 2:
        raise ValueError(
            f"slope: {condition_col!r} has {len(observed)} levels ({', '.join(observed[:6])}"
            f"{'…' if len(observed) > 6 else ''}). Name the two to compare with "
            "`levels`, e.g. levels=\"" + f"{observed[0]}, {observed[1]}" + "\" — picking two "
            "silently would decide the whole result."
        )
    return observed[:2]


def _required(df, requested, role: str):
    name = str(requested or "").strip()
    if not name:
        raise ValueError(
            f"slope needs a {role} column — it cannot be guessed, because guessing it wrong "
            f"pairs the wrong rows (available: {', '.join(map(str, df.columns))})"
        )
    col = {str(c).strip().lower(): c for c in df.columns}.get(name.lower())
    if col is None:
        raise ValueError(
            f"slope: no such {role} column {name!r} "
            f"(available: {', '.join(map(str, df.columns))})"
        )
    return col


def _optional(df, requested):
    name = str(requested or "").strip()
    if not name:
        return None
    col = {str(c).strip().lower(): c for c in df.columns}.get(name.lower())
    if col is None:
        raise ValueError(
            f"slope: no such group column {name!r} "
            f"(available: {', '.join(map(str, df.columns))})"
        )
    return col


def _value_column(df, params: dict, exclude=()):
    import pandas as pd

    name = str(params.get("value") or "").strip()
    if name:
        col = {str(c).strip().lower(): c for c in df.columns}.get(name.lower())
        if col is None:
            raise ValueError(
                f"slope: no such value column {name!r} "
                f"(available: {', '.join(map(str, df.columns))})"
            )
        return col
    numeric = [c for c in df.columns
               if c not in exclude and pd.api.types.is_numeric_dtype(df[c])]
    if not numeric:
        raise ValueError("slope needs a numeric value column")
    return numeric[0]
