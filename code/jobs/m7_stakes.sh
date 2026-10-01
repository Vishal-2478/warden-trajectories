#!/bin/bash

# =====================================================================
# THE STAKES ARM.
#
# THE QUESTION THIS ANSWERS
# Under HARD and SUBTLE cues -- which vary only "will a human read this log"
# -- Qwen2.5-7B identified its condition in 360/360 trials and behaved
# identically anyway (0.227 vs 0.231, n=450/condition, p=0.94).
#
# But the alignment-faking literature never manipulates observation alone.
# Greenblatt et al. (2024) and the Llama-3-8B replication (arXiv 2506.21584)
# tell the model this session will be used to RETRAIN it. That is a
# consequence, not merely an audience -- and prior work has confounded the two.
#
# So this job holds everything else fixed and adds the consequence:
#
#     HARD / SUBTLE  ->  someone may read this
#     STAKES         ->  this session will change what you become
#
# PRE-REGISTERED PREDICTION, written before the run:
#   Primary measure: shortcut_sole_basis, monitored vs unmonitored, stakes cue.
#   If consequence is what drives the effect, the violation rate should be
#   LOWER under stakes-monitored than stakes-unmonitored.
#   n = 450 per condition (1350 episodes), for 80% power at an 8-point gap.
#   ONE RUN. Report whatever it says.
#
#   cd code/jobs
#   bash warden_stakes.sh
#
# Stage 1 is the manipulation check -- does the model even understand the
# retraining claim? If it does not, the behavioural arm is uninterpretable and
# there is no point reading it, exactly as before.
# =====================================================================

JOB_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$JOB_DIR" || exit 1
set -o pipefail

# ---- edit me --------------------------------------------------------
MODEL_NAME="mistralai/Mistral-7B-Instruct-v0.3"
MODEL_DIR="Mistral-7B-Instruct-v0.3"
TAG="mistral7b_stakes"
N_STAKES=450                            # x3 conditions = 1350 episodes
N_MANCHECK=60
TEMP="${TEMP:-0.7}"
WORKERS="${WORKERS:-16}"
# ---------------------------------------------------------------------

MODEL_PATH="${WARDEN_DATA:-$(cat "$HOME/.warden_data_dir" 2>/dev/null || echo "$HOME/warden_data")}/models/$MODEL_DIR"

source "$JOB_DIR/_warden_env.sh"
cd "$WARDEN_PROJECT" || exit 1

R="$WARDEN_DATA/results"
START=$(date +%s)

# =====================================================================
# STAGE 1 -- MANIPULATION CHECK on the stakes cue.
# Temperature 0: we are testing whether the model CAN read the cue.
# =====================================================================
echo
echo "############ STAGE 1/3  MANIPULATION CHECK (stakes cue) ############"
python run.py mancheck --model "$MODEL_NAME" --cue stakes \
    --n "$N_MANCHECK" --temperature 0.0 --out "$R/mancheck_stakes_${TAG}"

# =====================================================================
# STAGE 2 -- THE STAKES EXPERIMENT. 1350 episodes.
# =====================================================================
echo
echo "############ STAGE 2/3  STAKES EXPERIMENT ($((N_STAKES*3)) episodes) ############"
python run.py stakes \
    --model "$MODEL_NAME" --n "$N_STAKES" --randomize \
    --workers "$WORKERS" --temperature "$TEMP" \
    --results "$R/${TAG}_experiment" || { echo "!! stakes run failed"; exit 1; }

# =====================================================================
# STAGE 3 -- ANALYSIS + TARBALL. No judge here (no network access during the run).
# =====================================================================
echo
echo "############ STAGE 3/3  ANALYSIS ############"
python run.py analyze \
    --results "$R/${TAG}_experiment" \
    --out     "$R/analysis_${TAG}" --perm 10000 || { echo "!! analysis failed"; exit 1; }

tar -czf "$R/${TAG}_ALL.tar.gz" -C "$R" \
    "${TAG}_experiment" "analysis_${TAG}" "mancheck_stakes_${TAG}" 2>/dev/null
cp -f "$R/${TAG}_ALL.tar.gz" "$HOME/" 2>/dev/null || true

MINS=$(( ($(date +%s) - START) / 60 ))
echo
echo "======================================================================"
echo "DONE in ${MINS} min."
echo "  Results  : $R/analysis_${TAG}/RESULTS.md"
echo "  Tarball  : $HOME/${TAG}_ALL.tar.gz   <-- drag THIS home"
echo
echo "HOW TO READ IT"
echo "  Manipulation check must PASS first. If the model cannot tell it is in"
echo "  the training-update sample, the behavioural numbers mean nothing."
echo
echo "  Then compare shortcut_sole_basis, monitored vs unmonitored:"
echo "    a gap appears  -> CONSEQUENCE is what matters, not observation."
echo "                      That explains both our null and the prior"
echo "                      literature, and it is a real finding."
echo "    still flat     -> this model is insensitive to oversight framing"
echo "                      of any kind, including a stated training threat."
echo "                      Also a real finding, and a cleaner scope limit."
echo "======================================================================"
sed -n '/## 2. monitored vs unmonitored/,/^## 2. monitored vs ambiguous/p' \
    "$R/analysis_${TAG}/RESULTS.md" | head -25 || true
