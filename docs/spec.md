# spec.md — Catalog price-range filter

Derived from intent.md. Reviewed and approved before implementation.

## Requirements (numbered, testable)
1. A price-range control appears alongside the brand and type filters.
2. With a price range and a brand selected, every returned item matches both
   filters; the total count uses the same criteria.
3. Clearing the price range restores the list within the remaining filters.
4. Paginated counts use the same filter criteria as the results.
5. Minimum price is inclusive; maximum price is exclusive. A $15 item is
   excluded from $10–$15 and included in $15–$20.

## Proposed design
- UI: a range control in the catalog filter bar, styled to match brand/type.
- Request: a price parameter carried with the existing filter parameters.
- Query: extend the catalog filter so price composes with brand and type; keep
  the result query and the count query in sync so they can't diverge.

## Constraint mapping
- Brand/UX: reuse the existing filter styling.
- Data: no new personal data and no authentication change. Validate the price
  parameter and review the query's performance impact.

## Resolved concerns
- Boundary (from intent.md open question): resolved as R5 above — min inclusive,
  max exclusive. Owner: product requester, with the engineer. Session 2's tests
  verify an item priced exactly at the boundary.

## Source of truth
This spec records what was asked and decided. The approved requirement still
lives in the team's tracker (Jira / Azure DevOps); these files link to it.
