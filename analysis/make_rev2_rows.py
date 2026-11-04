#!/usr/bin/env python3
"""Table rows for the revision runs (marked c), from out_rev2/*.csv.
Writes res/tab_outcome_rev.tex, res/tab_perarm_rev.tex, res/tab_did_rev.tex.
usage: python3 analysis/make_rev2_rows.py out_rev2 RESDIR"""
import sys
from pathlib import Path

import pandas as pd

OUT, RES = Path(sys.argv[1]), Path(sys.argv[2])
SHORT = {"Qwen2.5-7B": "Qwen-7B", "Qwen2.5-14B": "Qwen-14B", "Phi-4": "Phi-4", "Mistral-7B": "Mistral-7B"}
NAME = {"observationR": r"obs.\ (rand.)$^{\mathrm{c}}$", "encoding": r"inert 2$^{\mathrm{c}}$"}
MORDER = {"Qwen2.5-7B": 0, "Qwen2.5-14B": 1, "Phi-4": 2, "Mistral-7B": 3}
AORDER = {"observationR": 0, "encoding": 1}


def fp(p):
    return r"$<$0.001" if p < 0.001 else f"{p:.3f}"


def sgn(x, d=3):
    return "$" + f"{x:+.{d}f}" + "$"


def ci(lo, hi, d=3):
    return f"[{lo:.{d}f}, {hi:.{d}f}]".replace("-", "$-$")


oc = pd.read_csv(OUT / "outcome_new.csv")
od = pd.read_csv(OUT / "outcome_did_new.csv")
oc = oc.assign(o1=oc.model.map(MORDER), o2=oc.arm.map(AORDER)).sort_values(["o2", "o1"])
lines = []
for r in oc.itertuples():
    d = od[(od.model == r.model) & (od.comparison == "observationR - inert")] if r.arm == "observationR" else od.iloc[0:0]
    did = (f"{sgn(d.did.iloc[0])} {ci(d.ci_lo.iloc[0], d.ci_hi.iloc[0])} & {fp(d.p.iloc[0])} & {fp(d.p_holm.iloc[0])}"
           if len(d) else r"--- & --- & ---")
    lines.append(f"{SHORT[r.model]} & {NAME[r.arm]} & {r.p_mon:.3f} & {r.p_unmon:.3f} & {sgn(r.diff)} "
                 f"{ci(r.ci_lo, r.ci_hi)} & {fp(r.p_holm)} & {did} \\\\")
(RES / "tab_outcome_rev.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

pa = pd.read_csv(OUT / "per_arm_new.csv")
pa = pa[pa.new & (pa.scope == "matched")]
pa = pa.assign(o1=pa.model.map(MORDER), o2=pa.arm.map(AORDER)).sort_values(["o2", "o1"])
lines = [f"{SHORT[r.model]} & {NAME[r.arm]} & {r.n_mon}/{r.n_unmon} & {r.jsd:.4f} & {sgn(r.z_paired, 2)} & "
         f"{fp(r.p_paired)} & {fp(r.p_paired_holm)} \\\\" for r in pa.itertuples()]
(RES / "tab_perarm_rev.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

dd = pd.read_csv(OUT / "did_new.csv")
dd = dd[(dd.scope == "matched") & (dd.scheme == "paired")]
want = [("observationR - inert", r"obs.\,(r.) $-$ inert$^{\mathrm{c}}$"),
        ("consequence - observationR", r"cons. $-$ obs.\,(r.)$^{\mathrm{c}}$"),
        ("consequence - encoding", r"cons. $-$ inert 2$^{\mathrm{c}}$")]
lines, first = [], True
for comp, label in want:
    g = dd[dd.comparison == comp].assign(o1=lambda x: x.model.map(MORDER)).sort_values("o1")
    if g.empty:
        continue
    if not first:
        lines.append(r"\addlinespace")
    first = False
    for r in g.itertuples():
        lines.append(f"{label} & {SHORT[r.model]} & {sgn(r.delta, 4)} & {sgn(r.z, 2)} & {fp(r.p)} & {fp(r.p_holm)} \\\\")
(RES / "tab_did_rev.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("wrote", *[p.name for p in RES.glob("tab_*_rev.tex")])
