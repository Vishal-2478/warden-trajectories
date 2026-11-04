#!/usr/bin/env python3
"""Fig. 2 (revision): permutation nulls of trajectory difference-in-differences.

Changes requested by Reviewer 1 (comment 24): larger labels, a legend that
separates the observed statistic from the null distribution, the same
(rollout-paired) permutation scheme as Tables III-V, and no panel that relies on
the non-randomized observation arm.

usage: python make_figure_v2.py out/nulls.npz out/did.csv fig.pdf "MODEL|b-a|scope|scheme|title" ...
"""
import sys
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

INK, INK2, GRID = "#0b0b0b", "#52514e", "#d9d8d3"
NULL_FILL, BAND = "#b4b2a9", "#ecebe6"
npz, didcsv, out = sys.argv[1:4]
specs = [s.split("|") for s in sys.argv[4:]]
Z = np.load(npz); did = pd.read_csv(didcsv)
plt.rcParams.update({"font.family": "serif",
                     "font.serif": ["Times New Roman", "Liberation Serif", "Nimbus Roman", "TeX Gyre Termes", "Times", "DejaVu Serif"],
                     "mathtext.fontset": "stix", "pdf.fonttype": 42, "ps.fonttype": 42,
                     "font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.linewidth": 0.6,
                     "xtick.labelsize": 8.5})
fig, axes = plt.subplots(1, len(specs), figsize=(2.35 * len(specs), 1.62), squeeze=False, sharex=True)
lims = []
for ax, (model, comp, scope, scheme, title) in zip(axes[0], specs):
    b, a = comp.split("-")
    key = f"DID__{model}__{b}-{a}__{scope}__{scheme}".replace(" ", "")
    null = Z[key]
    row = did[(did.model == model) & (did.comparison == f"{b} - {a}") & (did.scope == scope) & (did.scheme == scheme)].iloc[0]
    obs, mu = row.delta, null.mean()
    lo95, hi95 = np.quantile(null, [0.025, 0.975])
    ax.axvspan(lo95, hi95, color=BAND, zorder=0, linewidth=0)
    ax.hist(null, bins=60, color=NULL_FILL, edgecolor="white", linewidth=0.3, zorder=1)
    ax.axvline(mu, color=INK2, linewidth=0.9, linestyle=(0, (2, 2)), zorder=2)
    ax.axvline(obs, color=INK, linewidth=1.6, zorder=3)
    p = row.p
    ptxt = "p < 0.001" if p < 0.001 else f"p = {p:.3f}"
    lab = f"z = {row.z:+.1f}, {ptxt}".replace("-", "−")
    ax.set_ylim(0, ax.get_ylim()[1] * 1.30)
    left = obs > mu
    ax.text(0.03 if left else 0.97, 0.96, lab, transform=ax.transAxes, ha="left" if left else "right",
            va="top", fontsize=8.5, color=INK, bbox=dict(boxstyle="square,pad=0.2", fc="white", ec="none", alpha=0.9))
    lims.append((min(null.min(), obs), max(null.max(), obs)))
    ax.set_title(title, fontsize=9, color=INK, loc="left")
    ax.set_xlabel(r"$\Delta$JSD (cue B $-$ cue A)")
    ax.set_yticks([])
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
lo = min(x for x, _ in lims); hi = max(y for _, y in lims); pad = 0.06 * (hi - lo)
axes[0][0].set_xlim(lo - pad, hi + pad)
handles = [Patch(facecolor=NULL_FILL, edgecolor="none", label="permutation null (no cue effect)"),
           Patch(facecolor=BAND, edgecolor="none", label="central 95% of the null"),
           Line2D([0], [0], color=INK2, lw=0.9, ls=(0, (2, 2)), label="null center (bias of JSD)"),
           Line2D([0], [0], color=INK, lw=1.6, label="observed difference")]
fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, fontsize=8.5,
           bbox_to_anchor=(0.5, -0.02), handlelength=1.6, columnspacing=1.2)
fig.tight_layout(rect=(0, 0.12, 1, 1))
fig.savefig(out, bbox_inches="tight", metadata={"CreationDate": None})
fig.savefig(out.replace(".pdf", ".png"), dpi=200, bbox_inches="tight")
print("saved", out)
