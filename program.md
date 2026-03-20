# Autoresearch Operational Program

Complete step-by-step instructions for running the autonomous experiment loop.

## Table of Contents
- [Configuration Variables](#configuration-variables)
- [Phase 1: Setup](#phase-1-setup)
- [Phase 2: Baseline](#phase-2-baseline)
- [Phase 3: Experiment Loop](#phase-3-experiment-loop)
- [Crash Recovery](#crash-recovery)
- [Experiment Strategy Guide](#experiment-strategy-guide)

## Configuration Variables

These are established during setup and remain fixed for the entire session:

| Variable | Description | Example |
|----------|-------------|---------|
| `TARGET_FILE` | The single mutable file | `train.py` |
| `RUN_CMD` | Command to run one experiment | `python train.py` |
| `TIMEOUT_SEC` | Max seconds per experiment | `300` |
| `METRIC_NAME` | Name of the metric being optimized | `val_loss` |
| `METRIC_DIRECTION` | `minimize` or `maximize` | `minimize` |
| `METRIC_EXTRACT` | How to extract metric from output | `grep "^val_loss:" run.log \| awk '{print $2}'` |
| `RESULTS_FILE` | Path to results log | `results.tsv` |
| `MAX_CONSECUTIVE_CRASHES` | Stop after N crashes in a row | `3` |

## Phase 1: Setup

```
1. Confirm all configuration variables with the user
2. Verify TARGET_FILE exists and is readable
3. Verify RUN_CMD works (dry run if possible)

4. Git safety — ABSOLUTE, no exceptions:
   a. Check current branch: git branch --show-current
   b. If on main/master → create experiment branch:
      git checkout -b autoresearch/session-$(date +%Y-%m-%d)
   c. If already on a non-main branch → confirm with user before continuing
   d. NEVER run git push for any reason

5. Ensure git repo has clean working tree:
   git add -A && git commit -m "autoresearch: baseline state"

6. Ensure RESULTS_FILE and run.log are gitignored:
   grep -q "results.tsv" .gitignore || echo "results.tsv" >> .gitignore
   grep -q "run.log" .gitignore     || echo "run.log"     >> .gitignore
   git add .gitignore && git commit -m "autoresearch: ignore results and logs" 2>/dev/null || true

7. Create RESULTS_FILE with header:
   echo "commit\tmetric\tstatus\tdescription" > results.tsv

8. Initialize counters:
   CONSECUTIVE_CRASHES = 0
   EXPERIMENT_NUMBER = 1
```

## Phase 2: Baseline

```
1. Run: timeout <TIMEOUT_SEC> <RUN_CMD> > run.log 2>&1
2. If exit code != 0:
   Report error to user and stop — cannot proceed without a working baseline
3. Extract metric: <METRIC_EXTRACT>
4. Validate metric is a number — if not, stop and ask user to fix METRIC_EXTRACT
5. Record baseline:
   BASELINE = extracted metric value
   BEST = BASELINE
   COMMIT_HASH = $(git rev-parse --short HEAD)
6. Log: echo "<COMMIT_HASH>\t<BASELINE>\tbaseline\tinitial baseline run" >> results.tsv
7. Report to user:
   "Baseline <METRIC_NAME>: <BASELINE>
    Branch: $(git branch --show-current)
    Timeout per experiment: <TIMEOUT_SEC>s
    Max consecutive crashes: <MAX_CONSECUTIVE_CRASHES>
    Starting experiment loop. Interrupt at any time to stop."
```

## Phase 3: Experiment Loop

Execute this loop until a stop condition is met.

**Stop conditions:**
- User interrupts
- `CONSECUTIVE_CRASHES >= MAX_CONSECUTIVE_CRASHES`
- User-defined experiment limit reached (if set)

**Never stop for any other reason.**

```
while true:
    # 1. ANALYZE
    Read TARGET_FILE to understand current state
    Read RESULTS_FILE to see what has been tried — do not repeat failed experiments
    Formulate ONE hypothesis for improvement

    # 2. MODIFY
    Make ONE focused change to TARGET_FILE
    Write a short description of the change (max 60 chars)

    # 3. COMMIT
    git add <TARGET_FILE>
    git commit -m "exp <EXPERIMENT_NUMBER>: <short description>"
    COMMIT_HASH = $(git rev-parse --short HEAD)

    # 4. RUN
    timeout <TIMEOUT_SEC> <RUN_CMD> > run.log 2>&1
    EXIT_CODE = $?

    # 5. EVALUATE
    if EXIT_CODE != 0:
        # Crashed or timed out
        CONSECUTIVE_CRASHES += 1
        echo "<COMMIT_HASH>\tN/A\tcrashed\t<description>" >> results.tsv
        git reset --hard HEAD~1

        if CONSECUTIVE_CRASHES >= MAX_CONSECUTIVE_CRASHES:
            STOP — report to user:
            "Stopped after <N> consecutive crashes.
             Last error summary: <first 5 lines of run.log>
             Please investigate and restart when ready."
            exit loop

        Analyze error in run.log for next attempt
        Continue to next iteration

    else:
        CONSECUTIVE_CRASHES = 0
        RESULT = <METRIC_EXTRACT>

        if RESULT is better than BEST (per METRIC_DIRECTION):
            # Improvement — KEEP
            BEST = RESULT
            echo "<COMMIT_HASH>\t<RESULT>\tkept\t<description>" >> results.tsv
            Report: "✓ EXP <N> [<COMMIT_HASH>]: <METRIC_NAME> <RESULT> (was <previous BEST>) — KEPT"
        else:
            # No improvement — DISCARD
            echo "<COMMIT_HASH>\t<RESULT>\tdiscarded\t<description>" >> results.tsv
            git reset --hard HEAD~1
            Report: "✗ EXP <N> [<COMMIT_HASH>]: <METRIC_NAME> <RESULT> (best: <BEST>) — discarded"

    # 6. NEXT
    EXPERIMENT_NUMBER += 1
    Continue immediately
```

## Crash Recovery

When a run crashes or times out:

1. **Do NOT stop the loop** unless `MAX_CONSECUTIVE_CRASHES` is reached
2. Read `run.log` to diagnose the error
3. Common causes and responses:

| Error type | Response |
|---|---|
| Syntax error | The modification had a bug. Revert and try a different approach. |
| OOM / resource exhaustion | Change was too expensive. Revert and try something smaller. |
| Import error | Tried to use unavailable dependency. Revert and use only existing imports. |
| Timeout (exit 124) | Change made things too slow. Revert and try something lighter. |
| Test failure | Change broke correctness. Revert immediately — correctness is non-negotiable. |

4. After reverting, **use the crash information** to inform the next experiment — never retry the exact same change

## Experiment Strategy Guide

### Exploration vs Exploitation

- **Early experiments (1-20)**: Explore broadly. Try different algorithmic approaches, major hyperparameter changes, structural modifications.
- **Mid experiments (20-50)**: Focus on what worked. Fine-tune parameters around successful changes.
- **Late experiments (50+)**: Exploit aggressively. Small variations on the best-performing configuration.

### Idea Generation

For each experiment, draw from these categories:

**Parameters & Constants**
- Scale numeric constants up/down (2x, 0.5x, 10x)
- Try known good values from literature or common practice
- Grid-search around values that have worked

**Algorithm & Logic**
- Replace algorithm X with algorithm Y
- Add/remove caching or memoization
- Change iteration order or data access patterns
- Simplify conditional logic

**Architecture & Structure**
- Add/remove layers, stages, or processing steps
- Change data flow (parallel vs sequential, batched vs streaming)
- Modify buffer/batch/window sizes

**Efficiency**
- Vectorize loops
- Reduce memory allocations
- Use more efficient data structures
- Remove unnecessary computation

**Simplification (high value!)**
- Remove code that doesn't contribute to the metric
- Replace complex logic with simpler alternatives
- Inline unnecessary abstractions
- Delete dead code paths

### Domain-Specific Strategies

**ML training**
Metric: val_loss, accuracy, val_bpb
Try: learning rate schedule, optimizer (Adam/Muon/SGD), batch size, model depth, dropout rate, weight decay, gradient clipping, layer normalization placement

**UI/UX improvement**
Metric: Lighthouse score, bundle size, render time, linting errors
Try: component splitting, lazy imports, memoization, accessibility fixes, CSS consolidation, dead code removal

**Backend / API**
Metric: p95 latency, requests/sec, error rate
Try: query optimization, N+1 fixes, connection pooling, response caching, payload compression, index hints

**CLI tools**
Metric: execution time, output lines, test pass rate
Try: output readability, error message clarity, flag naming, help text, exit codes, streaming vs buffered output

### Anti-Patterns to Avoid

- Making multiple unrelated changes in one experiment
- Repeating an exact experiment that already failed (check results.tsv first)
- Changing the evaluation metric or extraction method
- Adding external dependencies without approval
- Making changes so large they are likely to crash
- Running `git push` for any reason
- Committing to main/master