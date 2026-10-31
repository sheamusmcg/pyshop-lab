---
name: regression-check
description: Find untested workflows and conditional paths, build integration and regression coverage for them (batch loads, services with cache conditions, calculations across a population, UI workflows), capture baselines, compare original and changed versions, assert approved dependencies, investigate and fix differences. Use for "find what we aren't testing", "check for regressions", "compare against main", "does this still use the old service", or before refactoring anything that writes data. Requires regression-check.yml at the repo root.
---

# Regression check

Two questions, asked separately, because a baseline can preserve a defect:

| Check | Question | Tool |
| :- | :- | :- |
| Regression comparison | Did behaviour or data change between versions? | `compare.py --baseline` |
| Requirement and dependency assertion | Does this workflow use approved dependencies and produce the required result? | `compare.py` on one capture, plus `expected_values` |

The scripts capture and diff. You discover, interpret, investigate and fix.
You never edit a baseline, loosen a tolerance, or remove an assertion to pass.

## Inputs

- `regression-check.yml` at the repo root (`reference/config.md`). Missing: stop and propose one.
- The base ref (default `origin/main`) and the change under test.
- The requirement for the change, so intended differences can be told from unintended ones.
- The approved and deprecated dependency lists come from the config. **Never infer that a service is deprecated from its name.**

## Procedure

### 1. Discover: build the workflow and coverage inventory

Before capturing anything, inspect the codebase and write an inventory. Use
`scripts/inventory.py` to seed it from entry points and the existing config,
then complete it by reading code. For each workflow:

- **Entry point**: endpoint, batch command, report, screen, or calculation module.
- **Conditional paths**: parameters, flags, configuration, dates, fund types,
  regions, fallbacks. Name each branch and what selects it.
- **Dependencies**: service clients, configured endpoints, queries, stored
  procedures. Mark each approved / deprecated / unknown per the config.
- **Existing tests**: which paths they exercise, and whether they assert on
  data and dependencies or only on completion.
- **Gaps**: paths or conditions with no scenario, or with assertions that
  would not detect a wrong result or a wrong dependency.

Attach file and line references to every finding. State plainly that the
inventory is a proposed map from code inspection for an engineer to confirm,
not a claim of exhaustive coverage. A text match on an old endpoint name is a
lead, not proof; proof comes from the call log in step 4.

Prioritise gaps where a rarely used path or parameter combination may call a
deprecated dependency, then calculations compared only by totals, then
cached reads after writes.

### 2. Establish coverage: scenarios, fixtures, tests

For each prioritised gap, add a scenario to `regression-check.yml`:

- `batch`: the command with the parameter combination that selects the path.
- `calculation`: the command that produces the result population; set
  `result_table`, and add independently derived rows to an `expected_values`
  file (derived from the documented formula or a reviewed source, never copied
  from a capture).
- `service`: request / cache / clock steps. Do not clear the cache before each
  request; the cache state is the condition under test. Cover empty, hit,
  update-then-read, expiry, and source-changed-after-caching as the config allows.
- `ui`: the browser read of the displayed business value after the workflow.

Set `expect_dependencies: approved_only` on any scenario that should not
touch a deprecated service. Write any missing integration tests in the
project's test suite as well; the scenario catalogue complements them.

### 3. Capture the baseline on the unchanged code

```
python .claude/skills/regression-check/scripts/capture.py --label base
```

Run it twice. If the two captures differ, the baseline is unstable: add a
`normalize` rule for the varying field or fix the nondeterminism. Then run the
requirement checks on the baseline alone:

```
python .claude/skills/regression-check/scripts/compare.py --candidate tests/baselines
```

A dependency or expected-value failure here is a pre-existing defect. Report
it as such; do not "fix" it by removing the assertion.

### 4. Run both versions and compare

```
.claude/skills/regression-check/scripts/run_both.sh origin/main
```

Base runs in a git worktree; both sides get fresh databases. Read the output:

- **business / response / data** differences: changed between versions.
  Calculation scenarios print how many keys (funds) differ out of the population.
- **dependency**: a call to a service not in `approved_dependencies`, with the
  call count from the log.
- **expected**: an independently verified value no longer matches.
- **missing / duplicate**: rows or scenarios present on one side only, or keyed
  twice. These are findings, never skipped.

For each: intended (cite the requirement), unintended, or unclear.

### 5. Investigate and repair

Reproduce with one scenario (`capture.py --scenario <id>`), read the code on
that path, form one hypothesis, make the smallest fix, rerun `run_both.sh`.
Keep the failing output and the passing rerun.

### 6. Return the review package

Use `reference/report-template.md`: commits compared; inventory and the gaps
chosen; scenarios added; differences by kind with verdicts; dependency
findings with evidence; fixes with before/after output; proposed baseline
updates (not applied); remaining gaps.

## Rules

- Baselines under `baseline_dir` and tolerances in the config are changed only
  by a reviewed PR with the `baseline-change` label; CI (`baseline-guard`)
  enforces it. You propose, a person applies.
- Tolerances are approved values, not chosen to make a comparison pass.
- Seeded or restored controlled data only. No production data in baselines; no
  secrets or personal data in captures (normalize them first).
- One database per run; the same starting dataset and parameters on both sides.
- Dependency proof is observable evidence (call log, captured requests, server
  log), not source text.

## Escalate instead of guessing

Stop and report when the requirement does not settle whether a difference is
intended; the baseline is unstable after one normalize attempt; the app, a
dependency or a controlled dataset is unavailable here; a fix would change
behaviour outside the workflow under test; the config is missing or names
commands you cannot verify; or the approved-dependency list does not cover a
service you found.

## Files

- `scripts/inventory.py`: seeds the workflow inventory from entry points, commands and config
- `scripts/capture.py`: scenarios -> captures (responses, stdout summary, rows, calls)
- `scripts/compare.py`: regression diff with tolerances + dependency and expected-value checks
- `scripts/run_both.sh`: base in a worktree, capture both, compare
- `reference/config.md`, `reference/report-template.md`
