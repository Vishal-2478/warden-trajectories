#!/bin/bash
# Regenerates every number, table and figure reported in the paper from the
# released data, into results/. Run from the repository root:
#     bash analysis/make_results.sh
# Requires: python3 with numpy, pandas, scipy, matplotlib, tabulate.
set -euo pipefail
# ---- main study
python3 analysis/trajectory_analysis.py analysis/manifest.csv --perm 10000 --out out
python3 analysis/make_tables.py out results 10000
python3 analysis/make_ieee_tables.py out results
python3 analysis/make_text_numbers.py out results
python3 analysis/make_figure.py out/nulls.npz out/did.csv results/fig_null.pdf \
  'Phi-4|consequence-observation|matched|free|(a) Phi-4: consequence − observation' \
  'Qwen2.5-7B|consequence-inert|matched|free|(b) Qwen2.5-7B: consequence − inert' \
  'Phi-4|consequence-inert|matched|free|(c) Phi-4: consequence − inert'
# ---- revision analyses of the main-study episodes (CIs, power, unigram/trigram,
#      selection check, stricter verdict rule; Tables II-VI of the revised paper)
rm -rf raw && mkdir raw            # unpack the raw episodes of the main study
for f in data/*/raw_episodes.tar.gz; do
  d="raw/$(basename "$(dirname "$f")")"; mkdir -p "$d"; tar -xzf "$f" -C "$d"
done
python3 analysis/extract_submissions.py raw submissions.csv
python3 analysis/revision_analyses.py analysis/manifest.csv \
  --submissions submissions.csv --perm 10000 --out out_rev
python3 analysis/make_ieee_tables_v2.py out results out_rev
# ---- revision runs (Nov 2026): randomized observation arm and second inert cue
#      (rows marked c in Tables III-V; own Holm families)
python3 analysis/revision2_analyses.py analysis/manifest.csv data/revision_runs --out out_rev2
python3 analysis/make_rev2_rows.py out_rev2 results
echo "done: results/ (numbers, tables, figure); full test output in out/, out_rev/, out_rev2/"
