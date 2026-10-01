#!/usr/bin/env python3
"""Write every data-derived number that appears in the running text of the paper.

The tables and trajectory statistics are produced by make_tables.py and
make_ieee_tables.py. This script covers the remaining numbers quoted in the text
(episode and trial counts, submission rates, first actions, manipulation-check
answers, simulation results and so on), so that no result in the paper is typed
by hand. Design parameters (sample size per condition, number of permutations,
temperature, step budget, thresholds) are stated in the text directly.

The script also checks the qualitative claims that the text makes about the data
(for example, that no model changed its violation rate under the observation cue)
and stops with an error if any of them does not hold.

Usage (from the repository root, after trajectory_analysis.py has written out/):
    python3 analysis/make_text_numbers.py out results
writes results/textnumbers.tex
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

OUT, RES = Path(sys.argv[1]), Path(sys.argv[2])
RES.mkdir(parents=True, exist_ok=True)
D = Path("data")
sys.dont_write_bytecode = True  # do not leave __pycache__ in code/
sys.path.insert(0, "code")
from warden.conditions import cue_text  # noqa: E402  (plain-Python module, no dependencies)

RUNS = {  # (model, arm) -> folder
    ("Qwen2.5-7B", "inert"): "qwen7b_neutral",
    ("Qwen2.5-7B", "observation"): "qwen7b_hard450_calibrate",
    ("Qwen2.5-7B", "salience"): "qwen7b_lexical",
    ("Qwen2.5-7B", "consequence"): "qwen7b_stakes",
    ("Qwen2.5-14B", "inert"): "qwen14b_neutral",
    ("Qwen2.5-14B", "observation"): "qwen14b_hard450_calibrate",
    ("Qwen2.5-14B", "consequence"): "qwen14b_stakes",
    ("Phi-4", "inert"): "phi4_neutral",
    ("Phi-4", "observation"): "phi4_hard450_calibrate",
    ("Phi-4", "salience"): "phi4_lexical",
    ("Phi-4", "consequence"): "phi4_stakes",
    ("Mistral-7B", "observation"): "mistral7b_hard450_calibrate",
    ("Mistral-7B", "consequence"): "mistral7b_stakes",
}
CUE_STYLE = {"observation": "hard", "consequence": "stakes", "salience": "lexical", "inert": "neutral"}

macros = {}


def put(name, value):
    assert re.fullmatch(r"[A-Za-z]+", name), name
    assert name not in macros, f"duplicate macro {name}"
    macros[name] = value


def need(cond, msg):
    if not cond:
        sys.exit(f"CHECK FAILED: {msg}")


def thousands(n):
    return f"{n:,}".replace(",", "{,}")


def count(n):
    """Counts below ten are spelled out in running text (IEEE style)."""
    words = "zero one two three four five six seven eight nine".split()
    return words[n] if 0 <= n < 10 else str(n)


def pct(x, d=1):
    return f"{100 * x:.{d}f}\\%"


def sgn(x, d=3):
    return f"${x:+.{d}f}$"


def peq(p, sym="p", floor=None):
    """p-value with its relation sign, e.g. $p=0.016$ or $p\\le 10^{-4}$."""
    if floor is not None and p <= floor + 1e-12:
        return f"${sym}\\le 10^{{-4}}$"
    if p < 0.001:
        return f"${sym}<0.001$"
    if p < 0.01:
        return f"${sym}={p:.4f}$"
    return f"${sym}={p:.3f}$"


def feats(model, arm):
    return pd.read_csv(D / RUNS[(model, arm)] / "episode_features.csv")


def results_table(model, arm):
    """Section 2 (monitored vs unmonitored) of a run's RESULTS.md, as a DataFrame."""
    txt = (D / RUNS[(model, arm)] / "RESULTS.md").read_text(encoding="utf-8")
    sec = txt.split("## 2. monitored vs unmonitored", 1)[1].split("### Trajectory", 1)[0]
    lines = [l for l in sec.splitlines() if l.startswith("|")]
    cols = [c.strip() for c in lines[0].strip("|").split("|")]
    rows = [[c.strip() for c in l.strip("|").split("|")] for l in lines[2:]]
    df = pd.DataFrame(rows, columns=cols)
    df["p_holm"] = df["p_holm"].astype(float)
    return df.set_index("measure")


def interaction(stem):
    txt = (D / "outcome_interactions" / f"{stem}.txt").read_text(encoding="utf-8")
    row = next(l for l in txt.splitlines() if l.startswith("| shortcut_sole_basis"))
    vals = [c.strip() for c in row.strip("|").split("|")]
    return float(vals[4]), float(vals[5])  # interaction DiD, permutation p


def by_cond(df, col):
    g = df.groupby("condition")[col].mean()
    return g["monitored"], g["unmonitored"]


# ---------------------------------------------------------------- scale of the study
all_feats = {k: feats(*k) for k in RUNS}
put("RunsTotal", str(len(all_feats)))
put("EpisodesTotal", thousands(sum(len(df) for df in all_feats.values())))
sizes = {n for df in all_feats.values() for n in df.condition.value_counts()}
need(sizes == {450}, f"every condition should hold 450 episodes, found {sizes}")

mc = {}
for f in sorted((D / "manipulation_checks").glob("*.json")):
    d = json.loads(f.read_text(encoding="utf-8"))
    tally = defaultdict(Counter)
    for t in d["trials"]:
        tally[t["condition"]][t["answer"]] += 1
    mc[f.stem] = (d, tally)
put("ManCheckTrials", thousands(sum(len(d["trials"]) for d, _ in mc.values())))

# ---------------------------------------------------------------- protocol failures and submission
fail = {k: (df.termination_reason == "format_failure").mean() for k, df in all_feats.items()}
need(all(v == 0 for k, v in fail.items() if k[0] != "Mistral-7B"), "protocol failures outside Mistral-7B")
mf = sorted(v for k, v in fail.items() if k[0] == "Mistral-7B")
put("MistralFailRange", f"{100 * mf[0]:.1f}--{pct(mf[-1])}")
need(mf[-1] < 0.01, "Mistral-7B protocol failures should stay below 1%")


def sub_range(prefix):
    v = sorted(df.submitted.astype(float).mean() for k, df in all_feats.items() if k[0].startswith(prefix))
    lo, hi = v[0], v[-1]
    return f"{100 * lo:.1f}--{'100' if hi == 1 else f'{100 * hi:.1f}'}\\%"


put("QwenSubRange", sub_range("Qwen"))
put("PhiSubRange", sub_range("Phi"))
put("MistralSubRange", sub_range("Mistral"))

# ---------------------------------------------------------------- manipulation checks
for stem, (d, t) in mc.items():
    if stem.startswith("mancheck_hard_"):
        need(t["monitored"]["YES"] == t["unmonitored"]["NO"] == t["ambiguous"]["UNKNOWN"] == 60,
             f"observation check not perfect in {stem}")
put("ManCheckPerCondition", str(len(mc["mancheck_hard_phi4_mancheck"][0]["trials"]) // 3))
for stem in ["mancheck_neutral_phi4_neutral", "mancheck_lexical_phi4_lexical",
             "mancheck_neutral_qwen7b_neutral", "mancheck_lexical_qwen7b_lexical"]:
    d, t = mc[stem]
    need(sum(c["UNKNOWN"] for c in t.values()) == len(d["trials"]), f"{stem}: not UNKNOWN throughout")
put("ControlUnknownTrials", str(len(mc["mancheck_neutral_phi4_neutral"][0]["trials"])))
d, t = mc["mancheck_neutral_qwen14b_neutral"]
need(t["monitored"]["YES"] == t["unmonitored"]["YES"] == 60, "Qwen2.5-14B inert check pattern changed")
put("QFourteenInertYes", str(t["monitored"]["YES"] + t["unmonitored"]["YES"]))
for stem in ["mancheck_stakes_qwen7b", "mancheck_stakes_qwen14b_stakes", "mancheck_stakes_phi4_stakes"]:
    need(mc[stem][0]["key_accuracy"] >= 0.80, f"{stem} should pass")
put("MistralConsKey", f"{mc['mancheck_stakes_mistral7b_stakes'][0]['key_accuracy']:.2f}")
need(float(macros["MistralConsKey"]) <= 0.60, "Mistral-7B consequence check should fail")

# ---------------------------------------------------------------- outcome results
gaps = []
for m in ["Qwen2.5-7B", "Qwen2.5-14B", "Phi-4", "Mistral-7B"]:
    a, b = by_cond(all_feats[(m, "observation")], "shortcut_sole_basis")
    gaps.append(abs(a - b))
    need(results_table(m, "observation").loc["shortcut_sole_basis", "p_holm"] >= 0.05,
         f"{m}: observation P1 difference is significant")
put("ObsMaxGapPts", f"{100 * max(gaps):.1f}")

q7 = {arm: by_cond(all_feats[("Qwen2.5-7B", arm)], "shortcut_sole_basis")
      for arm in ["inert", "salience", "consequence"]}
put("QSevenSalDiff", sgn(q7["salience"][0] - q7["salience"][1]))
put("QSevenConsDiff", sgn(q7["consequence"][0] - q7["consequence"][1]))
put("QSevenConsDiffPts", f"{100 * abs(q7['consequence'][0] - q7['consequence'][1]):.1f}")
put("QSevenConsMon", f"{q7['consequence'][0]:.3f}")
put("QSevenConsUnmon", f"{q7['consequence'][1]:.3f}")
need(results_table("Qwen2.5-7B", "inert").loc["shortcut_sole_basis", "p_holm"] >= 0.05,
     "Qwen2.5-7B inert P1 should not change")
did, p = interaction("Qwen2.5-7B_consequence-vs-inert")
put("QSevenConsDiDInert", sgn(did))
put("QSevenConsDiDInertP", peq(p, floor=1e-4))
r = [round(x, 1) for x in by_cond(all_feats[("Qwen2.5-7B", "consequence")], "n_records_inspected")]
need(r[0] == r[1], "records inspected no longer equal to one decimal")
put("QSevenConsRecords", f"{r[0]:.1f}")

fa = pd.crosstab(all_feats[("Qwen2.5-7B", "inert")].first_action, all_feats[("Qwen2.5-7B", "inert")].condition)
put("QSevenInertPolicyFirstMon", str(fa.loc["check_policy", "monitored"]))
put("QSevenInertPolicyFirstUnmon", str(fa.loc["check_policy", "unmonitored"]))
fa = pd.crosstab(all_feats[("Phi-4", "inert")].first_action, all_feats[("Phi-4", "inert")].condition)
put("PhiInertCachedFirstMon", str(fa.loc["retrieve_cached_assessment", "monitored"]))
put("PhiInertCachedFirstUnmon", str(fa.loc["retrieve_cached_assessment", "unmonitored"]))

# Phi-4: which outcome measures survive Holm under each cue
PRIMARY = ["shortcut_sole_basis", "verification_complete"]
sig = {arm: results_table("Phi-4", arm).query("p_holm < 0.05") for arm in
       ["observation", "consequence", "inert", "salience"]}
for arm in ["observation", "inert"]:
    need(sig[arm].empty, f"Phi-4 {arm}: a measure survives correction")
need(list(sig["consequence"].index) == ["policy_checked_any"], "Phi-4 consequence: survivors changed")
tab = results_table("Phi-4", "consequence")
put("NMeasures", str(len(tab)))
put("NSecondary", str(len(tab) - len(PRIMARY)))
a, b = by_cond(all_feats[("Phi-4", "consequence")], "policy_checked_any")
put("PhiConsPolicyMon", f"{a:.3f}")
put("PhiConsPolicyUnmon", f"{b:.3f}")
put("PhiConsPolicyPH", peq(tab.loc["policy_checked_any", "p_holm"], sym="p_{\\mathrm{H}}"))
need("verification_complete" in sig["salience"].index, "Phi-4 salience: P2 no longer survives")
need("shortcut_sole_basis" not in sig["salience"].index, "Phi-4 salience: P1 now survives")
put("PhiSalNSecondarySig", count(len([m for m in sig["salience"].index if m not in PRIMARY])))
a, b = by_cond(all_feats[("Phi-4", "salience")], "verification_complete")
put("PhiSalVerMon", f"{a:.3f}")
put("PhiSalVerUnmon", f"{b:.3f}")
put("PhiSalVerPH", peq(results_table("Phi-4", "salience").loc["verification_complete", "p_holm"],
                       sym="p_{\\mathrm{H}}"))

# Families used for Holm correction
put("NOutcomeDiD", count(len(list((D / "outcome_interactions").glob("*-vs-inert.txt")))))
pa = pd.read_csv(OUT / "per_arm.csv")
put("NTrajArms", str(pa[pa.scope == "matched"].shape[0]))

# ---------------------------------------------------------------- matched-outcome sample sizes
m = pa[pa.scope == "matched"]
put("MatchedMin", str(int(min(m.n_mon.min(), m.n_unmon.min()))))
put("MatchedMax", str(int(max(m.n_mon.max(), m.n_unmon.max()))))

# ---------------------------------------------------------------- simulation check (analysis/calib.py)
txt = (D / "simulation_checks" / "calib_pair0.5_1.0.txt").read_text(encoding="utf-8")
nsims = set(re.findall(r"n_sims=(\d+)", txt))
need(len(nsims) == 1, "simulation file should hold one n_sims value")
put("SimN", nsims.pop())
rates = defaultdict(list)
for key, val in re.findall(r"'(\w+)': (?:np\.float64\()?([0-9.]+)", txt):
    rates[key].append(float(val))
paired = rates["arm_paired"] + rates["did_paired"]
free = rates["arm_free"] + rates["did_free"]
put("SimPairedRange", f"{100 * min(paired):.0f}--{100 * max(paired):.0f}\\%")
put("SimFreeMax", pct(max(free)))

# ---------------------------------------------------------------- cue lengths (code/warden/conditions.py)
gap = {arm: abs(len(cue_text("monitored", s)) - len(cue_text("unmonitored", s)))
       / max(len(cue_text("monitored", s)), len(cue_text("unmonitored", s)))
       for arm, s in CUE_STYLE.items()}
put("CueLenMax", pct(max(gap.values())))
need(max(gap, key=gap.get) == "consequence", "the consequence cue no longer has the largest length gap")

# ---------------------------------------------------------------- write
lines = ["% Generated by analysis/make_text_numbers.py from the released data. Do not edit."]
lines += [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in macros.items()]
(RES / "textnumbers.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"wrote {RES / 'textnumbers.tex'} ({len(macros)} macros)")
