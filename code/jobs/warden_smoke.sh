#!/bin/bash

# =====================================================================
# WARDEN SMOKE TEST -- 3 real episodes.
#
#   cd code/jobs
#   bash warden_smoke.sh
#
# To watch the model server while it runs, tail the vLLM log:
#   tail -f code/jobs/vllm_qwen7b_smoke.log
#
# SUCCESS: three blocks -- MONITORED / UNMONITORED / AMBIGUOUS -- each
# ending "-> submitted", each listing 4-8 tools Qwen chose itself.
# =====================================================================

JOB_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$JOB_DIR" || exit 1

# ---- the only lines you edit ----------------------------------------
MODEL_NAME="Qwen/Qwen2.5-7B-Instruct"
MODEL_DIR="Qwen2.5-7B-Instruct"
TAG="qwen7b_smoke"
TEMP="${TEMP:-0.7}"
# ---------------------------------------------------------------------

MODEL_PATH="${WARDEN_DATA:-$(cat "$HOME/.warden_data_dir" 2>/dev/null || echo "$HOME/warden_data")}/models/$MODEL_DIR"

source "$JOB_DIR/_warden_env.sh"

echo "=================== WARDEN SMOKE TEST ==================="
cd "$WARDEN_PROJECT" || exit 1
python run.py smoke \
    --model "$MODEL_NAME" \
    --temperature "$TEMP" \
    --results "$WARDEN_DATA/results/smoke_${TAG}"
RC=$?

echo
if [ $RC -eq 0 ]; then
    echo "SMOKE TEST FINISHED OK."
    echo "Read the three trajectories above. If Qwen chose its own tools and"
    echo "reached 'submitted', run:   bash warden_full.sh"
else
    echo "SMOKE TEST FAILED (exit $RC)."
    echo "vLLM log: $WARDEN_JOBDIR/vllm_${TAG}.log"
fi
exit $RC
