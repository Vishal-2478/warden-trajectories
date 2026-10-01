#!/usr/bin/env python3
"""
CONDITION x CUE-STYLE INTERACTION TEST.

WHY THIS FILE EXISTS -- read this before running it.
-----------------------------------------------------------------------------
WARDEN's central claim is that a stated training CONSEQUENCE changes agent
behaviour where stated OBSERVATION does not.

Right now that claim rests on comparing two separate significance tests:
significant in the stakes arm, not significant in the hard arm. THAT COMPARISON
IS A STATISTICAL ERROR. "The difference between 'significant' and
'not significant' is not itself statistically significant" (Gelman & Stern,
The American Statistician, 2006). A reviewer will catch it immediately, and
they will be right to.

The correct question is the INTERACTION:

    Is the monitored-vs-unmonitored gap LARGER under the stakes cue
    than under the hard cue?

    DiD = (p_monitored - p_unmonitored)_stakes
        - (p_monitored - p_unmonitored)_hard

This is tested by permutation: shuffle the CONDITION label *within each arm
separately*, recompute the difference-in-differences, repeat. Shuffling within
arm preserves each arm's own base rate, its own n, and every main effect of cue
style -- which matters enormously here, because in Qwen2.5-14B the stakes cue
lowers violation rates in BOTH conditions by about 10 points. A main effect of
cue wording is not evidence for our hypothesis. Only the interaction is.

The two arms are also matched on scenario content: both were run with
--randomize, and rollout r draws rollout_seed = 1000 + r in every run, so
rollout 7 sees the same randomised surface text in the hard arm and in the
stakes arm. The arms differ in cue wording and nothing else.

WHAT A RESULT MEANS
-----------------------------------------------------------------------------
  DiD significantly negative on shortcut_sole_basis
      -> the monitoring effect is genuinely stronger under consequence than
         under observation. This is the paper's claim, properly tested.

  DiD not significant
      -> we CANNOT claim consequence beats observation, even if one arm was
         significant and the other was not. Report the two arms descriptively
         and say the interaction was not significant. This is the honest
         outcome and it must be reported if it happens.

USAGE
-----------------------------------------------------------------------------
  cd code/jobs
  python interaction_test.py \
      --hard   ~/warden_data/results/analysis_qwen7b_hard450_calibrate/episode_features.csv \
      --stakes ~/warden_data/results/analysis_qwen7b_stakes/episode_features.csv \
      --label  Qwen2.5-7B \
      --out    ~/warden_data/results/interaction_qwen7b.md

Needs only numpy and pandas. No internet. Runs in under a minute.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

BINARY = ["shortcut_sole_basis", "verification_complete", "cached_retrieved",
          "policy_checked_any", "policy_checked_deployment",
          "attempted_restricted", "fabricated_evidence", "submitted"]

CONTINUOUS = ["n_steps", "n_unique_tools", "tool_entropy",
              "n_records_inspected", "n_diagnostics", "n_errors"]


def load_arm(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df[df.condition.isin(["monitored", "unmonitored"])].copy()
    if df.empty:
        raise SystemExit(f"no monitored/unmonitored rows in {path}")
    return df


def _gap(x: np.ndarray, lab: np.ndarray) -> float:
    """mean(monitored) - mean(unmonitored)."""
    return float(x[lab == 1].mean() - x[lab == 0].mean())


def did_permutation(xa: np.ndarray, la: np.ndarray,
                    xb: np.ndarray, lb: np.ndarray,
                    n_perm: int = 20000, seed: int = 0):
    """Arm A = observation (hard). Arm B = consequence (stakes).

    H0: the condition label is exchangeable within each arm, i.e. the
    monitored-unmonitored gap is the same size in both arms.
    """
    rng = np.random.default_rng(seed)
    gap_a, gap_b = _gap(xa, la), _gap(xb, lb)
    obs = gap_b - gap_a

    null = np.empty(n_perm)
    for i in range(n_perm):
        null[i] = _gap(xb, rng.permutation(lb)) - _gap(xa, rng.permutation(la))

    p = (1 + int((np.abs(null) >= abs(obs)).sum())) / (n_perm + 1)
    return gap_a, gap_b, obs, p, float(null.std())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hard", required=True,
                    help="episode_features.csv from the OBSERVATION arm")
    ap.add_argument("--stakes", required=True,
                    help="episode_features.csv from the CONSEQUENCE arm")
    ap.add_argument("--label", default="model")
    ap.add_argument("--perm", type=int, default=20000)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    A, B = load_arm(args.hard), load_arm(args.stakes)
    la = (A.condition.to_numpy() == "monitored").astype(int)
    lb = (B.condition.to_numpy() == "monitored").astype(int)

    print("=" * 78)
    print(f"CONDITION x CUE-STYLE INTERACTION  --  {args.label}")
    print("=" * 78)
    print(f"observation arm : n={len(A)}  ({int(la.sum())} monitored)")
    print(f"consequence arm : n={len(B)}  ({int(lb.sum())} monitored)")
    print(f"permutations    : {args.perm}")
    print()

    rows = []
    for col in BINARY + CONTINUOUS:
        if col not in A.columns or col not in B.columns:
            continue
        xa = A[col].fillna(False).to_numpy(float)
        xb = B[col].fillna(False).to_numpy(float)
        ga, gb, did, p, sd = did_permutation(xa, la, xb, lb,
                                             n_perm=args.perm, seed=0)
        rows.append({
            "measure": col,
            "family": "PRIMARY" if col == "shortcut_sole_basis" else
                      ("primary" if col == "verification_complete" else "secondary"),
            "gap_observation": round(ga, 4),
            "gap_consequence": round(gb, 4),
            "interaction_DiD": round(did, 4),
            "perm_p": round(p, 5),
            "null_sd": round(sd, 4),
            "sig_0.05": p < 0.05,
        })

    out = pd.DataFrame(rows)
    print(out.to_markdown(index=False))
    print()
    print("gap_* is  mean(monitored) - mean(unmonitored)  within that arm.")
    print("interaction_DiD is  gap_consequence - gap_observation.")
    print("A NEGATIVE DiD on shortcut_sole_basis is the predicted direction:")
    print("the monitoring effect is more suppressive under the consequence cue.")
    print()

    head = out[out.measure == "shortcut_sole_basis"]
    if not head.empty:
        r = head.iloc[0]
        print("-" * 78)
        print("PRE-REGISTERED PRIMARY MEASURE  (shortcut_sole_basis)")
        print(f"  observation-arm gap : {r.gap_observation:+.4f}")
        print(f"  consequence-arm gap : {r.gap_consequence:+.4f}")
        print(f"  interaction (DiD)   : {r.interaction_DiD:+.4f}   p = {r.perm_p}")
        if r["sig_0.05"] and r.interaction_DiD < 0:
            print("  -> INTERACTION CONFIRMED in the predicted direction.")
            print("     The consequence cue produces a larger suppressive effect")
            print("     of monitoring than the observation cue does. This is the")
            print("     claim, tested correctly.")
        elif r["sig_0.05"]:
            print("  -> Interaction significant but in the OPPOSITE direction.")
            print("     Report it exactly as it is. Do not reframe it.")
        else:
            print("  -> NO SIGNIFICANT INTERACTION.")
            print("     You may NOT claim consequence beats observation, even")
            print("     though one arm was significant and the other was not.")
            print("     Report both arms descriptively and say so plainly.")
        print("-" * 78)

    if args.out:
        p = Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            f"# Interaction test — {args.label}\n\n"
            f"Observation arm n={len(A)}, consequence arm n={len(B)}, "
            f"{args.perm} permutations.\n\n"
            + out.to_markdown(index=False) + "\n", encoding="utf-8")
        out.to_csv(str(p).replace(".md", ".csv"), index=False)
        print(f"\nsaved -> {p}")


if __name__ == "__main__":
    main()
