# Regression check: <workflow>

**Compared:** base `<sha>` (`<ref>`) vs candidate `<sha>` (`<branch>`); config as of `<sha>`.

**Scenarios run:** `<id>`, `<id>`, ... (added: `<id>` because `<gap found in step 1>`)

## Differences

| Scenario | Kind | Field / table.key | Base | Candidate | Verdict | Reference |
| :- | :- | :- | :- | :- | :- | :- |
| order_two_mugs | data | items.1 stock | 8 | 6 | unintended, fixed in `<sha>` | second update in `<file:line>` |

## Fixes
- `<sha>`: <one line>. Before: <failing line from compare>. After: no differences.

## Proposed baseline updates (not applied)
- `<scenario>.json` `<field>`: <old> -> <new>, because <requirement line>.

## Gaps
- <path or dependency not covered, and why>
