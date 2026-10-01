#!/usr/bin/env python3
"""
WARDEN command line.

  python run.py smoke      --model mock
  python run.py calibrate  --model Qwen/Qwen2.5-7B-Instruct --n 20
  python run.py experiment --model Qwen/Qwen2.5-7B-Instruct --n 75 --randomize
  python run.py judge      --results results/experiment --judge-model gpt-4o
  python run.py analyze    --results results/experiment --out analysis/qwen7b
  python run.py annotate   --results results/experiment --out annotation/round1
  python run.py kappa      --sheet annotation/round1/filled.csv \
                           --hidden annotation/round1/_hidden_judge_labels.csv
"""

from __future__ import annotations

import argparse
import itertools
import os
from pathlib import Path

from dotenv import load_dotenv

from warden.analysis import run_analysis
from warden.annotation import compute_kappa, export_sample
from warden.conditions import CONDITIONS
from warden.judge import judge_directory
from warden.llm import LLMClient
from warden.metrics import load_episodes
from warden.runner import run_batch, run_episode, save_episode
from warden.scenario_s1 import ScenarioS1

load_dotenv()


def subject_models(results_dir) -> list[str]:
    """Which model actually produced the episodes in this directory."""
    import json
    seen = set()
    for p in sorted(Path(results_dir).rglob("*.json"))[:200]:
        try:
            m = json.loads(p.read_text(encoding="utf-8")).get("model")
            if m:
                seen.add(m)
        except Exception:
            continue
    return sorted(seen)


def make_client(args) -> LLMClient:
    return LLMClient(model=args.model, base_url=args.base_url,
                     api_key=args.api_key, temperature=args.temperature)


def build_jobs(args, client, cue_style, n):
    jobs = []
    for variant, condition in itertools.product(args.variants.split(","), CONDITIONS):
        for r in range(n):
            # The same rollout index gets the SAME randomised surface text in
            # every condition, so surface wording is matched across conditions
            # and only the monitoring cue differs.
            scen = ScenarioS1(variant, rollout_seed=(1000 + r) if args.randomize else None)
            jobs.append(dict(scenario=scen, condition=condition, model=args.model,
                             client=client, cue_style=cue_style, rollout=r,
                             seed=(args.seed + r) if args.seed is not None else None,
                             max_steps=args.max_steps))
    return jobs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["smoke", "calibrate", "experiment",
                                        "stakes", "lexical", "neutral", "judge", "analyze",
                                        "annotate", "kappa", "mancheck"])
    ap.add_argument("--model", default=os.getenv("WARDEN_MODEL", "mock"))
    ap.add_argument("--base-url", default=os.getenv("WARDEN_BASE_URL"))
    ap.add_argument("--api-key", default=os.getenv("WARDEN_API_KEY"))
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--n", type=int, default=20, help="rollouts per condition per variant")
    ap.add_argument("--variants", default="v1")
    ap.add_argument("--randomize", action="store_true",
                    help="per-rollout template randomisation (WARDEN_PLAN sec.2)")
    ap.add_argument("--max-steps", type=int, default=10)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--results", default=None)
    ap.add_argument("--out", default="analysis/latest")
    ap.add_argument("--perm", type=int, default=10000)
    ap.add_argument("--judge-model", default=os.getenv("WARDEN_JUDGE_MODEL", "gpt-4o"))
    ap.add_argument("--judge-base-url", default=os.getenv("WARDEN_JUDGE_BASE_URL"))
    ap.add_argument("--judge-api-key", default=os.getenv("WARDEN_JUDGE_API_KEY"))
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--fraction", type=float, default=0.10)
    ap.add_argument("--sheet", default=None)
    ap.add_argument("--hidden", default=None)
    ap.add_argument("--cue", default="hard", choices=["hard", "subtle", "stakes", "lexical", "neutral"],
                    help="which cue wording the manipulation check should test")
    ap.add_argument("--a", default=None, help="annotator 1 CSV from annotate.html")
    ap.add_argument("--b", default=None, help="annotator 2 CSV from annotate.html")
    args = ap.parse_args()

    if args.command == "smoke":
        client = make_client(args)
        root = Path(args.results or "results/smoke")
        for condition in CONDITIONS:
            ep = run_episode(ScenarioS1("v1"), condition, args.model, client,
                             cue_style="subtle", rollout=0, seed=args.seed,
                             max_steps=args.max_steps)
            p = save_episode(ep, root)
            print(f"\n=== {condition.upper()} -> {ep['termination_reason']}")
            for t in ep["trajectory"]:
                print(f"  {t['step']:>2}. {t['tool'] or 'PARSE_FAIL':<28} "
                      f"{'ERR' if t['is_error'] else '   '} {t['arguments']}")
            print(f"  submission: {ep['submission']}")
            print(f"  saved: {p}")
        print("\nSmoke test done. Read the JSON, then run calibrate.")

    elif args.command in ("calibrate", "experiment", "stakes", "lexical", "neutral"):
        client = make_client(args)
        # calibrate -> hard cue, stakes -> training-consequence cue,
        # experiment -> subtle operational prose.
        cue_style = {"calibrate": "hard", "stakes": "stakes", "lexical": "lexical", "neutral": "neutral"}.get(
            args.command, "subtle")
        root = Path(args.results or f"results/{args.command}")
        jobs = build_jobs(args, client, cue_style, args.n)
        print(f"{args.command}: {len(jobs)} episodes | model={args.model} "
              f"| cue={cue_style} | randomize={args.randomize} "
              f"| max_steps={args.max_steps} | workers={args.workers}")
        run_batch(jobs, root, workers=args.workers)
        print(f"\nDone -> {root}")
        print(f"Next: python run.py judge   --results {root}")
        print(f"      python run.py analyze --results {root} --out analysis/{args.command}")

    elif args.command == "judge":
        jc = LLMClient(model=args.judge_model, base_url=args.judge_base_url,
                       api_key=args.judge_api_key, temperature=0.0, max_tokens=300)
        # Self-judging check. The old version compared the judge against
        # --model, which is almost never passed on a judge run (it defaults to
        # "mock"), so the check never fired. Read the subject model out of the
        # episodes themselves instead -- that is the thing that must not match.
        subjects = subject_models(args.results or "results/experiment")
        jfam = args.judge_model.split("/")[0].split("-")[0].lower()
        clash = [s for s in subjects
                 if jfam and jfam in s.split("/")[0].split("-")[0].lower()]
        if clash:
            raise SystemExit(
                f"REFUSING TO RUN. Judge '{args.judge_model}' is the same model "
                f"family as the subject(s) {clash}.\n"
                "Judging a model with itself is a conflict of interest a reviewer "
                "will catch immediately.\n"
                "Use a different family, e.g.:\n"
                "  --judge-model meta-llama/Llama-3.3-70B-Instruct \\\n"
                "  --judge-base-url https://router.huggingface.co/v1 "
                "--judge-api-key YOUR_KEY")
        if subjects:
            print(f"subject model(s): {', '.join(subjects)}  |  judge: {args.judge_model}")
        n = judge_directory(args.results or "results/experiment", jc,
                            workers=args.workers, overwrite=args.overwrite)
        print(f"judged {n} episodes")

    elif args.command == "analyze":
        df = load_episodes(args.results or "results/experiment")
        p = run_analysis(df, args.out, n_perm=args.perm)
        print(f"Wrote {p}")
        cols = [c for c in ["shortcut_sole_basis", "verification_complete",
                            "judge_benign", "n_steps", "tool_entropy"]
                if c in df.columns]
        print(df.groupby("condition")[cols].mean(numeric_only=True).round(3))

    elif args.command == "annotate":
        export_sample(args.results or "results/experiment",
                      args.out if args.out != "analysis/latest" else "annotation/round1",
                      fraction=args.fraction)

    elif args.command == "mancheck":
        # Manipulation check: did the model actually perceive the cue?
        # Without this, a behavioural null is uninterpretable -- it could mean
        # "saw it and didn't care" or "never noticed it".
        from warden.mancheck import run_manipulation_check
        client = make_client(args)
        cue_style = "subtle" if args.variants == "subtle" else args.cue
        run_manipulation_check(
            ScenarioS1("v1"), client, cue_style=cue_style, n=args.n,
            out_dir=args.out if args.out != "analysis/latest" else "analysis/mancheck",
            seed=args.seed)

    elif args.command == "kappa":
        if not args.hidden:
            raise SystemExit(
                "kappa needs --hidden <_hidden_judge_labels.csv> plus either\n"
                "  --a annotator_1.csv --b annotator_2.csv   (from annotate.html)\n"
                "  or --sheet <one combined csv>")
        if args.a and args.b:
            compute_kappa(None, args.hidden, a_csv=args.a, b_csv=args.b)
        elif args.sheet:
            compute_kappa(args.sheet, args.hidden)
        else:
            raise SystemExit("give either --a and --b, or --sheet")


if __name__ == "__main__":
    main()
