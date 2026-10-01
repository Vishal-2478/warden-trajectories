"""Synthetic episode_features.csv generator for validating trajectory_analysis.py.
Each rollout r has its own latent 'environment' that shapes routes in BOTH
conditions (this is the pairing). A cue effect, when present, shifts route
choice in the monitored condition only."""
import numpy as np, pandas as pd, sys
from pathlib import Path

TOOLS = ["search", "inspect", "policy", "diag", "compare", "status", "cached", "restricted"]

def episode(rng, env, effect):
    # env: rollout-specific tool weights; effect: extra weight on 'policy', less on 'cached'
    w = env.copy()
    w[TOOLS.index("policy")] *= (1 + effect)
    w[TOOLS.index("cached")] *= (1 - min(effect, 0.9))
    w = w / w.sum()
    seq, steps = [], rng.integers(3, 11)
    for _ in range(steps - 1):
        seq.append(TOOLS[rng.choice(len(TOOLS), p=w)])
    submitted = rng.random() < 0.85
    if submitted:
        seq.append("submit")
    verdict = ("adverse" if rng.random() < 0.9 else "retain") if submitted else "none"
    return dict(tool_sequence="→".join(seq), submitted=submitted, verdict=verdict,
                termination_reason="submitted" if submitted else "max_steps", n_steps=len(seq))

def make(path, effect, n=450, seed=0, pair_strength=3.0):
    rng = np.random.default_rng(seed)
    rows = []
    for r in range(n):
        env = rng.gamma(pair_strength, 1.0, len(TOOLS))      # shared by both conditions
        for cond, eff in [("monitored", effect), ("unmonitored", 0.0), ("ambiguous", 0.0)]:
            e = episode(rng, env, eff)
            e.update(condition=cond, rollout=r)
            rows.append(e)
    pd.DataFrame(rows).to_csv(path, index=False)

if __name__ == "__main__":
    out = Path(sys.argv[1]); out.mkdir(exist_ok=True)
    spec = {  # scenario: {arm: effect}
        "S1_specific": dict(inert=0.0, observation=0.0, salience=0.0, consequence=0.6),
        "S2_generic":  dict(inert=0.0, observation=0.0, salience=0.6, consequence=0.6),
    }
    man = []
    s = 100
    for scen, arms in spec.items():
        for arm, eff in arms.items():
            s += 1
            p = out / f"{scen}_{arm}.csv"
            make(p, eff, seed=s)
            man.append(dict(model=scen, arm=arm, path=str(p)))
    pd.DataFrame(man).to_csv(out / "manifest.csv", index=False)
    print(pd.DataFrame(man))
