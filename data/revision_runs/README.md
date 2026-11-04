# Revision runs (November 2026)

Seven runs added during the IConSCEPT 2026 revision, on the same model files,
settings and GPU type as the main study. Job scripts, with the predictions written
before the runs, are in `code/jobs/revision_runs/`.

| folder | model | cue |
|---|---|---|
| analysis_qwen7b_obsR | Qwen2.5-7B | observation, randomized surface text |
| analysis_qwen14b_obsR | Qwen2.5-14B | observation, randomized surface text |
| analysis_phi4_obsR | Phi-4 | observation, randomized surface text |
| analysis_mistral7b_obsR | Mistral-7B | observation, randomized surface text |
| analysis_qwen7b_encoding | Qwen2.5-7B | second inert cue (tool-response encoding) |
| analysis_qwen14b_encoding | Qwen2.5-14B | second inert cue (tool-response encoding) |
| analysis_phi4_encoding | Phi-4 | second inert cue (tool-response encoding) |

Each `analysis_*` folder holds the per-episode features, the within-run results and
`raw_episodes.tar.gz` (all 1,350 episodes). `mancheck_encoding_*` holds the
manipulation check of the second inert cue. Analysis:

    python3 analysis/revision2_analyses.py analysis/manifest.csv data/revision_runs --out out_rev2
    python3 analysis/make_rev2_rows.py out_rev2 results
