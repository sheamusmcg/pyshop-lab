# Team Review Standard

Starter standard for Session 2. Review against it in Lab Block 5; revise it in Block 6
from what the three reviews missed or misreported.

## Four review passes (run in order)
1. Intent - does the change meet the acceptance criteria in docs/spec.md?
2. Design - does it fit our architecture and conventions?
3. Implementation - bugs, edge cases, error handling.
4. Tests - do the tests actually protect the change?

## Four questions for any test
- Defect detection: what incorrect behavior would cause this test to fail?
- Assertions: do the assertions verify the required outcome?
- Scenarios: which relevant boundaries, empty results and error paths are tested?
- Expected results: are expected values taken from the acceptance criteria in docs/spec.md, independently of the implementation?

## Finding severity
Blocker / Major / Minor / Nit - state severity on every finding.

## Evidence required
Each finding names the file, the specific case, how to reproduce, and the docs/spec.md criterion it violates, if any.

## High-risk checks (stricter bar + a human reviewer)
Apply these to auth, infrastructure/deploy, security-sensitive, and compliance paths:
- Auth/authz: who can do what - is the check in the right place, fail-closed, and tested for the deny case?
- Infra/deploy: what's the blast radius if this is wrong - and is there a rollback?
- Security: are inputs validated, secrets kept out of logs/outputs, queries/commands constructed safely?
- Compliance: does it touch regulated data or audit trails, is the handling logged, does it need sign-off before merge?
- For all of the above: require a human reviewer and ask for evidence and rationale, not just the agent's answer.

## When a human must review (not just the automated pass)
- Anything in the high-risk categories.
- Any change where the tests were also written by the agent and not independently judged.
