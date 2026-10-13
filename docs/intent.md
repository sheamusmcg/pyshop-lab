# intent.md — Catalog price-range filter

## The request
Customers browsing the catalog want to narrow results by price, while keeping
the brand and type filters they've already selected.

## Desired outcome
A price-range control sits alongside the existing brand and type filters.
Selecting a range narrows the results; the brand and type selections still apply.

## Affected users
Shoppers using the catalog page. No admin or back-office change.

## Constraints
- Match the existing filter bar's styling and behaviour.
- The result list and the paginated count must agree.
- No change to how catalog data is stored.

## Open questions
- Is the upper price boundary inclusive or exclusive? An item priced exactly at
  a boundary (e.g. $15 in a $10–$15 range) must not land in two ranges.
