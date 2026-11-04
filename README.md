# WARDEN: code and data for "Same Decision, Different Route"

This repository contains the code and data behind the paper
*Same Decision, Different Route: Sensitivity and Specificity of Trajectory Tests for Oversight Effects in Tool-Using Language Model Agents*
(V. V. Mali and S. Singh, Department of Information Technology, Dr. B. R. Ambedkar National Institute of Technology Jalandhar),
which calls the evaluation framework implemented here **WARDEN**:
the environment and agent code, the job script of every run, every episode, every manipulation check, and the analysis that produces every number reported in the paper.

## Regenerate all reported numbers (one command)

```
pip install numpy pandas scipy matplotlib tabulate
bash analysis/make_results.sh          # run from the repository root
```

This runs three stages and writes every number and table row of the paper to `results/`:

1. **Main study** (`data/<run>/`): trajectory tests with 10,000 permutations; every trajectory statistic (`numbers.tex`), every other number quoted in the text (`textnumbers.tex`), the tables and the null-distribution figure of the first submission. `make_text_numbers.py` also checks each statement the paper makes about the data (for example, that no model changed its violation rate under the observation cue) and stops with an error if one does not hold.
2. **Revision analyses of the main-study episodes** (`out_rev/`): 95% confidence intervals, power, unigram and trigram routes, the selection check of the matched-outcome scope, a stricter verdict rule and Mistral-7B among submitted episodes. The raw episodes are unpacked into `raw/` for this step.
3. **Revision runs** (`data/revision_runs/`, `out_rev2/`): the randomized observation arm and the second inert cue, with their own Holm families; table rows marked c in the revised paper (`tab_*_rev.tex`).

The whole script takes a few minutes. Full test output is in `out/TRAJECTORY_RESULTS.md`, `out_rev/` and `out_rev2/REVISION2_RESULTS.md`. Outcome-level interaction tests of the main study are in `data/outcome_interactions/`.

## What is here

| Path | Contents |
|---|---|
| `analysis/trajectory_analysis.py` | Trajectory tests: per-arm Jensen–Shannon divergence with free and rollout-paired permutations; cross-cue and control-ladder difference-in-differences; Holm correction; censoring table. |
| `analysis/make_tables.py`, `make_ieee_tables.py`, `make_text_numbers.py`, `make_figure.py`, `make_results.sh` | Turn the analysis output and the data into the paper's numbers, tables and figure. |
| `analysis/synth.py`, `analysis/calib.py` | Simulation checks of the permutation tests. `python3 calib.py 0.5 1.0` (run inside `analysis/`) reproduces the false-positive rates quoted in Section IV of the paper; its output is stored in `data/simulation_checks/`. |
| `analysis/revision_analyses.py`, `extract_submissions.py`, `make_ieee_tables_v2.py`, `make_figure_v2.py` | Analyses added in the revision on the main-study episodes, and the tables of the revised paper. |
| `analysis/revision2_analyses.py`, `make_rev2_rows.py` | Analysis of the seven revision runs and their table rows (marked c). |
| `analysis/manifest.csv` | Which data folder is which model and cue arm (main study). |
| `code/` | The simulated workplace environment, episode runner, manipulation check and per-run analysis (`run.py`, `warden/`). |
| `code/jobs/` | The run script of every run (`*.sh`), the shared start-up script `_warden_env.sh` (starts a local vLLM server), `setup_once.sh` (environment and model download), and `interaction_test.py` (outcome-level difference-in-differences). For publication, scheduler directives and machine-specific settings were removed from the run scripts; their predictions, decision rules and run commands are unchanged. |
| `data/<run>/episode_features.csv` | One row per episode: condition, rollout, `variant`, primary and secondary measures, verdict, and the ordered tool calls (`tool_sequence`). |
| `data/<run>/raw_episodes.tar.gz` | The complete raw record of every episode (one JSON per episode: prompts, every tool call and observation, final environment state). |
| `data/<run>/RESULTS.md` | The per-run report written at the end of each run. |
| `data/manipulation_checks/` | Every manipulation-check record (question, answer and raw reply for each trial). |
| `data/outcome_interactions/` | Outcome-level difference-in-differences of the main study (Table III of the revised paper), produced by `code/jobs/interaction_test.py`. |
| `data/simulation_checks/` | Output of `analysis/calib.py 0.5 1.0`, from which the paper quotes the false-positive rates of the permutation tests. |
| `code/jobs/revision_runs/` | The job scripts of the seven revision runs as they were run on a PBS cluster (machine-specific identifiers removed), with their predictions in the headers, and `run_extra.py`, which registers the second inert cue. |
| `data/revision_runs/` | Episodes, per-run results and manipulation checks of the seven revision runs (see its `README.md`). |
| `INTEGRITY_LOG.md` | Defects we found in our own code and process, and how each was handled. |

All 27,000 formal episodes are included: 17,550 in the 13 runs of the main study and 9,450 in the seven revision runs (each run: 3 conditions × 450 episodes).

## Runs

| Folder | Model | Cue family | Surface text |
|---|---|---|---|
| `qwen7b_hard450_calibrate` | Qwen2.5-7B-Instruct | observation | fixed (`v1`) |
| `qwen7b_stakes` | Qwen2.5-7B-Instruct | consequence | randomised (`v1rand`) |
| `qwen7b_neutral` | Qwen2.5-7B-Instruct | inert (line wrapping) | randomised |
| `qwen7b_lexical` | Qwen2.5-7B-Instruct | salience (archival) | randomised |
| `qwen14b_hard450_calibrate` | Qwen2.5-14B-Instruct | observation | fixed |
| `qwen14b_stakes` | Qwen2.5-14B-Instruct | consequence | randomised |
| `qwen14b_neutral` | Qwen2.5-14B-Instruct | inert | randomised |
| `phi4_hard450_calibrate` | Phi-4 | observation | fixed |
| `phi4_stakes` | Phi-4 | consequence | randomised |
| `phi4_neutral` | Phi-4 | inert | randomised |
| `phi4_lexical` | Phi-4 | salience | randomised |
| `mistral7b_hard450_calibrate` | Mistral-7B-Instruct-v0.3 | observation | fixed |
| `mistral7b_stakes` | Mistral-7B-Instruct-v0.3 | consequence (excluded: manipulation check failed) | randomised |

**Revision runs (November 2026, `data/revision_runs/`).** Same model files, settings and GPU type.

| Folder | Model | Cue family | Surface text |
|---|---|---|---|
| `analysis_qwen7b_obsR` | Qwen2.5-7B-Instruct | observation | randomised |
| `analysis_qwen14b_obsR` | Qwen2.5-14B-Instruct | observation | randomised |
| `analysis_phi4_obsR` | Phi-4 | observation | randomised |
| `analysis_mistral7b_obsR` | Mistral-7B-Instruct-v0.3 | observation | randomised |
| `analysis_qwen7b_encoding` | Qwen2.5-7B-Instruct | second inert cue (tool-response encoding) | randomised |
| `analysis_qwen14b_encoding` | Qwen2.5-14B-Instruct | second inert cue | randomised |
| `analysis_phi4_encoding` | Phi-4 | second inert cue | randomised |

**Surface text.** Randomised runs resample names, identifiers and numbers per rollout (seed 1000 + r), identically across conditions. The observation runs were produced by the `calibrate` stage of their job scripts, which does not randomise, so every episode in them shows the same text. Comparisons *within* a run are unaffected; comparisons *between* an observation run and another run differ in surface variation as well as cue content. The observation cue also differs in form from the other three: it is a direct notice (`SESSION NOTICE`), whereas the consequence, salience and inert cues share one template (`OPERATIONAL CONTEXT`, a batch line and an `ENABLED`/`DISABLED` switch) and differ only in content (`code/warden/conditions.py`). The paper states both points, marks comparisons with the observation arm (note a in its tables) and bases its conclusions on inert-referenced comparisons. See `INTEGRITY_LOG.md`, item 21. In the revision, the observation arm was repeated with randomised text in all four models (`*_obsR`): it again left the violation rate unchanged and shifted routes in no model.

**Manipulation checks of the control cues.** The check asks whether the action log is retained and reviewed by a human. For the salience and inert cues, which say nothing about review, the intended answer is UNKNOWN in every condition; the `verdict` field of those files reads `FAILED` only because the script scores every cue against YES/NO. Qwen2.5-7B and Phi-4 answered UNKNOWN in every control-cue trial. Qwen2.5-14B answered YES in all 60 monitored and all 60 unmonitored trials of the inert cue, so its inert arm is not a valid baseline; the paper marks comparisons against it (note b) and does not use them for conclusions (`INTEGRITY_LOG.md`, item 25). The second inert cue of the revision (the character encoding of tool responses, same template) was answered UNKNOWN in all 180 trials by each of Qwen2.5-7B, Qwen2.5-14B and Phi-4 (`data/revision_runs/mancheck_encoding_*`), so it is a valid baseline in all three.

## Predictions written before the runs

The job scripts of the consequence (`*_stakes`), salience (`q7_lexical`, `p4_lexical`) and inert (`q7_neutral`, `p4_neutral`, `q14_neutral`) runs state the primary measure and predicted direction in their header, written before submission. The observation scripts (`warden_hard450.sh`, `p4_obs.sh`, `q14_obs.sh`, `m7_obs.sh`) fix the sample size (`N_CALIB=450`) but contain no written prediction.

The three control runs added last (`p4_neutral`, `p4_lexical`, `q14_neutral`) were run on 30 September 2026; their headers hold the predictions and decision rules, whose text is unchanged since submission. Their central prediction failed: in Phi-4 the inert cue moves trajectories as much as the training-consequence cue (matched outcomes, consequence minus inert: −0.00115, paired p = 0.876), so the Phi-4 trajectory result is not read as an oversight effect.

The seven revision runs state their predictions in the headers of `code/jobs/revision_runs/*.pbs`, written before submission; `out_rev2/predictions.csv` evaluates them. Two failed: the second inert cue moved routes more than the consequence cue (expected: no difference) in Qwen2.5-7B and Phi-4, and in Phi-4 it also raised the violation rate.

## Notes for readers of the code

- Model decoding was not seeded; every episode is an independent draw at temperature 0.7. Only the environment's surface text is seeded.
- The docstring of `code/jobs/interaction_test.py` says both arms were run with `--randomize`; that is true for consequence, salience and inert runs but not for the observation runs (see above).
- In the observation job scripts, the comment next to `N_CALIB=450` still reads "60 episodes" from an earlier setting; the jobs ran 1,350 episodes each, as the data show.
- The header of `code/jobs/q7_neutral.sh` was copied from the salience job and still describes "storage compression"; the job itself runs the inert (line-wrapping) cue, as its `--cue neutral` and `run.py neutral` lines show.
- The revised paper no longer shows the null-distribution figure (`results/fig_null.pdf`); the tests it showed are reported in its Table V. `make_results.sh` still draws it.
- `code/jobs/_warden_env.sh` accepts `GPU_UTIL` (default 0.85, as for all earlier runs). The three control runs used a smaller value because the GPU was shared; this changes throughput only (`INTEGRITY_LOG.md`, item 22).

## How to cite

A revised version of the paper was submitted to IConSCEPT 2026 in November 2026; the full citation will be added here on publication. Until then, please cite:

> V. V. Mali and S. Singh, "Same Decision, Different Route: Sensitivity and Specificity of Trajectory Tests for Oversight Effects in Tool-Using Language Model Agents," 2026. Code and data: https://github.com/Vishal-2478/warden-trajectories

GitHub's "Cite this repository" button uses `CITATION.cff`.

## Licence

See `LICENSE`.
