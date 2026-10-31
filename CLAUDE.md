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

- Orders:  POST /order {"lines":[{"item_id":1,"quantity":2}]}  -> records the order and reduces stock
- Database: in-memory by default; set PYSHOP_DB=sqlite:///path.db for a file (the regression harness does this)

## Conventions
- Prices are floats; filter boundaries are min-inclusive, max-exclusive.
- A filter arg of None means "no filter on that field".
- Placing an order reduces each item's stock by exactly the quantity ordered, once.
  The response total and the stored order total come from the same calculation.

## Gotchas to watch (the lab teaches you to warn the agent about these)
- The filter predicate is DUPLICATED: domain/catalog_filter.py has both
  item_matches and filter_predicate_for_count. Any new filter must be added to
  BOTH, or the list and the count drift.
- The repository count must apply the SAME filters as the list.

## Platform modules (representative examples for the regression lab)
- pyshop/services/pricing.py : PricingV2 (approved) and PricingLegacy (deprecated). Both write call_log.
- pyshop/batch/load_prices.py : nightly price load, parameterised by --region, --as-of, --tolerance.
- pyshop/calc/forecast.py + run_forecast.py : per-fund forecast, keyed (fund_id, scenario, period, metric).
- pyshop/web/forecast.py : GET/PUT /forecast/<id> (cached, PUT invalidates), /report/holdings, /funds/<id> UI,
  /cache/stats and test-only POST /clock/advance.
- Approved dependencies are listed in regression-check.yml, not inferred from names.
