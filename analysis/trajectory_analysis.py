#!/usr/bin/env python3
"""
TRAJECTORY ANALYSIS -- per-arm trajectory tests, cross-arm and control-ladder
difference-in-differences, Holm correction and the censoring check, in one run.

WHAT IT DOES, IN PLAIN WORDS
-----------------------------------------------------------------------------
For every (model, cue arm) you give it, it asks the pre-registered question
    "do monitored and unmonitored episodes take different ROUTES?"
by comparing the pooled tool-call bigram distributions of the two conditions
with Jensen-Shannon divergence (JSD) and a permutation test.

It does that three ways (the "scopes"):
    all        every episode
    submitted  only episodes that filed a decision   (censoring check)
    matched    only episodes whose filed verdict is 'adverse'
               (same final answer, so the outcome cannot explain a difference)

and with two permutation schemes:
    free    shuffle condition labels across all episodes (the paper's test)
    paired  swap labels only WITHIN a rollout index r. Rollout r shows the
            same randomised surface text in every condition, so the design
            is paired; this is the exact test for that design. Free
            permutation ignores the pairing and is expected to be
            conservative (larger p), never anti-conservative.

Then it compares arms with a difference-in-differences on JSD:
    Delta = JSD_armB(mon, unmon) - JSD_armA(mon, unmon)
with labels permuted within each arm separately, and a p-value measured
from the permutation null's own centre (JSD is upward-biased at finite n
and the bias differs by arm, so the null is not centred at zero).

Comparisons made automatically, whenever both arms exist for a model:
    consequence - observation     (the paper's Table 4)
    X - inert  for every other X  (is it content, or any toggle?)
    consequence - salience        (is it oversight content, or any
                                   loaded content?)

Holm correction is applied within each named family and printed.

INPUT
-----------------------------------------------------------------------------
A manifest CSV with three columns:
    model,arm,path
    Phi-4,observation,/path/analysis_phi4_hard450_calibrate/episode_features.csv
    Phi-4,consequence,/path/analysis_phi4_stakes/episode_features.csv
    Phi-4,inert,/path/analysis_phi4_neutral/episode_features.csv
    ...
arm must be one of: inert, observation, salience, consequence

USAGE
-----------------------------------------------------------------------------
    python trajectory_analysis.py manifest.csv --perm 10000 --out out

OUTPUT (in --out)
-----------------------------------------------------------------------------
    TRAJECTORY_RESULTS.md     human-readable report
    per_arm.csv             one row per model x arm x scope
    did.csv                 one row per model x comparison x scope
    censoring.csv           submission / step-budget rates by condition
    nulls.npz               every permutation null (for the figure)
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ARMS = ["inert", "observation", "salience", "consequence"]
SCOPES = ["all", "submitted", "matched"]


# ------------------------------------------------------------------ basics
def bigrams(seq: str) -> Counter:
    """Identical to warden.metrics.bigrams (START/END sentinels)."""
    tools = ["<START>"] + (seq.split("→") if isinstance(seq, str) and seq else []) + ["<END>"]
    return Counter(zip(tools[:-1], tools[1:]))


def count_matrix(seqs: list[str]) -> np.ndarray:
    cs = [bigrams(s) for s in seqs]
    vocab: dict = {}
    for c in cs:
        for k in c:
            vocab.setdefault(k, len(vocab))
    M = np.zeros((len(cs), len(vocab)))
    for i, c in enumerate(cs):
        for k, v in c.items():
            M[i, vocab[k]] = v
    return M


def jsd_rows(P: np.ndarray, Q: np.ndarray) -> np.ndarray:
    """Row-wise JSD (base 2) between count matrices P and Q of equal shape."""
    P = P / P.sum(axis=1, keepdims=True)
    Q = Q / Q.sum(axis=1, keepdims=True)
    M = 0.5 * (P + Q)
    with np.errstate(divide="ignore", invalid="ignore"):
        a = np.where(P > 0, P * np.log2(P / M), 0.0).sum(axis=1)
        b = np.where(Q > 0, Q * np.log2(Q / M), 0.0).sum(axis=1)
    return 0.5 * a + 0.5 * b


# ------------------------------------------------------------ permutations
def label_draws(lab: np.ndarray, strata: np.ndarray | None, n: int,
                rng: np.random.Generator, chunk: int) -> np.ndarray:
    """Return a (chunk x N) 0/1 matrix of permuted 'monitored' labels."""
    N = len(lab)
    if strata is None:                                   # free
        keys = rng.random((chunk, N))
        order = np.argsort(keys, axis=1)
        out = np.zeros((chunk, N))
        k = int(lab.sum())
        rows = np.repeat(np.arange(chunk), k)
        out[rows, order[:, :k].ravel()] = 1
        return out
    # paired: within each stratum, a random permutation of that stratum's labels.
    # Implemented by sorting random keys within stratum and reassigning the
    # stratum's own labels in that order -- exact for any stratum size.
    keys = rng.random((chunk, N)) + strata[None, :] * 2.0   # strata stay blocks
    order = np.argsort(keys, axis=1)                          # permuted positions
    base_order = np.argsort(strata, kind="stable")
    sorted_labels = lab[base_order]                           # labels, grouped by stratum
    out = np.empty((chunk, N))
    rows = np.arange(chunk)[:, None]
    out[rows, order] = sorted_labels[None, :]
    return out


def arm_null(M: np.ndarray, lab: np.ndarray, strata, n_perm: int, seed: int,
             chunk: int = 1000) -> np.ndarray:
    rng = np.random.default_rng(seed)
    total = M.sum(axis=0)
    null = np.empty(n_perm)
    done = 0
    while done < n_perm:
        c = min(chunk, n_perm - done)
        L = label_draws(lab, strata, n_perm, rng, c)
        mon = L @ M
        null[done:done + c] = jsd_rows(mon, total[None, :] - mon)
        done += c
    return null


def observed_jsd(M: np.ndarray, lab: np.ndarray) -> float:
    mon = M[lab == 1].sum(axis=0, keepdims=True)
    return float(jsd_rows(mon, M.sum(axis=0, keepdims=True) - mon)[0])


def centred_p(obs: float, null: np.ndarray) -> tuple[float, float, float]:
    """Two-sided p measured from the null's own centre, plus doubled-tail check."""
    n = len(null)
    mu, sd = float(null.mean()), float(null.std())
    p_c = (1 + int((np.abs(null - mu) >= abs(obs - mu)).sum())) / (n + 1)
    p_gt = (1 + int((null >= obs).sum())) / (n + 1)
    p_lt = (1 + int((null <= obs).sum())) / (n + 1)
    z = (obs - mu) / sd if sd > 0 else float("nan")
    return p_c, min(1.0, 2 * min(p_gt, p_lt)), z


def holm(p: list[float]) -> list[float]:
    m = len(p)
    order = sorted(range(m), key=lambda i: p[i])
    adj, run = [0.0] * m, 0.0
    for r, i in enumerate(order):
        run = max(run, (m - r) * p[i])
        adj[i] = min(1.0, run)
    return adj


# ------------------------------------------------------------------ data
def load(path: str, scope: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    need = {"condition", "tool_sequence", "rollout", "submitted", "verdict"}
    miss = need - set(df.columns)
    if miss:
        raise SystemExit(f"{path}: missing columns {sorted(miss)}")
    df = df[df.condition.isin(["monitored", "unmonitored"])].copy()
    sub = df.submitted.astype(str).str.lower().isin(["true", "1"])
    if scope == "submitted":
        df = df[sub]
    elif scope == "matched":
        df = df[df.verdict == "adverse"]
    df["tool_sequence"] = df.tool_sequence.fillna("")
    return df.reset_index(drop=True)


# ------------------------------------------------------------------ main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest")
    ap.add_argument("--perm", type=int, default=10000)
    ap.add_argument("--out", default="out")
    ap.add_argument("--seed", type=int, default=20260929)
    a = ap.parse_args()

    man = pd.read_csv(a.manifest)
    bad = set(man.arm) - set(ARMS)
    if bad:
        raise SystemExit(f"unknown arm(s) {bad}; allowed {ARMS}")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    per_arm, cens, nulls = [], [], {}
    obs_store: dict = {}
    seed = a.seed
    for _, row in man.iterrows():
        raw = pd.read_csv(row.path)
        raw = raw[raw.condition.isin(["monitored", "unmonitored"])]
        # ---- censoring table (all episodes)
        for cond in ["monitored", "unmonitored"]:
            d = raw[raw.condition == cond]
            s = d.submitted.astype(str).str.lower().isin(["true", "1"])
            ms = (d.termination_reason == "max_steps") if "termination_reason" in d else pd.Series(False, index=d.index)
            cens.append(dict(model=row.model, arm=row.arm, condition=cond, n=len(d),
                             submitted=round(s.mean(), 4), hit_step_budget=round(ms.mean(), 4),
                             adverse=round((d.verdict == "adverse").mean(), 4),
                             mean_steps=round(d.n_steps.mean(), 3) if "n_steps" in d else None))
        dm, du = raw[raw.condition == "monitored"], raw[raw.condition == "unmonitored"]
        sm = dm.submitted.astype(str).str.lower().isin(["true", "1"])
        su = du.submitted.astype(str).str.lower().isin(["true", "1"])
        p_sub = stats.fisher_exact([[sm.sum(), len(sm) - sm.sum()], [su.sum(), len(su) - su.sum()]])[1]
        cens.append(dict(model=row.model, arm=row.arm, condition="Fisher p (submitted)",
                         n=None, submitted=round(p_sub, 5), hit_step_budget=None,
                         adverse=None, mean_steps=None))

        for scope in SCOPES:
            df = load(row.path, scope)
            lab = (df.condition == "monitored").to_numpy().astype(int)
            M = count_matrix(df.tool_sequence.tolist())
            obs = observed_jsd(M, lab)
            res = dict(model=row.model, arm=row.arm, scope=scope,
                       n_mon=int(lab.sum()), n_unmon=int(len(lab) - lab.sum()),
                       jsd=round(obs, 5))
            for scheme in ["free", "paired"]:
                seed += 1
                strata = df.rollout.to_numpy() if scheme == "paired" else None
                null = arm_null(M, lab, strata, a.perm, seed)
                nulls[f"{row.model}|{row.arm}|{scope}|{scheme}"] = null
                p_one = (1 + int((null >= obs).sum())) / (a.perm + 1)
                res[f"null_mean_{scheme}"] = round(float(null.mean()), 5)
                res[f"z_{scheme}"] = round((obs - null.mean()) / null.std(), 2) if null.std() > 0 else None
                res[f"p_{scheme}"] = p_one
            per_arm.append(res)
            obs_store[(row.model, row.arm, scope)] = obs

    # ---------------------------------------------------------------- DiD
    comparisons = [("consequence", "observation", "T4: consequence - observation (paper Table 4)"),
                   ("observation", "inert", "LADDER: X - inert"),
                   ("salience", "inert", "LADDER: X - inert"),
                   ("consequence", "inert", "LADDER: X - inert"),
                   ("consequence", "salience", "CONTENT: consequence - salience")]
    did = []
    for model in man.model.unique():
        have = set(man[man.model == model].arm)
        for b, a_, fam in comparisons:
            if b not in have or a_ not in have:
                continue
            for scope in SCOPES:
                obs = obs_store[(model, b, scope)] - obs_store[(model, a_, scope)]
                for scheme in ["free", "paired"]:
                    null = (nulls[f"{model}|{b}|{scope}|{scheme}"]
                            - nulls[f"{model}|{a_}|{scope}|{scheme}"])
                    nulls[f"DID|{model}|{b}-{a_}|{scope}|{scheme}"] = null
                    p_c, p_t, z = centred_p(obs, null)
                    did.append(dict(family=fam, model=model, comparison=f"{b} - {a_}",
                                    scope=scope, scheme=scheme,
                                    jsd_b=round(obs_store[(model, b, scope)], 5),
                                    jsd_a=round(obs_store[(model, a_, scope)], 5),
                                    delta=round(obs, 5),
                                    null_mean=round(float(null.mean()), 5),
                                    z=round(z, 2), p=p_c, p_tailcheck=p_t))
    per_arm = pd.DataFrame(per_arm)
    did = pd.DataFrame(did)
    cens = pd.DataFrame(cens)

    # ---------------------------------------------------------------- Holm
    # Per-arm: family = all (model, arm) tests in one scope and scheme.
    for scheme in ["free", "paired"]:
        per_arm[f"p_{scheme}_holm"] = np.nan
        for scope in SCOPES:
            m = per_arm.scope == scope
            per_arm.loc[m, f"p_{scheme}_holm"] = holm(per_arm.loc[m, f"p_{scheme}"].tolist())
    # DiD: family = (family name, scheme); scopes are pooled INTO the family,
    # i.e. the correction counts every model x scope cell.
    # The 'submitted' scope is a censoring sensitivity check, not a test of the
    # claim, so it is left out of the families (its p_holm stays empty).
    did["p_holm"] = np.nan
    core = did[did.scope.isin(["all", "matched"])]
    for (fam, scheme), g in core.groupby(["family", "scheme"]):
        did.loc[g.index, "p_holm"] = holm(g.p.tolist())

    per_arm.to_csv(out / "per_arm.csv", index=False)
    did.to_csv(out / "did.csv", index=False)
    cens.to_csv(out / "censoring.csv", index=False)
    np.savez_compressed(out / "nulls.npz", **{k.replace("|", "__").replace(" ", ""): v
                                               for k, v in nulls.items()})

    # ---------------------------------------------------------------- report
    floor = 1 / (a.perm + 1)
    L = [f"# Trajectory analysis  ({a.perm} permutations; smallest reportable p = {floor:.5f})", "",
         "p at the floor means 'no permutation was as extreme'. Report it as "
         f"p < {2*floor:.4f} and give z.", "",
         "## 1. Per-arm: do monitored and unmonitored routes differ?", "",
         "One-sided permutation p (JSD cannot be negative). Holm within scope.", "",
         per_arm[["model", "arm", "scope", "n_mon", "n_unmon", "jsd",
                  "z_free", "p_free", "p_free_holm", "z_paired", "p_paired", "p_paired_holm"]]
         .to_markdown(index=False, floatfmt=".5f"), "",
         "## 2. Difference-in-differences between arms", "",
         "Two-sided, centred on the permutation null. Holm within family x scheme, "
         "counting every model x scope cell.", ""]
    for scheme in ["free", "paired"]:
        L += [f"### {scheme} permutation", "",
              did[did.scheme == scheme][["family", "model", "comparison", "scope", "jsd_b", "jsd_a",
                                         "delta", "null_mean", "z", "p", "p_tailcheck", "p_holm"]]
              .to_markdown(index=False, floatfmt=".5f"), ""]
    L += ["## 3. Censoring check (all episodes)", "",
          cens.to_markdown(index=False, floatfmt=".4f"), "",
          "## 4. How to read this", "",
          "- `paired` p should be <= `free` p in most rows. If `paired` is much LARGER, "
          "check the pairing -- that would mean the pairing is not what we think.",
          "- `p` and `p_tailcheck` should agree closely. A big gap means a skewed null: report both.",
          "- LADDER rows test specificity. `X - inert` significant means the cue's CONTENT moved "
          "routes beyond what a meaningless toggle does.",
          "- CONTENT row: consequence - salience near zero means routes respond to "
          "loaded content in general, not to oversight specifically. Report it either way.", ""]
    (out / "TRAJECTORY_RESULTS.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
