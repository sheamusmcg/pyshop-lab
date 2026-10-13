# plan.md — Catalog price-range filter (example)

An example of the written form of a plan. In most sessions the planning step
runs in **plan mode** — the agent proposes the plan, you refine it in the chat,
and it's gone when the session ends. Write a `plan.md` like this one only when
the change is higher-risk or crosses a handoff and you want the plan reviewed or
committed alongside the code. It is derived from the approved `spec.md`.

Spec: `docs/spec.md` (R1–R5, AC1–AC7). Boundary rule: min inclusive, max exclusive.

## Approach
Follow the existing brand/type filter pattern at every layer. The price filter
composes with brand and type; the paged list and the total count go through the
same filter path so they can't diverge.

## Changes by layer

1. **Domain — the filter predicate** (`pyshop/domain/catalog_filter.py`)
   - Add optional `price_min` / `price_max` (default `None`) to **both**
     `item_matches` and `filter_predicate_for_count`.
   - Rule: `price_min` inclusive, `price_max` exclusive (`min <= price < max`).
   - Both predicates are duplicates and must change together (R2, R4, AC7).

2. **Infrastructure — the repository** (`pyshop/infrastructure/models.py`)
   - Add the price bounds to `list_items` and `count_items`; pass the same
     arguments to both predicates so the list and the count stay in sync.

3. **Web — request and view-model** (`pyshop/web/catalog.py`)
   - Read a `price` parameter alongside `brand` and `type`.
   - Map the preset bands (Under $10 / $10–$15 / $15–$20 / $20 and over) to
     `(min, max)` bounds in the view-model; the domain sees only min/max.
   - An unrecognized value means no price filter (same as brand/type).

4. **Template — the control** (`pyshop/web/templates/catalog.html`)
   - Add a Price `<select>` after Type, same markup and submit behavior,
     preserving the selected band (R1, AC1).

## Tests
- Unit (`tests/test_unit.py`): min-inclusive, max-exclusive, the $15 boundary
  example (AC3–AC5), and a check that the list and count predicates agree (AC7).
- Integration (`tests/test_integration.py`): price + brand together returns
  only matching items and a matching total (AC2, AC6).

## Risks / watch-outs
- The duplicated predicate: a new filter added to one copy but not the other
  makes the list and count drift. Change both.
- Keep the UI labels in the web layer; the domain stays generic (min/max).

## Done when
AC1–AC7 pass, the app shows the Price dropdown working alongside brand and type,
and the unit + integration tests are green.
