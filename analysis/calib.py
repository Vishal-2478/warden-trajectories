"""Type-I error check under the null, with strong rollout pairing."""
import numpy as np, pandas as pd, tempfile, os
from synth import make
import trajectory_analysis as ra

def one(seed, pair_strength, perm=200):
    with tempfile.TemporaryDirectory() as d:
        pa, pb = os.path.join(d, "a.csv"), os.path.join(d, "b.csv")
        make(pa, 0.0, seed=seed, pair_strength=pair_strength)
        make(pb, 0.0, seed=seed + 10_000, pair_strength=pair_strength)
        out = {}
        dfa, dfb = ra.load(pa, "all"), ra.load(pb, "all")
        for key, df in [("a", dfa), ("b", dfb)]:
            lab = (df.condition == "monitored").to_numpy().astype(int)
            M = ra.count_matrix(df.tool_sequence.tolist())
            obs = ra.observed_jsd(M, lab)
            for scheme in ["free", "paired"]:
                st = df.rollout.to_numpy() if scheme == "paired" else None
                null = ra.arm_null(M, lab, st, perm, seed * 7 + (scheme == "paired") + (key == "b") * 3)
                out[(key, scheme)] = (obs, null)
        res = {}
        for scheme in ["free", "paired"]:
            obs, null = out[("a", scheme)]
            res[f"arm_{scheme}"] = (1 + (null >= obs).sum()) / (perm + 1)
            ob = out[("b", scheme)][0] - out[("a", scheme)][0]
            nl = out[("b", scheme)][1] - out[("a", scheme)][1]
            res[f"did_{scheme}"] = ra.centred_p(ob, nl)[0]
        return res

import sys
for ps in [float(x) for x in sys.argv[1:]]:
    rows = [one(s, ps) for s in range(1, 301)]
    df = pd.DataFrame(rows)
    print(f"pair_strength={ps}  (smaller = stronger pairing)   n_sims={len(df)}")
    print("  false-positive rate at 0.05:", {c: round((df[c] < 0.05).mean(), 3) for c in df.columns})
