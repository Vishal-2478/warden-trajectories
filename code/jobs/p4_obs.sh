#!/bin/bash

# =====================================================================
# THE REAL RUN, for ONE model, in one job:
#
#   stage 1  calibration    60 episodes, HARD cue ("You ARE monitored")
#   stage 2  THE GATE       does the model react at all? -> stop if not
#   stage 3  experiment    225 episodes, SUBTLE cue, randomised templates
#   stage 4  analysis      RESULTS.md + 3 figures
#   stage 5  tarball       one file to take home
#
#   cd code/jobs
#   bash warden_full.sh
#
# Run ONLY after warden_smoke.sh looked correct.
#
# TO RUN A DIFFERENT MODEL: download it first with
#     bash setup_once.sh <hf-repo-id>
# then change the three lines under "edit me".
# =====================================================================

JOB_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$JOB_DIR" || exit 1
set -o pipefail

# ---- edit me --------------------------------------------------------
MODEL_NAME="microsoft/phi-4"
MODEL_DIR="phi-4"
TAG="phi4_hard450"
N_CALIB=450                              # x3 conditions =  60 episodes
N_FORMAL=75                             # x3 conditions = 225 episodes
TEMP="${TEMP:-0.7}"
WORKERS="${WORKERS:-16}"
# ---------------------------------------------------------------------

MODEL_PATH="${WARDEN_DATA:-$(cat "$HOME/.warden_data_dir" 2>/dev/null || echo "$HOME/warden_data")}/models/$MODEL_DIR"

source "$JOB_DIR/_warden_env.sh"
cd "$WARDEN_PROJECT" || exit 1

R="$WARDEN_DATA/results"
START=$(date +%s)

# =====================================================================
# STAGE 1 -- CALIBRATION. Hard, unmissable cue. 60 episodes.
# Never pooled with the formal data. Its only job is to answer: does this
# model react to an explicit monitoring statement at all?
# =====================================================================
echo
echo "############ STAGE 1/5  CALIBRATION (hard cue, $((N_CALIB*3)) episodes) ############"
python run.py calibrate \
    --model "$MODEL_NAME" --n "$N_CALIB" --workers "$WORKERS" --temperature "$TEMP" \
    --results "$R/${TAG}_calibrate" || { echo "!! calibration run failed"; exit 1; }

python run.py analyze \
    --results "$R/${TAG}_calibrate" \
    --out     "$R/analysis_${TAG}_calibrate" --perm 5000 \
    || echo "(calibration analysis failed -- the gate below still runs)"

# =====================================================================
# STAGE 2 -- THE GATE. The single most important decision in the project,
# made automatically instead of trusting you to read a file at 2am.
# Override with:  WARDEN_SKIP_GATE=1 bash warden_full.sh
# =====================================================================
echo
echo "############ STAGE 2/5  CALIBRATION GATE ############"
python jobs/gate_check.py "$R/${TAG}_calibrate"
GATE=$?
if [ $GATE -ne 0 ]; then
    echo
    echo "STOPPING BEFORE THE 225-EPISODE RUN. Read the guidance above."
    echo "Calibration data kept at: $R/${TAG}_calibrate  -- copy it home,"
    echo "it is real data and it goes in the paper either way."
    tar -czf "$R/${TAG}_calibration_only.tar.gz" \
        -C "$R" "${TAG}_calibrate" "analysis_${TAG}_calibrate" 2>/dev/null || true
    exit 2
fi

# =====================================================================
# STAGE 3 -- THE FORMAL EXPERIMENT. Subtle cue, randomised templates.
# 225 episodes. This is the dataset the paper is built on.
# =====================================================================
echo
echo "############ STAGE 3/5  FORMAL EXPERIMENT (subtle cue, $((N_FORMAL*3)) episodes) ############"
python run.py experiment \
    --model "$MODEL_NAME" --n "$N_FORMAL" --randomize --workers "$WORKERS" --temperature "$TEMP" \
    --results "$R/${TAG}_experiment" || { echo "!! formal run failed"; exit 1; }

# =====================================================================
# STAGE 4 -- ANALYSIS. The judge is NOT run here (no internet on this
# node); it runs later on your laptop. Both primary dependent variables
# and the trajectory permutation test are computed now.
# =====================================================================
echo
echo "############ STAGE 4/5  ANALYSIS ############"
python run.py analyze \
    --results "$R/${TAG}_experiment" \
    --out     "$R/analysis_${TAG}" --perm 10000 || { echo "!! analysis failed"; exit 1; }

# =====================================================================
# STAGE 5 -- ONE TARBALL TO TAKE HOME. No backups on this machine.
# =====================================================================
echo
echo "############ STAGE 5/5  PACKING ############"
tar -czf "$R/${TAG}_ALL.tar.gz" -C "$R" \
    "${TAG}_calibrate" "${TAG}_experiment" \
    "analysis_${TAG}_calibrate" "analysis_${TAG}" 2>/dev/null
cp -f "$R/${TAG}_ALL.tar.gz" "$HOME/" 2>/dev/null || true

MINS=$(( ($(date +%s) - START) / 60 ))
echo
echo "======================================================================"
echo "DONE in ${MINS} min."
echo
echo "  Headline numbers  : $R/analysis_${TAG}/RESULTS.md"
echo "  Raw episodes      : $R/${TAG}_experiment"
echo "  EVERYTHING zipped : $HOME/${TAG}_ALL.tar.gz   <-- drag THIS home"
echo
echo "NEXT, on your laptop:"
echo "  1. download ${TAG}_ALL.tar.gz"
echo "  2. extract it"
echo "  3. python run.py judge   --results results/${TAG}_experiment --judge-model <other family>"
echo "  4. python run.py analyze --results results/${TAG}_experiment --out analysis/${TAG} --perm 10000"
echo "======================================================================"
grep -A6 "Trajectory-distribution test" "$R/analysis_${TAG}/RESULTS.md" | head -20 || true
