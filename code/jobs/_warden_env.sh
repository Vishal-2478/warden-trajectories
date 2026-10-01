# =====================================================================
# Shared prelude for the run scripts in this folder. Do not run directly;
# every *.sh run script `source`s it. It activates the Python environment,
# starts a vLLM server for $MODEL_NAME on one GPU, waits until it answers,
# and points WARDEN at it. Set CUDA_VISIBLE_DEVICES yourself to choose a GPU.
#
# The vLLM settings below (max-model-len 8192, GPU memory fraction 0.85 unless
# GPU_UTIL is set) are the ones used for every run in the paper; the three
# control runs used a smaller GPU_UTIL because the GPU was shared, which
# changes throughput only.
# =====================================================================

warden_die() { echo; echo "!! $*"; echo; exit 1; }

# --- 0. find the project root (the folder that holds run.py) -----------
export WARDEN_JOBDIR="${JOB_DIR:-$PWD}"
PROJECT="$WARDEN_JOBDIR"
while [ ! -f "$PROJECT/run.py" ] && [ "$PROJECT" != "/" ]; do
    PROJECT="$(dirname "$PROJECT")"
done
[ -f "$PROJECT/run.py" ] || warden_die "Could not find run.py above $WARDEN_JOBDIR."
export WARDEN_PROJECT="$PROJECT"
echo "project  : $WARDEN_PROJECT"

# --- 1. Python environment ---------------------------------------------
CONDA_SH="$(cat "$HOME/.warden_conda_sh" 2>/dev/null || echo "$HOME/miniconda3/etc/profile.d/conda.sh")"
[ -f "$CONDA_SH" ] || warden_die "conda.sh not found at $CONDA_SH. Run setup_once.sh first."
# shellcheck disable=SC1090
source "$CONDA_SH"
conda activate warden || warden_die "conda env 'warden' missing. Run setup_once.sh first."
export PYTHONNOUSERSITE=1
export TOKENIZERS_PARALLELISM=false

# PyTorch-native sampling instead of JIT-compiled FlashInfer kernels: same
# numerics, no compiler needed at start-up.
export VLLM_USE_FLASHINFER_SAMPLER=0

# Models are downloaded beforehand (setup_once.sh); never reach the network here.
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

# --- 2. data directory -------------------------------------------------
export WARDEN_DATA="${WARDEN_DATA:-$(cat "$HOME/.warden_data_dir" 2>/dev/null || echo "$HOME/warden_data")}"
export HF_HOME="$WARDEN_DATA/hf_cache"
mkdir -p "$WARDEN_DATA/results" || warden_die "cannot write to $WARDEN_DATA"
echo "data dir : $WARDEN_DATA"

# --- 3. the model must already be on disk ------------------------------
[ -f "$MODEL_PATH/config.json" ] || warden_die \
"Model not found at $MODEL_PATH
   Download it first:  bash setup_once.sh $MODEL_NAME"

# --- 4. start vLLM in the background -----------------------------------
PORT="${PORT:-8000}"
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

# --- 5. wait for it to answer ------------------------------------------
echo "waiting for the model to load (2-6 minutes is normal) ..."
READY=0
for i in $(seq 1 150); do
    if python -c "import urllib.request; urllib.request.urlopen('http://localhost:$PORT/v1/models', timeout=5)" 2>/dev/null; then
        READY=1; echo "vLLM is up after ~$((i*10))s"; break
    fi
    if ! kill -0 "$VLLM_PID" 2>/dev/null; then
        echo "!! vLLM died during startup. Last 60 lines of vllm_${TAG}.log:"
        tail -60 "$WARDEN_JOBDIR/vllm_${TAG}.log"
        exit 1
    fi
    sleep 10
done
[ "$READY" -eq 1 ] || { echo "!! vLLM never answered in 25 min."; tail -60 "$WARDEN_JOBDIR/vllm_${TAG}.log"; exit 1; }

# A local vLLM server needs no key; "EMPTY" is the conventional placeholder.
export WARDEN_BASE_URL="http://localhost:$PORT/v1"
export WARDEN_API_KEY=EMPTY
echo "WARDEN will talk to $WARDEN_BASE_URL"
echo
