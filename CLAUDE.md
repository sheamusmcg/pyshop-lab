# PyShop - project guidance for the agent

Flask catalog app, layered like eShopOnWeb. This is a STARTER CLAUDE.md -
the lab has you extend it.

## Architecture - keep the layers clean
- domain/        : entities + filter logic. No Flask, no SQLAlchemy imports.
- infrastructure/: SQLAlchemy models + repository. The only place that talks SQL.
- web/           : Flask routes + view-models + templates. No business logic.
Dependencies point inward: web -> infrastructure -> domain. Never the reverse.

## Build & test
- Run the app:  python -m pyshop.web.app   (http://localhost:5001)
- Unit + integration:  python -m pytest tests/test_unit.py tests/test_integration.py
- E2E (Playwright):     python -m pytest tests/test_e2e.py
- Coverage:  coverage run -m pytest ... ; coverage report --include="pyshop/*"

## Conventions
- Prices are floats; filter boundaries are min-inclusive, max-exclusive.
- A filter arg of None means "no filter on that field".

## Gotchas to watch (the lab teaches you to warn the agent about these)
- The filter predicate is DUPLICATED: domain/catalog_filter.py has both
  item_matches and filter_predicate_for_count. Any new filter must be added to
  BOTH, or the list and the count drift.
- The repository count must apply the SAME filters as the list.
