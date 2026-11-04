#!/bin/bash
# Submits the 7 runs so that they run one after another (one GPU instance at a time).
cd "$(dirname "$0")" || exit 1
prev=""
for f in 1_obsR_q7 2_obsR_p4 3_enc_q14 4_enc_p4 5_enc_q7 6_obsR_q14 7_obsR_m7; do
    if [ -z "$prev" ]; then id="$(qsub "$f.pbs")"; else id="$(qsub -W depend=afterany:"$prev" "$f.pbs")"; fi
    [ -n "$id" ] || { echo "!! qsub failed for $f -- check the log"; exit 1; }
    echo "$f -> $id"; prev="$id"
done
echo; qstat -u "$USER"
