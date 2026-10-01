#!/bin/bash
# Regenerates every trajectory number, table and figure reported in the paper
# from the released data, into results/. Run from the repository root:
#     bash analysis/make_results.sh
# Requires: python3 with numpy, pandas, scipy, matplotlib, tabulate.
set -euo pipefail
python3 analysis/trajectory_analysis.py analysis/manifest.csv --perm 10000 --out out
python3 analysis/make_tables.py out results 10000
python3 analysis/make_ieee_tables.py out results
python3 analysis/make_text_numbers.py out results
python3 analysis/make_figure.py out/nulls.npz out/did.csv results/fig_null.pdf \
  'Phi-4|consequence-observation|matched|free|(a) Phi-4: consequence − observation' \
  'Qwen2.5-7B|consequence-inert|matched|free|(b) Qwen2.5-7B: consequence − inert' \
  'Phi-4|consequence-inert|matched|free|(c) Phi-4: consequence − inert'
echo "done: results/ (numbers.tex, textnumbers.tex, tables, fig_null.pdf); full test output in out/"
