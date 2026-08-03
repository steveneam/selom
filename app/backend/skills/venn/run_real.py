"""Real Venn engine (pandas).

Reads the same boolean membership matrix as ``upset`` (first column = element id, the
rest = sets) and derives the DISTINCT regions: each element is counted once, in the
region of exactly the sets it belongs to. That is the only counting a Venn can honestly
display — the drawn areas are disjoint, so an "at least these sets" (inclusive) count
would make the printed numbers sum past the union.

Set selection, when the matrix carries more than three columns: ``sets`` names them
explicitly, otherwise the three largest are taken and the figure SAYS SO in its title.
A silent truncation here is the exact failure the skill exists to avoid — a reader
cannot tell a 3-of-9 view from a complete one.
"""

from skills._plotly import jsonable
from skills.upset.run_real import _as_member
from skills.venn.run import venn_spec


def run(data_path: str, params: dict) -> dict:
    import pandas as pd

    low = str(data_path).lower()
    if low.endswith((".xlsx", ".xls")):
        df = pd.read_excel(data_path, index_col=0)
    else:
        df = pd.read_csv(data_path, sep="\t" if low.endswith(".tsv") else ",", index_col=0)

    if df.shape[1] < 2:
        raise ValueError("venn needs a membership matrix with at least two set columns")

    membership = pd.DataFrame({col: _as_member(df[col], pd) for col in df.columns})
    chosen, note = _choose_sets(membership, params)

    counts: dict[tuple, int] = {}
    for _, row in membership[chosen].iterrows():
        region = tuple(c for c in chosen if row[c])
        if region:
            counts[region] = counts.get(region, 0) + 1

    title = "Set overlap" + note
    return jsonable(venn_spec(counts, chosen, params, title))


def _choose_sets(membership, params) -> tuple[list, str]:
    """Pick the 2–3 columns to draw, and the title note that keeps the choice visible."""
    columns = list(membership.columns)
    requested = str(params.get("sets") or "").strip()
    if requested:
        names = [s.strip() for s in requested.split(",") if s.strip()]
        missing = [n for n in names if n not in columns]
        if missing:
            raise ValueError(
                f"venn: no such set column(s): {', '.join(missing)} "
                f"(available: {', '.join(map(str, columns))})"
            )
        if len(names) not in (2, 3):
            raise ValueError(f"venn: name 2 or 3 sets, got {len(names)} — use `upset` for more")
        return names, ""

    if len(columns) <= 3:
        return columns, ""
    sizes = {c: int(membership[c].sum()) for c in columns}
    top = sorted(columns, key=lambda c: (-sizes[c], columns.index(c)))[:3]
    return top, f" — 3 largest of {len(columns)} sets"
