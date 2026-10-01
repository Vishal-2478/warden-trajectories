#!/usr/bin/env python3
"""Turn trajectory_analysis.py output into LaTeX, so no number is ever typed by hand.

usage: python make_tables.py OUT_DIR GEN_DIR PERM
writes GEN_DIR/numbers.tex   \newcommand macros for every statistic
       GEN_DIR/tab_traj.tex  rows for the cross-cue table (consequence - observation)
       GEN_DIR/tab_perarm.tex rows for the per-arm table
       GEN_DIR/tab_ladder.tex rows for the control-ladder table
"""
import re, sys
from pathlib import Path
import pandas as pd

out, gen, perm = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
gen.mkdir(parents=True, exist_ok=True)
pa = pd.read_csv(out / "per_arm.csv")
did = pd.read_csv(out / "did.csv")
cen = pd.read_csv(out / "censoring.csv")
FLOOR = 1 / (perm + 1)
MODELS = ["Qwen2.5-7B", "Qwen2.5-14B", "Phi-4"]
MODELS = [m for m in MODELS if m in set(pa.model)] + [m for m in pa.model.unique() if m not in MODELS]
ARMS = ["inert", "observation", "salience", "consequence"]
SHORT = {"inert": "Inert", "observation": "Obs", "salience": "Sal", "consequence": "Cons"}
SCOPE = {"all": "All", "matched": "Matched", "submitted": "Sub"}
NUM = {"7": "Seven", "14": "Fourteen", "4": "Four", "2": "Two", "5": "Five"}

def mname(m):
    m = re.sub(r"(\d+)", lambda x: NUM.get(x.group(1), "N"), m.replace("Qwen2.5", "Qwen"))
    return re.sub(r"[^A-Za-z]", "", m)

def fp(p):                       # permutation p
    if p <= FLOOR * 1.0001:
        return rf"$\le${FLOOR:.4f}".replace("0.0001", r"$10^{-4}$").replace(r"$\le$$10^{-4}$", r"$\le\!10^{-4}$")
    return f"{p:.4f}" if p < 0.01 else f"{p:.3f}"

def fh(p):                       # Holm-adjusted
    if pd.isna(p): return "---"
    return r"$<$0.001" if p < 0.001 else (f"{p:.4f}" if p < 0.01 else f"{p:.3f}")

def fz(z): return f"{z:+.2f}"
def fj(x): return f"{x:.5f}"
def fd(x): return f"{x:+.5f}"

macros = []
def mac(name, val): macros.append(rf"\newcommand{{\{name}}}{{{val}}}")

# ---- per-arm macros
for _, r in pa.iterrows():
    b = f"Arm{mname(r.model)}{SHORT[r.arm]}{SCOPE[r.scope]}"
    mac(b + "JSD", fj(r.jsd)); mac(b + "Nmon", int(r.n_mon)); mac(b + "Nunmon", int(r.n_unmon))
    for s in ("free", "paired"):
        S = s.capitalize()
        mac(b + S + "P", fp(r[f"p_{s}"])); mac(b + S + "Z", fz(r[f"z_{s}"]))
        mac(b + S + "Pholm", fh(r[f"p_{s}_holm"]))
# ---- DiD macros
for _, r in did.iterrows():
    bb, aa = [x.strip() for x in r.comparison.split("-")]
    b = f"Did{mname(r.model)}{SHORT[bb]}{SHORT[aa]}{SCOPE[r.scope]}{r.scheme.capitalize()}"
    mac(b + "Delta", fd(r.delta)); mac(b + "Z", fz(r.z)); mac(b + "P", fp(r.p)); mac(b + "Pholm", fh(r.p_holm))
    mac(b + "Zabs", f"{abs(r.z):.1f}"); mac(b + "JSDa", fj(r.jsd_a)); mac(b + "JSDb", fj(r.jsd_b))
# ---- censoring macros
for _, r in cen[cen.condition.isin(["monitored", "unmonitored"])].iterrows():
    b = f"Cen{mname(r.model)}{SHORT[r.arm]}{'Mon' if r.condition == 'monitored' else 'Unmon'}"
    mac(b + "Sub", f"{100 * r.submitted:.1f}\\%"); mac(b + "Budget", f"{100 * r.hit_step_budget:.1f}\\%")
for _, r in cen[cen.condition.str.startswith("Fisher")].iterrows():
    mac(f"Cen{mname(r.model)}{SHORT[r.arm]}FisherP", f"{r.submitted:.3f}")
mac("PermN", f"{perm:,}".replace(",", "{,}")); mac("PermFloor", f"{FLOOR:.4f}")
(gen / "numbers.tex").write_text("\n".join(macros) + "\n", encoding="utf-8")

# ---- cross-cue table (paper Table 4): consequence - observation
rows = []
for m in MODELS:
    for sc in ("all", "matched"):
        f = did[(did.model == m) & (did.comparison == "consequence - observation") & (did.scope == sc)]
        if f.empty: continue
        fr, pr = f[f.scheme == "free"].iloc[0], f[f.scheme == "paired"].iloc[0]
        rows.append(f"{m} & {'all' if sc == 'all' else 'matched'} & {fj(fr.jsd_a)} & "
                    f"{fj(fr.jsd_b)} & ${fd(fr.delta)}$ & ${fz(fr.z)}$ & {fp(fr.p)} & {fh(fr.p_holm)} & {fp(pr.p)} \\\\")
(gen / "tab_traj.tex").write_text("\n".join(rows) + "\n", encoding="utf-8")

# ---- per-arm table
rows = []
for m in MODELS:
    for a in ARMS:
        g = pa[(pa.model == m) & (pa.arm == a)]
        if g.empty: continue
        A, M = g[g.scope == "all"].iloc[0], g[g.scope == "matched"].iloc[0]
        rows.append(f"{m} & {a} & {fj(A.jsd)} & {fp(A.p_free)} & {fp(A.p_paired)} & "
                    f"{fj(M.jsd)} & {fp(M.p_free)} & {fp(M.p_paired)} \\\\")
    rows.append(r"\addlinespace")
(gen / "tab_perarm.tex").write_text("\n".join(rows[:-1]) + "\n", encoding="utf-8")

# ---- ladder table: X - inert, consequence - salience; paired primary, free alongside
rows = []
for m in MODELS:
    for comp in ("observation - inert", "salience - inert", "consequence - inert", "consequence - salience"):
        for sc in ("matched", "all"):
            f = did[(did.model == m) & (did.comparison == comp) & (did.scope == sc)]
            if f.empty: continue
            pr, fr = f[f.scheme == "paired"].iloc[0], f[f.scheme == "free"].iloc[0]
            rows.append(f"{m} & {comp.replace(' - ', ' $-$ ')} & {'matched' if sc == 'matched' else 'all'} & "
                        f"${fd(pr.delta)}$ & ${fz(pr.z)}$ & {fp(pr.p)} & {fh(pr.p_holm)} & {fp(fr.p)} \\\\")
    if rows and rows[-1] != r"\addlinespace": rows.append(r"\addlinespace")
if rows and rows[-1] == r"\addlinespace": rows = rows[:-1]
(gen / "tab_ladder.tex").write_text("\n".join(rows) + "\n", encoding="utf-8")
print(f"wrote {len(macros)} macros and 3 tables to {gen}")
