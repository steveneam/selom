"""Shared helpers for emitting editable Plotly specs from Selom skills.

``jsonable`` converts a Plotly figure dict — which carries numpy arrays and, under
Plotly 6, base64 typed-array encoding (``{"dtype", "bdata", "shape"}``) — into plain
JSON arrays + native Python scalars. Every skill emits the SAME wire shape the
frontend and the MSW mock are built against, so a figure renders byte-for-byte the
same whether it came from a real runner or the offline stub.

This is the decoder first written for the scRNA UMAP engine, factored here so all
B2 skills reuse one implementation instead of duplicating it.
"""


def jsonable(obj):
    """Return ``obj`` with all numpy/Plotly-typed values reduced to plain JSON."""
    import numpy as np

    return _convert(obj, np)


def numeric_label_order(labels):
    """Indices that put ``labels`` in NUMERIC order when every label is a number written as a
    string, else ``None`` (leave the caller's order alone).

    Cluster ids reach a figure as strings (``adata.obs["leiden"].astype(str)``), and every default
    ordering in the stack — ``pandas.groupby``, ``sorted`` — is then LEXICOGRAPHIC: ``0, 1, 10, 11,
    …, 2, …, 9``. On a categorical axis that silently places cluster 10 between 1 and 11, so a
    reader decoding cluster identity from column position decodes it wrong (parity-audit D2).

    Returns indices rather than sorted labels because the caller almost always has a matrix to
    permute in step with them.
    """
    labels = list(labels)
    try:
        keys = [int(str(v)) for v in labels]
    except (TypeError, ValueError):
        return None
    if not keys:
        return None
    order = sorted(range(len(keys)), key=lambda i: keys[i])
    return None if order == list(range(len(keys))) else order


def _convert(obj, np):
    import base64

    if isinstance(obj, dict):
        # Plotly 6 base64 typed-array: decode back to a real coordinate list.
        if "bdata" in obj and "dtype" in obj:
            arr = np.frombuffer(base64.b64decode(obj["bdata"]), dtype=np.dtype(obj["dtype"]))
            shape = obj.get("shape")
            if shape is not None:
                arr = arr.reshape([int(s) for s in str(shape).split(",")])
            return arr.tolist()
        return {k: _convert(v, np) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_convert(v, np) for v in obj]
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.generic):
        return obj.item()
    return obj
