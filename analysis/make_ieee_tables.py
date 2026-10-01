#!/usr/bin/env python3
"""Build the three compact tables of the IEEE conference version of the paper.

Every number comes from files in this repository:
  * data/<run>/episode_features.csv        (violation rates, recomputed here)
  * data/<run>/RESULTS.md                   (within-arm Holm p for the violation rate)
  * data/outcome_interactions/*.txt         (outcome-level difference-in-differences)
  * out/per_arm.csv, out/did.csv            (trajectory tests, from trajectory_analysis.py)

Table notes use superscript letters, as the IEEE conference template asks:
  a  the observation arm, whose surface text was not randomised;
  b  an inert arm that the model read as a statement about human review in its
     manipulation check (answers other than UNKNOWN in
     data/manipulation_checks/mancheck_neutral_*.json), and comparisons that use
     it as the reference.

Usage (from the repository root, after trajectory_analysis.py has written out/):
    python3 analysis/make_ieee_tables.py out results
"""
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

OUT, RES = Path(sys.argv[1]), Path(sys.argv[2])
RES.mkdir(parents=True, exist_ok=True)
D = Path("data")

RUNS = [  # model, arm, folder, reference-arm folder for the outcome DiD, interaction file stem
    ("Qwen2.5-7B", "inert", "qwen7b_neutral", None),
    ("Qwen2.5-7B", "observation", "qwen7b_hard450_calibrate", "Qwen2.5-7B_observation-vs-inert"),
    ("Qwen2.5-7B", "salience", "qwen7b_lexical", "Qwen2.5-7B_salience-vs-inert"),
    ("Qwen2.5-7B", "consequence", "qwen7b_stakes", "Qwen2.5-7B_consequence-vs-inert"),
    ("Qwen2.5-14B", "inert", "qwen14b_neutral", None),
    ("Qwen2.5-14B", "observation", "qwen14b_hard450_calibrate", "Qwen2.5-14B_observation-vs-inert"),
    ("Qwen2.5-14B", "consequence", "qwen14b_stakes", "Qwen2.5-14B_consequence-vs-inert"),
    ("Phi-4", "inert", "phi4_neutral", None),
    ("Phi-4", "observation", "phi4_hard450_calibrate", "Phi-4_observation-vs-inert"),
    ("Phi-4", "salience", "phi4_lexical", "Phi-4_salience-vs-inert"),
    ("Phi-4", "consequence", "phi4_stakes", "Phi-4_consequence-vs-inert"),
    ("Mistral-7B", "observation", "mistral7b_hard450_calibrate", None),
]
DAG = r"$^{\mathrm{a}}$"
DDAG = r"$^{\mathrm{b}}$"
INERT_CHECK = {"Qwen2.5-7B": "mancheck_neutral_qwen7b_neutral", "Qwen2.5-14B": "mancheck_neutral_qwen14b_neutral",
               "Phi-4": "mancheck_neutral_phi4_neutral"}


def inert_misread(model):
    """True if the model answered anything but UNKNOWN to the inert cue's manipulation check."""
    f = D / "manipulation_checks" / f"{INERT_CHECK[model]}.json"
    trials = json.loads(f.read_text(encoding="utf-8"))["trials"]
    return any(t["answer"] != "UNKNOWN" for t in trials if t["condition"] in ("monitored", "unmonitored"))


MISREAD = {m for m in INERT_CHECK if inert_misread(m)}
print("inert arm read as implying review:", sorted(MISREAD) or "none")
SHORT = {"Qwen2.5-7B": "Qwen-7B", "Qwen2.5-14B": "Qwen-14B", "Phi-4": "Phi-4", "Mistral-7B": "Mistral-7B"}
ABBR = {"inert": "inert", "observation": "obs.", "salience": "sal.", "consequence": "cons."}


def fp(p, floor=1e-4):
    if p <= floor + 1e-12:
        return r"$\le\!10^{-4}$"
    if p < 0.001:
        return r"$<$0.001"
    if p < 0.01:
        return f"{p:.4f}"
    return f"{p:.3f}"


def fp_exact(p):
    """p-values from exact tests (not permutation), so no permutation floor applies."""
    if p < 0.001:
        return r"$<$0.001"
    return f"{p:.3f}"


def sgn(x, d=3):
    s = f"{x:+.{d}f}"
    return "$" + s.replace("-", "-") + "$"


def holm(ps):
    ps = np.asarray(ps, float)
    order = np.argsort(ps)
    m = len(ps)
    adj = np.empty(m)
    run = 0.0
    for k, i in enumerate(order):
        run = max(run, (m - k) * ps[i])
        adj[i] = min(1.0, run)
    return adj


def within_arm_pholm(folder):
    """Holm-adjusted p for shortcut_sole_basis, monitored vs unmonitored, from RESULTS.md."""
    txt = (D / folder / "RESULTS.md").read_text(encoding="utf-8")
    sec = txt.split("## 2. monitored vs unmonitored", 1)[1]
    header = next(l for l in sec.splitlines() if l.startswith("| measure"))
    cols = [c.strip() for c in header.strip("|").split("|")]
    row = next(l for l in sec.splitlines() if l.startswith("| shortcut_sole_basis"))
    vals = [c.strip() for c in row.strip("|").split("|")]
    return float(vals[cols.index("p_holm")])


def interaction(stem):
    txt = (D / "outcome_interactions" / f"{stem}.txt").read_text(encoding="utf-8")
    row = next(l for l in txt.splitlines() if l.startswith("| shortcut_sole_basis"))
    vals = [c.strip() for c in row.strip("|").split("|")]
    return float(vals[4]), float(vals[5])  # interaction_DiD, perm_p


# ---------------- Table I: violation rate (P1) ----------------
rows, dids = [], []
for model, arm, folder, stem in RUNS:
    df = pd.read_csv(D / folder / "episode_features.csv")
    m = df.loc[df.condition == "monitored", "shortcut_sole_basis"].astype(float).mean()
    u = df.loc[df.condition == "unmonitored", "shortcut_sole_basis"].astype(float).mean()
    ph = within_arm_pholm(folder)
    did = interaction(stem) if stem else None
    rows.append(dict(model=model, arm=arm, m=m, u=u, ph=ph, did=did))
    if did:
        dids.append(did[1])
adj = iter(holm(dids))
lines, prev = [], None
for r in rows:
    if prev is not None and r["model"] != prev:
        lines.append(r"\addlinespace")
    prev = r["model"]
    arm = r["arm"] + (DAG if r["arm"] == "observation" else "") \
        + (DDAG if r["arm"] == "inert" and r["model"] in MISREAD else "")
    if r["did"]:
        d, p = r["did"]
        dtxt = sgn(d)[:-1] + r"^{\mathrm{b}}$" if r["model"] in MISREAD else sgn(d)
        didtxt = f"{dtxt} & {fp(p)} & {fp(next(adj))}"
    else:
        didtxt = r"--- & --- & ---"
    lines.append(f"{r['model']} & {arm} & {r['m']:.3f} & {r['u']:.3f} & {sgn(r['m']-r['u'])} & "
                 f"{fp_exact(r['ph'])} & {didtxt} \\\\")
(RES / "tab_outcome.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

# ---------------- Table II: per-arm trajectory tests (matched outcome, paired) ----------------
pa = pd.read_csv(OUT / "per_arm.csv")
pa = pa[pa.scope == "matched"]
order = {"inert": 0, "observation": 1, "salience": 2, "consequence": 3}
morder = {"Qwen2.5-7B": 0, "Qwen2.5-14B": 1, "Phi-4": 2}
pa = pa.assign(o1=pa.model.map(morder), o2=pa.arm.map(order)).sort_values(["o1", "o2"])
lines, prev = [], None
for r in pa.itertuples():
    if prev is not None and r.model != prev:
        lines.append(r"\addlinespace")
    prev = r.model
    arm = r.arm + (DAG if r.arm == "observation" else "") \
        + (DDAG if r.arm == "inert" and r.model in MISREAD else "")
    lines.append(f"{SHORT[r.model]} & {arm} & {r.n_mon}/{r.n_unmon} & {r.jsd:.4f} & {sgn(r.z_paired,2)} & "
                 f"{fp(r.p_paired)} & {fp(r.p_paired_holm)} \\\\")
(RES / "tab_perarm_ieee.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

# ---------------- Table III: trajectory DiD (matched outcome, paired) ----------------
dd = pd.read_csv(OUT / "did.csv")
dd = dd[(dd.scope == "matched") & (dd.scheme == "paired")]
want = ["consequence - inert", "salience - inert", "consequence - salience",
        "observation - inert", "consequence - observation"]
dd = dd[dd.comparison.isin(want)]
dd = dd.assign(o1=dd.model.map(morder), o2=dd.comparison.map({c: i for i, c in enumerate(want)}))
dd = dd.sort_values(["o2", "o1"])
lines, prev = [], None
for r in dd.itertuples():
    if prev is not None and r.comparison != prev:
        lines.append(r"\addlinespace")
    prev = r.comparison
    a, b = r.comparison.split(" - ")
    comp = ABBR[a] + r" $-$ " + ABBR[b] + (DAG if "observation" in r.comparison else "")
    mname = SHORT[r.model] + (DDAG if b == "inert" and r.model in MISREAD else "")
    lines.append(f"{comp} & {mname} & {sgn(r.delta,4)} & {sgn(r.z,2)} & {fp(r.p)} & {fp(r.p_holm)} \\\\")
(RES / "tab_did_ieee.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("wrote", *[p.name for p in sorted(RES.glob('tab_*_ieee.tex'))], "tab_outcome.tex")

# ---------------- Table IV: components of the Qwen2.5-7B consequence effect ----------------
def pholm_measure(folder, measure):
    txt = (D / folder / "RESULTS.md").read_text(encoding="utf-8")
    sec = txt.split("## 2. monitored vs unmonitored", 1)[1]
    header = next(l for l in sec.splitlines() if l.startswith("| measure"))
    cols = [c.strip() for c in header.strip("|").split("|")]
    row = next(l for l in sec.splitlines() if l.startswith(f"| {measure} "))
    vals = [c.strip() for c in row.strip("|").split("|")]
    return float(vals[cols.index("p_holm")])

df = pd.read_csv(D / "qwen7b_stakes" / "episode_features.csv")
mon, unm = df[df.condition == "monitored"], df[df.condition == "unmonitored"]
spec = [("shortcut\\_sole\\_basis", "shortcut_sole_basis", 3),
        ("cached\\_retrieved", "cached_retrieved", 3),
        ("submitted", "submitted", 3),
        ("records inspected (mean)", "n_records_inspected", 2),
        ("policy checked (any)", "policy_checked_any", 3),
        ("tool calls (mean)", "n_steps", 2)]
lines = []
for label, col, d in spec:
    a, b = mon[col].astype(float).mean(), unm[col].astype(float).mean()
    lines.append(f"{label} & {a:.{d}f} & {b:.{d}f} & {fp_exact(pholm_measure('qwen7b_stakes', col))} \\\\")
(RES / "tab_mechanism.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("wrote tab_mechanism.tex")
