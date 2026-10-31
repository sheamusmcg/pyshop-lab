---
name: regression-check
description: Establish regression coverage for a workflow's responses and persisted data, compare the original and changed versions, investigate differences, and fix unintended changes. Use before and after refactoring, when asked to "check for regressions", "compare against main", "capture a baseline", or when a change touches code that writes to the database. Requires regression-check.yml at the repo root.
---

# Regression check

Compare what a workflow does before and after a change: the HTTP responses and
the rows it writes. The scripts do the capturing and the diffing; your job is
scope, interpretation, investigation and the fix. Never edit a baseline file.

## Inputs you need

- `regression-check.yml` at the repo root: how to start the app, which tables to
  snapshot, the scenarios, and what is normalized. If it is missing, stop and
  propose one (see `reference/config.md`); do not invent commands.
- The base ref to compare against (default `origin/main`) and the change under
  test (the current branch).
- The requirement or ticket for the change, so you can tell intended differences
  from unintended ones.

## Procedure

Run the steps in order. Each one produces evidence; keep it for the report.

### 1. Investigate the workflow

Read the entry point, the services it calls, every database write on the path,
and the existing tests. Then answer, in writing:

- Which responses and which persisted rows does this workflow produce?
- Which of those do the existing tests check? Which are never queried after the
  transaction? (A test that checks the response but not the rows is the common gap.)
- Which scenarios should a baseline cover: the normal path, a multi-item or
  multi-step case, each rejection path, and the boundary the requirement names.

Evidence: the scenario list and the business fields each scenario validates.
If the config's `scenarios` section lacks one you need, add it to the config
(that is a reviewed file change) and say so.

### 2. Establish regression coverage

Write any missing integration tests for the gaps found in step 1, following
the project's existing test files. Then capture the baseline on the **unchanged**
code:

```
python .claude/skills/regression-check/scripts/capture.py --label base
```

This runs every scenario against a fresh database and writes one JSON per
scenario into `baseline_dir`, each tagged with the commit hash. Run it twice; if
the two captures differ, the baseline is unstable (time, ordering, randomness):
add a `normalize` rule for the field or fix the nondeterminism before continuing.

Evidence: the baseline files and the commit they were captured at.

### 3. Run both versions in isolation

```
.claude/skills/regression-check/scripts/run_both.sh origin/main
```

This checks the base ref out into a git worktree, captures base and candidate
with separate fresh databases, and compares. The committed baseline is not
touched. If the app needs a server database rather than SQLite, the config's
`database.reset` must point at a reset+seed command; without one, stop and ask.

### 4. Read the comparison

`compare.py` prints three kinds of difference per scenario:

- **business**: a field the config named, or the HTTP status. Treat as a defect
  until the requirement says otherwise.
- **response**: any other response field. Usually noise or a presentational
  change; still list it.
- **data**: a changed, added or missing row in a snapshotted table. A data
  difference with an unchanged response is the case this skill exists for.

For each difference decide: intended by the change (cite the requirement line),
unintended, or unclear. Unclear goes to escalation, not to a guess.

### 5. Investigate and repair unintended differences

Reproduce with the single scenario (`capture.py --scenario <id>` on the
candidate), read the code on the path, form one hypothesis, make the smallest
fix, rerun `run_both.sh`. Show the failing output and the passing rerun.

Do not make a difference disappear by changing the baseline, loosening a
normalize rule, or deleting an assertion. If the new behaviour is correct and
the baseline is wrong, say so in the report and propose the baseline update;
a person applies it (see Rules).

### 6. Return the review package

Put this in the PR description, in this order:

1. Commits compared (base and candidate hashes) and the config version.
2. Scenarios run, and any you added.
3. Differences: intended (with the requirement reference), unintended (with the
   fix commit), unresolved.
4. Proposed baseline updates, if any, each with a reason.
5. Gaps: paths not covered, dependencies not available, anything skipped.

## Rules

- **Baselines are read-only to you.** A change under `baseline_dir` or a removed
  assertion fails the `baseline-guard` CI check unless the PR carries the
  `baseline-change` label and a code owner approves. Propose; do not apply.
- **Seeded data only.** Baselines come from the config's seed, never from a
  production or shared database. Do not capture secrets, tokens or personal
  data; if a response contains them, add a normalize rule first.
- **Deterministic comparison.** Normalization is declared in the config, not
  improvised in a prompt. If a field varies run to run, that is a config change.
- **One database per run.** Never point two captures at the same database.

## Escalate instead of guessing

Stop and report when:

- the requirement does not say whether a difference is intended
- the baseline is unstable after one normalize attempt
- the app cannot start, or a dependency (external service, server database) is
  unavailable in this environment
- the fix would change behaviour outside the workflow under test
- the config is missing or names commands you cannot verify

State what you found, what you need, and what you did not change.

## Files

- `scripts/capture.py`: scenarios -> baseline JSON (fresh DB per scenario, commit hash recorded)
- `scripts/compare.py`: field-level diff of two capture directories; exit 1 on differences
- `scripts/run_both.sh`: worktree for base, capture both, compare
- `reference/config.md`: the `regression-check.yml` schema with a .NET example
- `reference/report-template.md`: the review-package layout
