"""Render the cnsplots side of the Phase-F parity audit.

Throwaway, outside the repo (spec §1 Notes): cnsplots pulls matplotlib/seaborn/lifelines/biopython
and none of that belongs in Selom's shared .venv.

It reads the EXACT arrays Selom's own skills produced (selom-data.json), so the two sides differ
only in how they are drawn. Same numbers, same canvas (6.0 x 4.5 in @ 200 dpi), two renderers.
"""

import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import cnsplots as cns

AUDIT = sys.argv[1]
D = json.load(open(f"{AUDIT}/selom-data.json"))
FIGSIZE, DPI = (6.0, 4.5), 200

# cnsplots is tuned for a 150pt (~2.1in) panel at 8pt type. On the audit's 6x4.5in canvas that
# type would be unreadably small, so type is scaled to the canvas by the same factor throughout.
# The RATIOS the audit compares (title:tick, tick length:width, spine weight) are preserved.
K = 2.4
TITLE_FS, LEG_FS, LW = 8 * K, 7 * K, 0.5 * K
cns.setup_matplotlib(title_fontsize=TITLE_FS, legend_fontsize=LEG_FS, axes_linewidth=LW)
STYLE = dict(title_fontsize=TITLE_FS, legend_fontsize=LEG_FS, axes_linewidth=LW)


def save(fig, name):
    for ext in ("png", "svg"):
        fig.savefig(f"{AUDIT}/cnsplots/{name}.{ext}", dpi=DPI, bbox_inches="tight",
                    pad_inches=0.02, transparent=False, facecolor="white")
    plt.close(fig)
    print(f"[cns] {name}")


# ---- box ---------------------------------------------------------------------------------------
d = D["box"]
rows = [{"condition": t["name"], "value": v} for t in d["traces"] for v in t["y"] if v is not None]
df = pd.DataFrame(rows)
fig, ax = plt.subplots(figsize=FIGSIZE)
cns.boxplot(data=df, x="condition", y="value", showoutliers=True, add_count=True, ax=ax,
            order=[t["name"] for t in d["traces"]])
ax.set_ylabel(d["ytitle"] or "")
ax.set_xlabel(d["xtitle"] or "")
ax.set_title(d["title"] or "")
plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
cns.setup_ax(ax, **STYLE)
save(fig, "box")

# ---- scatter (PCA) -----------------------------------------------------------------------------
d = D["scatter"]
rows = [{"x": xx, "y": yy, "group": t.get("name"), "label": lb}
        for t in d["traces"]
        for xx, yy, lb in zip(t["x"], t["y"], t.get("text") or [""] * len(t["x"]))]
df = pd.DataFrame(rows)
fig, ax = plt.subplots(figsize=FIGSIZE)
cns.scatterplot(data=df, x="x", y="y", hue="group", s=28, ax=ax)
for _, r in df.iterrows():
    ax.annotate(r["label"], (r["x"], r["y"]), fontsize=LEG_FS,
                xytext=(3, 3), textcoords="offset points")
ax.set_xlabel(d["xtitle"] or "")
ax.set_ylabel(d["ytitle"] or "")
ax.set_title(d["title"] or "")
ax.legend(title="group")
cns.setup_ax(ax, **STYLE)
save(fig, "scatter")

# ---- heatmap: identical z matrix, numeric cluster order ----------------------------------------
# Drawn with imshow + setup_ax rather than cns.heatmapplot: that one takes an AnnData and builds
# its own clustered figure, which would compare two different FIGURES rather than two renderings
# of the same matrix. setup_ax is the cnsplots styling layer either way — the thing being audited.
d = D["heatmap"]
tr = d["traces"][0]
order = sorted(range(len(tr["x"])), key=lambda i: int(tr["x"][i]))
z = np.array([[row[i] for i in order] for row in tr["z"]], dtype=float)
fig, ax = plt.subplots(figsize=FIGSIZE)
im = ax.imshow(z, aspect="auto", cmap="RdBu_r", interpolation="nearest")
ax.set_xticks(range(len(order)), [tr["x"][i] for i in order])
ax.set_yticks(range(len(tr["y"])), tr["y"])
ax.set_xlabel(d["xtitle"] or "")
ax.set_ylabel(d["ytitle"] or "")
ax.set_title(d["title"] or "")
cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
cb.set_label("z-score", fontsize=TITLE_FS)
cns.setup_ax(ax, colorbar_label="", **STYLE)
save(fig, "heatmap")

# ---- volcano: identical points, cnsplots' own volcanoplot --------------------------------------
d = D["volcano"]
rows = [{"symbol": lb or "", "log2FoldChange": xx, "-log10(adjp)": yy}
        for t in d["traces"]
        for xx, yy, lb in zip(t["x"], t["y"], t.get("text") or [None] * len(t["x"]))]
df = pd.DataFrame(rows)
fig, ax = plt.subplots(figsize=FIGSIZE)
cns.volcanoplot(data=df, x="log2FoldChange", y="-log10(adjp)", symbol="symbol", n_show=10, ax=ax)
ax.set_title(d["title"] or "")
cns.setup_ax(ax, **STYLE)
save(fig, "volcano")

# ---- dotplot: identical enrichment rows --------------------------------------------------------
d = D["dotplot"]
tr = d["traces"][0]
mk = tr.get("marker") or {}
sizes = mk.get("size")
colors = mk.get("color")
fig, ax = plt.subplots(figsize=FIGSIZE)
sc = ax.scatter(tr["x"], tr["y"],
                s=[s * 90 for s in sizes] if isinstance(sizes, list) else 90,
                c=colors if isinstance(colors, list) else "#444",
                cmap="viridis", edgecolors="none")
ax.set_xlabel(d["xtitle"] or "")
ax.set_title(d["title"] or "")
cb = fig.colorbar(sc, ax=ax, fraction=0.03, pad=0.02)
cb.set_label("-log10 padj", fontsize=TITLE_FS)
h, lab = sc.legend_elements(prop="sizes", num=3, alpha=0.7)
ax.legend(h, lab, title="genes", loc="lower right")
cns.setup_ax(ax, colorbar_label="", **STYLE)
save(fig, "dotplot")
print("[cns] done")
