# Integrity log: defects found in our own code and process

This log records every methodological defect we found in our own analysis code,
job scripts and process, what it affected, and how it was fixed. It is released
so that readers can judge the pipeline, not only its outputs. Numbering follows
the order in which items were recorded; item numbers are not contiguous in time.

### Analysis and statistics

1. **`gate_check.py` passed label-shuffled data.** Written to gate the pipeline
   on calibration quality, then tested against synthetic noise — and it
   **passed noise**. Rewritten with graded verdicts
   (BROKEN / FLAT / SUGGESTIVE / MODERATE / STRONG), `MIN_USABLE_FRACTION = 0.60`,
   and explicit flat-result detection (`FLAT_DIFF = 0.10`, `FLAT_P = 0.20`), with
   BROKEN and FLAT exiting non-zero. *Found by our own synthetic test, before it
   could affect a result.*
2. **`warden_full.sh` ignored its own gate.** The gate ran and its exit code was
   discarded. Wired into stage 2 with an exit-2 abort.
3. **`judge.py` scanned `C0_benign` first.** Because the label scan walked the
   list in declaration order, any malformed judge reply defaulted to *benign* —
   a silent bias toward finding nothing. Fixed with an explicit severity order
   (C4 → C2 → C5 → C1 → C6 → C3 → C0) and `\b` word boundaries.
4. **The self-judge guard never fired.** It compared the judge against
   `args.model`, which defaults to `"mock"` and is not passed on a judge run.
   Fixed to read the subject model out of the episode JSONs; now raises
   `SystemExit` on a family clash.
5. **`ax.boxplot(labels=)`** removed in matplotlib ≥ 3.9 — wrapped in
   try/except for `tick_labels`.
6. **`wilson()` bounds** could fall outside [0,1] — clamped.
7. **Degenerate κ**, hardcoded mock IDs, and a `groupby`-`apply` misuse — all
   fixed.

### Infrastructure

8. **`curl` is not installed on the GPU machine** — *the most costly bug.*
   vLLM started correctly, but the readiness poll used `curl`, never succeeded,
   and the job died after 25 minutes reporting "vLLM never answered." Confirmed
   by `grep -c "never answered"` = 1. Fixed with a Python `urllib` probe. **One
   full job wasted.**
9. **Default job memory was 1 GB** — jobs were killed before vLLM loaded. Fixed
   by requesting more memory for each job.
10. **`hf` CLI raised `ModuleNotFoundError`** — a stale `~/.local/bin/hf` shadowed
    on PATH and blocked by `PYTHONNOUSERSITE`. Worked around by calling
    `snapshot_download()` through `python -`.
11. **FlashInfer compile failure** — the installed CUDA toolkit was older than
    the vLLM 0.28 kernels expect. Fixed with `VLLM_USE_FLASHINFER_SAMPLER=0`.
12. **`sed` edits failed silently — twice.** `s/^N_CALIB=20$/` did not match
    because of a trailing comment; a TAG edit likewise. **Standing rule adopted:
    always `grep` to verify an edit before submitting a job.**
13. **Manipulation-check output paths lacked a model tag** — the 14B run
    overwrote the 7B result. Fixed with a `_${TAG}` suffix in both the `--out`
    and the `tar` lines. *Data was lost and had to be re-run.*
14. **File transfer from Windows failed** ("path canonicalization failed") —
    fixed with `scp -O`.
15. **Remote sessions were refused while a file-transfer session was open** (a
    session limit). Closing the transfer session first fixed it.
16. **The GPU machine was reachable only from the campus network.** Work from
    other networks was not possible.
20. **Two-sided p-value computed against the wrong reference point** —
    `trajectory_interaction.py`. The test counted how often `|null| ≥ |observed|`,
    i.e. it measured distance from **zero**. But JSD is non-negative and
    upward-biased at finite n, and that bias differs between arms, so the
    permutation null of the *difference* is not centred at zero. For Qwen-7B,
    Qwen-14B and Phi-4 the null means were within 0.002 of zero and the error was
    invisible. **Mistral-7B exposed it**: null mean −0.0116 (unequal usable n,
    184 vs 209, 101 bigram types), and the script printed
    `two-sided p = 0.850` alongside `one-sided p = 0.032` — a self-contradiction
    that could not be anything but a bug. Corrected, Mistral's Delta is +1.8 sd
    above the null centre, p ≈ 0.065. **Fixed** by centring on the permutation
    null's own mean, with a doubled-tail cross-check and a warning printed when
    the two disagree by more than 0.05. Validated on synthetic off-centre nulls:
    p = 0.98 where there is no effect, p = 0.00025 where there is.
    *Lesson: the internal contradiction between the two p-values is what caught
    it. Print more than one estimate of the same quantity — disagreement between
    them is a free correctness check.*
19. **A second GPU partition was unusable.** Every run in the project used the
    same GPU partition. The first attempt to use the second one failed at
    start-up (`NVMLError_InvalidArgument`). **Consequence: runs could not be
    parallelised; everything ran in sequence.** *Cost: one failed job. Caught
    because the log was checked rather than assumed.*

### Research-conduct decisions worth recording

17. **The shared data disk was 99% full**, and files belonging to another user
    could have been deleted to make room. **They were not deleted.** Data
    belonging to other users of a shared facility is not ours to remove; our own
    subfolder on another disk was used instead.

18. **Sample size was fixed before each run and never increased after seeing a
    result.** Every job script states its n in the header.

### Found while preparing the release (30 September 2026)

21. **The observation arms were not randomised.** The observation runs
    (`data/*_hard450_calibrate`) were generated by `run.py calibrate`, which,
    unlike the other commands used for formal runs, is called without
    `--randomize` in the job scripts. Every episode in those four runs therefore
    shows the same default surface text (`variant = v1` in
    `episode_features.csv`), whereas all consequence, salience and inert runs are
    randomised per rollout (`variant = v1rand`, seed 1000 + r). Earlier project
    notes wrongly stated that all arms were randomised. Found by checking the
    task text of the episode files: each observation run contains exactly one
    distinct task text. Consequence: comparisons within a run are unaffected;
    comparisons between the observation arm and another arm confound cue content
    with surface variation. The paper states this and bases
    its conclusions on inert-referenced comparisons, where both arms are
    randomised.
22. **Control runs failed at start-up twice (30 September 2026).** The first
    submission of `p4_neutral`, `p4_lexical` and `q14_neutral` stopped while vLLM
    was starting: another process occupied about 33 GB of the GPU partition, so
    the requested 85% of memory was not free. The second submission, directed
    to the second partition, failed as in item 19. No episode was generated in
    either attempt. `code/jobs/_warden_env.sh` was
    changed so that the vLLM memory fraction can be set per job (`GPU_UTIL`,
    default 0.85 as for every earlier run), and the runs were resubmitted with a
    smaller value. This changes throughput only.
23. **A simulation claim was restated from a fresh run.** The paper's
    false-positive rates for the permutation tests were re-derived with
    `python analysis/calib.py 0.5 1.0` (300 simulated datasets per pairing
    strength) and are quoted from that output.
24. **Numbers in the running text of the paper are now generated.** A draft of
    the paper typed some numbers in its text by hand (for example the
    first-action counts and the submission-rate ranges), although they matched
    the data. `analysis/make_text_numbers.py` now writes every such number to
    `results/textnumbers.tex` and checks each statement the text makes about the
    data. Two draft statements were corrected on the way: the residual length
    difference between the monitored and unmonitored cue blocks is 0.0--5.9% for
    the four cue families analysed (the draft range, 1.9--5.9%, included the
    "subtle" wording used only in pilot manipulation checks), and the observation
    cue does not share the template of the other three families.
25. **An inert baseline that failed its manipulation check was used as a
    reference in a draft.** Qwen2.5-14B answered that a human reviews the log in
    all 60 monitored and all 60 unmonitored trials of the line-wrapping cue
    (`data/manipulation_checks/mancheck_neutral_qwen14b_neutral.json`), so its
    inert arm does not provide a content-free baseline. The paper now marks every
    comparison against that arm (note b in its tables, set automatically by
    `analysis/make_ieee_tables.py` from the check file) and bases its conclusions
    on Qwen2.5-7B and Phi-4, whose control-cue checks returned UNKNOWN throughout.
