#!/bin/bash
# =====================================================================
# WARDEN -- one-time setup on the machine that will run the experiments.
#
#   cd code/jobs
#   bash setup_once.sh                                  # Qwen/Qwen2.5-7B-Instruct
#   bash setup_once.sh mistralai/Mistral-7B-Instruct-v0.3
#
# Creates the conda environment `warden`, installs vLLM and the project's
# requirements, and downloads the model weights to $WARDEN_DATA/models.
# Safe to run more than once; downloads resume.
# =====================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="$(dirname "$HERE")"
echo "Project directory: $PROJECT"

# --- 0. where large files live -----------------------------------------
export WARDEN_DATA="${WARDEN_DATA:-$HOME/warden_data}"
mkdir -p "$WARDEN_DATA/models" "$WARDEN_DATA/results"
echo "Data directory: $WARDEN_DATA"
echo "$WARDEN_DATA" > "$HOME/.warden_data_dir"

# --- 1. conda ----------------------------------------------------------
CONDA_SH=""
for c in "$HOME/miniconda3/etc/profile.d/conda.sh" "$HOME/anaconda3/etc/profile.d/conda.sh"; do
    [ -f "$c" ] && { CONDA_SH="$c"; break; }
done
if [ -z "$CONDA_SH" ]; then
    echo "No conda found. Installing Miniconda into $HOME/miniconda3 ..."
    curl -fsSL https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -o /tmp/miniconda_$USER.sh
    bash /tmp/miniconda_$USER.sh -b -p "$HOME/miniconda3"
    rm -f /tmp/miniconda_$USER.sh
    CONDA_SH="$HOME/miniconda3/etc/profile.d/conda.sh"
fi
echo "$CONDA_SH" > "$HOME/.warden_conda_sh"
# shellcheck disable=SC1090
source "$CONDA_SH"
if ! conda env list | awk '{print $1}' | grep -qx "warden"; then
    conda create -n warden python=3.11 -y
fi
set +u; conda activate warden; set -u
export PYTHONNOUSERSITE=1

# --- 2. packages (vLLM first: it pins torch and numpy) -----------------
python -m pip install --upgrade pip
python -m pip install vllm            # the paper's runs used vLLM 0.28.0
python -m pip install --upgrade-strategy only-if-needed -r "$PROJECT/requirements.txt"
python -m pip install --upgrade-strategy only-if-needed huggingface_hub

# --- 3. download the model ---------------------------------------------
export HF_HOME="$WARDEN_DATA/hf_cache"
MODEL=${1:-Qwen/Qwen2.5-7B-Instruct}
DEST="$WARDEN_DATA/models/$(basename "$MODEL")"
echo "Downloading $MODEL -> $DEST"
python - "$MODEL" "$DEST" <<'PY'
import sys
from huggingface_hub import snapshot_download
snapshot_download(repo_id=sys.argv[1], local_dir=sys.argv[2], max_workers=4)
print("download finished")
PY
[ -f "$DEST/config.json" ] || { echo "!! FAILED: $DEST/config.json missing."; exit 1; }

# --- 4. offline check of the code --------------------------------------
( cd "$PROJECT" && python run.py smoke --model mock --results "$WARDEN_DATA/results/_setup_mock" >/dev/null \
  && echo "mock smoke ok" )
echo "Setup complete. Next: bash warden_smoke.sh"
