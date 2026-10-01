#!/usr/bin/env python3
"""Paper figure: permutation null of a trajectory difference-in-differences,
with the observed value marked. One panel per requested comparison.

usage: python make_figure.py OUT_DIR/nulls.npz OUT_DIR/did.csv fig.pdf \
          "Phi-4|consequence-observation|matched|free|(a) Consequence vs. observation" \
          ["Phi-4|consequence-inert|matched|free|(b) Consequence vs. inert"]
"""
import sys
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

INK, INK2, GRID = "#0b0b0b", "#52514e", "#d9d8d3"
NULL_FILL, OBS = "#b4b2a9", "#0b0b0b"          # grey null, black observed line (prints in greyscale)

npz, didcsv, out = sys.argv[1:4]
specs = [s.split("|") for s in sys.argv[4:]]
Z = np.load(npz); did = pd.read_csv(didcsv)

# IEEE template: 8-point Times for figure labels. The figure is drawn at its printed
# width (0.94 of the text width), so 8 pt here is 8 pt on the page. Fonts are
# embedded as TrueType (pdf.fonttype 42).
plt.rcParams.update({"font.family": "serif",
                     "font.serif": ["Times New Roman", "Liberation Serif", "Nimbus Roman", "TeX Gyre Termes",
                                    "Times", "DejaVu Serif"],
                     "mathtext.fontset": "stix", "pdf.fonttype": 42, "ps.fonttype": 42,
                     "font.size": 8, "axes.edgecolor": INK2,
                     "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
                     "axes.linewidth": 0.6})
fig, axes = plt.subplots(1, len(specs), figsize=(2.2 * len(specs), 1.55), squeeze=False, sharex=True)
lims = []
for ax, (model, comp, scope, scheme, title) in zip(axes[0], specs):
    b, a = comp.split("-")
    key = f"DID__{model}__{b}-{a}__{scope}__{scheme}".replace(" ", "")
    if key not in Z:
        sys.exit(f"missing null {key}; have e.g. {list(Z.keys())[:5]}")
    null = Z[key]
    row = did[(did.model == model) & (did.comparison == f"{b} - {a}") &
              (did.scope == scope) & (did.scheme == scheme)].iloc[0]
    obs, mu, sd = row.delta, null.mean(), null.std()
    ax.hist(null, bins=60, color=NULL_FILL, edgecolor="white", linewidth=0.3)
    ax.axvline(obs, color=OBS, linewidth=1.4)
    ax.axvline(mu, color=INK2, linewidth=0.8, linestyle=(0, (2, 2)))
    lab = (f"observed: {obs:+.4f}\n{row.z:+.1f} SD from null center").replace("-", "\u2212")
    ax.set_ylim(0, ax.get_ylim()[1] * 1.38)   # headroom so the label sits above the bars
    left = obs > mu                      # put the label on the side away from the line
    ax.text(0.02 if left else 0.98, 0.95, lab, transform=ax.transAxes,
            ha="left" if left else "right", va="top", fontsize=8,
            color=INK, bbox=dict(boxstyle="square,pad=0.25", fc="white", ec="none", alpha=0.9))
    lims.append((min(null.min(), obs), max(null.max(), obs)))
    ax.set_title(title, fontsize=8, color=INK, loc="left")
    ax.set_xlabel("Difference in divergence (permuted labels)")
    ax.set_yticks([])
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="x", color=GRID, linewidth=0.4)
    ax.set_axisbelow(True)
lo = min(a for a, b in lims); hi = max(b for a, b in lims); pad = 0.06 * (hi - lo)
axes[0][0].set_xlim(lo - pad, hi + pad)
fig.tight_layout()
fig.savefig(out, bbox_inches="tight", metadata={"CreationDate": None})  # reproducible bytes
fig.savefig(out.replace(".pdf", ".png"), dpi=200, bbox_inches="tight")
print("saved", out)
