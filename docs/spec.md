# spec.md — Catalog price-range filter

Derived from intent.md. Reviewed and approved before implementation.

## Requirements (numbered, testable)
- **R1.** A price-range control appears alongside the brand and type filters.
- **R2.** With a price range and a brand selected, every returned item matches
  both filters; the total count uses the same criteria.
- **R3.** Clearing the price range restores the list within the remaining filters.
- **R4.** Paginated counts use the same filter criteria as the results.
- **R5.** Minimum price is inclusive; maximum price is exclusive. A $15 item is
  excluded from $10–$15 and included in $15–$20.

## Acceptance criteria
Each criterion is verifiable. R5's boundary rule — minimum inclusive, maximum
exclusive — holds throughout.

- [ ] **AC1 — Filter control (R1):** a price-range control appears alongside the
      existing brand and type filters and reuses their styling.
- [ ] **AC2 — Combined filters (R2):** when a price range, a brand, and a type
      are selected, every returned item satisfies all selected filters.
- [ ] **AC3 — Minimum boundary (R5):** an item whose price equals the selected
      minimum is included, provided it satisfies the other selected filters.
- [ ] **AC4 — Maximum boundary (R5):** an item whose price equals the selected
      maximum is excluded.
- [ ] **AC5 — Boundary example (R5):** an item priced at $15 is excluded from the
      $10–$15 range and included in the $15–$20 range, given the other filters.
- [ ] **AC6 — Clearing the range (R3):** clearing the price range removes only the
      price restriction; any selected brand and type filters stay applied.
- [ ] **AC7 — Matching totals (R2, R4):** the total count applies the same price,
      brand, and type criteria as the item list, so the list and the count never
      diverge. Verified at the repository level, where the list and the count
      share one filter path.

AC2 and AC7 make the design's filter composition and count/list parity explicit;
confirm them in review rather than treating them as new, silently approved
requirements.

## Proposed design
- **Control type:** preset price bands (for example Under $10, $10–$15, $15–$20,
  $20 and over), styled to match the existing brand and type dropdowns. Preset
  bands — not free min/max entry — keep the boundary rule testable and avoid
  invalid-range input.
- **Request:** a price parameter carried with the existing filter parameters.
- **Query:** extend the catalog filter so price composes with brand and type;
  keep the result query and the count query in sync so they can't diverge.

## Constraint mapping
- Brand/UX: reuse the existing filter styling.
- Data: no new personal data and no authentication change. Review the query's
  performance impact (the filter runs per request).

## Resolved concerns
- **Boundary (from intent.md open question):** resolved as R5 — min inclusive,
  max exclusive. Owner: product requester, with the engineer. Session 2's tests
  verify an item priced exactly at the boundary.
- **Invalid or reversed ranges:** not reachable with preset bands, so no min/max
  validation is specified. An unrecognized price value is treated as no price
  filter, consistent with how brand and type handle an unknown value.
- **No matching results:** the list is empty and the total count is zero; the
  remaining filters stay applied.

## Source of truth
This spec records what was asked and decided. The approved requirement still
lives in the team's tracker (Jira / Azure DevOps); these files link to it.
