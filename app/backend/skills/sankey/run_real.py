"""Real sankey engine (pandas) — a long edge table -> flow diagram.

Reads a CSV/TSV/XLSX of edges. Columns are resolved flexibly: ``source``/``from``/``src``
and ``target``/``to``/``dst`` (else the first two columns); a ``value``/``count``/``weight``
column is summed per source→target pair, or pairs are counted when none is present. The
largest ``max_links`` flows are kept and their nodes indexed for the shared ``sankey_spec``.
"""

from skills._plotly import jsonable
from skills.sankey.run import sankey_spec


def _pick(cols: dict, names, default):
    for n in names:
        if n in cols:
            return cols[n]
    return default


def run(data_path: str, params: dict) -> dict:
    import pandas as pd

    low = str(data_path).lower()
    if low.endswith((".xlsx", ".xls")):
        df = pd.read_excel(data_path)
    else:
        df = pd.read_csv(data_path, sep="\t" if low.endswith(".tsv") else ",")
    if df.shape[1] < 2:
        raise ValueError("sankey needs at least a source and a target column")

    cols = {str(c).lower(): c for c in df.columns}
    s_col = _pick(cols, ("source", "from", "src"), df.columns[0])
    t_col = _pick(cols, ("target", "to", "dst", "tgt"), df.columns[1])
    v_col = _pick(cols, ("value", "count", "n", "weight"), None)

    if v_col is not None:
        grouped = df.groupby([s_col, t_col], sort=False)[v_col].sum().reset_index()
        value_col = v_col
    else:  # no weight column -> count source->target occurrences
        grouped = df.groupby([s_col, t_col], sort=False).size().reset_index(name="__n")
        value_col = "__n"

    max_links = int(params.get("max_links", 60))
    grouped = grouped.sort_values(value_col, ascending=False).head(max_links)

    sources = grouped[s_col].astype(str).tolist()
    targets = grouped[t_col].astype(str).tolist()
    values = grouped[value_col].tolist()

    labels: list[str] = []
    idx: dict[str, int] = {}
    for lab in sources + targets:  # index only nodes that survived the cap (no orphans)
        if lab not in idx:
            idx[lab] = len(labels)
            labels.append(lab)

    src_i = [idx[s] for s in sources]
    tgt_i = [idx[t] for t in targets]
    return jsonable(sankey_spec(labels, src_i, tgt_i, values, "Sankey flow"))
