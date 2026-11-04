# =====================================================================
# Shared prelude for the PBS jobs of the revision runs. Do not run directly --
# the job scripts in this folder `source` it.
#
# WHAT IS DIFFERENT FROM code/jobs/_warden_env.sh
#   1. The GPU is split into TWO fixed 71 GB MIG instances whose UUIDs are
#      hard-coded by the admin, and PBS does NOT select one for you. If we do
#      not set CUDA_VISIBLE_DEVICES by hand, torch.cuda.is_available() returns
#      False and vLLM cannot find a GPU at all. (Manual section 7, step 3.)
#   2. Storage is /home/$USER -- shared with the compute node, so nothing has
#      to be copied anywhere.
#   3. HF_HUB_OFFLINE=1, because the compute node has no internet and we do
#      not want huggingface_hub stalling on a lookup it can never complete.
# =====================================================================

warden_die() { echo; echo "!! $*"; echo; exit 1; }

# --- 0. find the project root ------------------------------------------
export WARDEN_JOBDIR="${PBS_O_WORKDIR:-$PWD}"
PROJECT="$WARDEN_JOBDIR"
while [ ! -f "$PROJECT/run.py" ] && [ "$PROJECT" != "/" ]; do
    PROJECT="$(dirname "$PROJECT")"
done
[ -f "$PROJECT/run.py" ] || warden_die \
"Could not find run.py above $WARDEN_JOBDIR.
   Submit from inside the project, e.g.  cd ~/warden/jobs && qsub ..."
export WARDEN_PROJECT="$PROJECT"
echo "project  : $WARDEN_PROJECT"

# --- 1. conda ----------------------------------------------------------
# Job scripts do not read your login profile, so conda must be sourced by hand.
CONDA_SH="$(cat "$HOME/.warden_conda_sh" 2>/dev/null || echo "$HOME/miniconda3/etc/profile.d/conda.sh")"
[ -f "$CONDA_SH" ] || warden_die "conda.sh not found at $CONDA_SH. Run setup_once.sh on the login node first."
# shellcheck disable=SC1090
source "$CONDA_SH"
conda activate warden || warden_die "conda env 'warden' missing. Run setup_once.sh first."
export PYTHONNOUSERSITE=1
export TOKENIZERS_PARALLELISM=false

# vLLM JIT-compiles FlashInfer sampling kernels with ninja at startup. On a node
# whose CUDA toolkit is older than the wheels expect, that compile fails and the
# engine dies with "Engine core initialization failed". PyTorch-native sampling
# gives the same numerics and needs no compiler.
export VLLM_USE_FLASHINFER_SAMPLER=0

# The compute node has no internet (manual section 6). Without this,
# huggingface_hub blocks on network lookups it can never satisfy.
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

# Keeps large models from fragmenting GPU memory (manual section 7).
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

# --- 2. data directory -------------------------------------------------
export WARDEN_DATA="${WARDEN_DATA:-$(cat "$HOME/.warden_data_dir" 2>/dev/null || echo "$HOME/warden_data")}"
export HF_HOME="$WARDEN_DATA/hf_cache"
mkdir -p "$WARDEN_DATA/results" || warden_die "cannot write to $WARDEN_DATA"
echo "data dir : $WARDEN_DATA"

# --- 3. the model must already be on disk ------------------------------
[ -f "$MODEL_PATH/config.json" ] || warden_die \
"Model not found at $MODEL_PATH
   Download it on the LOGIN NODE first:
       cd ~/warden/jobs && bash setup_once.sh $MODEL_NAME"

# --- 4. pick a MIG instance -- REQUIRED on this machine ----------------
# Machine-specific MIG UUIDs were removed for publication; put yours here. If they
# are not found, the MIG instances listed by nvidia-smi are used instead
# (instance 1 = first listed, instance 2 = second), and with no MIG the whole GPU.
MIG_1="MIG-REPLACE-WITH-UUID-OF-INSTANCE-1"
MIG_2="MIG-REPLACE-WITH-UUID-OF-INSTANCE-2"
echo "=== GPU instances on this node ==="
LIST="$(nvidia-smi -L)" || warden_die "nvidia-smi failed -- this job did not get a GPU. Check the select= line has ngpus=1."
echo "$LIST"
case "${MIG_INSTANCE:-1}" in 2) WANT="$MIG_2"; MIG_IDX=2 ;; *) WANT="$MIG_1"; MIG_IDX=1 ;; esac
if echo "$LIST" | grep -q "${WANT#MIG-}"; then
    export CUDA_VISIBLE_DEVICES="$WANT"
else
    NOW="$(echo "$LIST" | grep -o 'MIG-[0-9a-f-]*' | sed -n "${MIG_IDX}p")"
    if [ -n "$NOW" ]; then
        export CUDA_VISIBLE_DEVICES="$NOW"
        echo "(the MIG id above was not found; using the listed MIG instance $MIG_IDX instead)"
    else
        export CUDA_VISIBLE_DEVICES=0
        echo "(no MIG instances on this node now; using the whole GPU 0)"
    fi
fi
echo "using: $CUDA_VISIBLE_DEVICES"

# --- 5. start vLLM in the background -----------------------------------
JOBNUM="${PBS_JOBID%%.*}"
case "$JOBNUM" in (*[!0-9]*|"") JOBNUM=$$ ;; esac
PORT=$(( 8000 + (JOBNUM % 1000) ))

VLLM_EXTRA=""
if vllm serve --help 2>/dev/null | grep -q -- '--disable-log-requests'; then
    VLLM_EXTRA="--disable-log-requests"
fi

echo
echo "vllm version : $(python -c 'import vllm;print(vllm.__version__)' 2>/dev/null || echo '?')"
echo "starting vLLM on port $PORT ..."
SETSID=""; command -v setsid >/dev/null 2>&1 && SETSID="setsid"
$SETSID vllm serve "$MODEL_PATH" \
    --served-model-name "$MODEL_NAME" \
    --port "$PORT" \
    --max-model-len 8192 \
    --gpu-memory-utilization "${GPU_UTIL:-0.85}" \
    $VLLM_EXTRA \
    > "$WARDEN_JOBDIR/vllm_${TAG}.log" 2>&1 &
VLLM_PID=$!

cleanup() {
    echo "stopping vLLM (pid $VLLM_PID)"
    pkill -TERM -P "$VLLM_PID" 2>/dev/null || true
    kill -TERM -- -"$VLLM_PID" 2>/dev/null || kill -TERM "$VLLM_PID" 2>/dev/null || true
    sleep 8
    pkill -KILL -P "$VLLM_PID" 2>/dev/null || true
    kill -KILL -- -"$VLLM_PID" 2>/dev/null || kill -KILL "$VLLM_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# --- 6. wait for it to answer ------------------------------------------
echo "waiting for the model to load (2-6 minutes is normal) ..."
READY=0
for i in $(seq 1 150); do
    if python -c "import urllib.request; urllib.request.urlopen('http://localhost:$PORT/v1/models', timeout=5)" 2>/dev/null; then
        READY=1; echo "vLLM is up after ~$((i*10))s"; break
    fi
    if ! kill -0 "$VLLM_PID" 2>/dev/null; then
        echo "!! vLLM died during startup. Last 60 lines of vllm_${TAG}.log:"
        tail -60 "$WARDEN_JOBDIR/vllm_${TAG}.log"
        echo
        echo "COMMON CAUSES ON THIS MACHINE:"
        echo "  'no GPU' / cuda not available -> the MIG UUID is wrong. Compare the"
        echo "        nvidia-smi -L output above with MIG_1/MIG_2 in _warden_env_rev.sh"
        echo "  'ninja ... non-zero exit'     -> a JIT compile failed. We already set"
        echo "        VLLM_USE_FLASHINFER_SAMPLER=0; send me the log if it persists."
        echo "  'Name or service not known'   -> something tried to reach the internet"
        echo "        from the compute node. The model must be downloaded beforehand."
        exit 1
    fi
    sleep 10
done
[ "$READY" -eq 1 ] || { echo "!! vLLM never answered in 25 min."; tail -60 "$WARDEN_JOBDIR/vllm_${TAG}.log"; exit 1; }

export WARDEN_BASE_URL="http://localhost:$PORT/v1"
export WARDEN_API_KEY=EMPTY
echo "WARDEN will talk to $WARDEN_BASE_URL"
echo
