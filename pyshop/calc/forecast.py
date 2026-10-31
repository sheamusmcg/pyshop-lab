"""Fund cashflow forecast. REPRESENTATIVE EXAMPLE, not a real forecasting model.

For each fund, forecasts quarterly distributions and capital calls for four
periods under two scenarios. The formula is deliberately simple; what matters
for the course is that it has branches (fund type, credit line, scenario) so a
change can affect some funds and not others.

Output rows are keyed by (fund_id, scenario, period, metric). A comparison
across versions should be made row by row on that key, never on totals alone.
"""
PERIODS = ["2027Q1", "2027Q2", "2027Q3", "2027Q4"]
SCENARIOS = {"base": 1.00, "downside": 0.85}

# Annual distribution and call rates by fund type (as fractions of commitment).
DIST_RATE = {"equity": 0.12, "credit": 0.09, "real_assets": 0.07}
CALL_RATE = {"equity": 0.10, "credit": 0.14, "real_assets": 0.08}


def forecast_fund(fund):
    """Return a list of dict rows for one fund."""
    rows = []
    remaining = fund.commitment * (1.0 - fund.called_pct)
    nav = fund.commitment * fund.called_pct
    for scenario, factor in SCENARIOS.items():
        rem, cur_nav = remaining, nav
        for period in PERIODS:
            dist = cur_nav * DIST_RATE[fund.fund_type] / 4.0 * factor
            call = min(rem, fund.commitment * CALL_RATE[fund.fund_type] / 4.0)
            if fund.has_credit_line:
                # Credit-line funds defer the first quarter's call to the next quarter.
                if period == PERIODS[0]:
                    call = 0.0
                elif period == PERIODS[1]:
                    call = min(rem, 2 * fund.commitment * CALL_RATE[fund.fund_type] / 4.0)
            rem -= call
            cur_nav = cur_nav + call - dist
            for metric, value in (("distribution", dist), ("call", call), ("nav", cur_nav)):
                rows.append({"fund_id": fund.id, "scenario": scenario, "period": period,
                             "metric": metric, "value": round(value, 2)})
    return rows


def run_all(session, fund_ids=None):
    from sqlalchemy import select, delete
    from pyshop.infrastructure.models import FundModel, ForecastModel
    q = select(FundModel)
    if fund_ids:
        q = q.where(FundModel.id.in_(fund_ids))
    funds = session.scalars(q.order_by(FundModel.id)).all()
    session.execute(delete(ForecastModel).where(ForecastModel.fund_id.in_([f.id for f in funds])))
    n = 0
    for f in funds:
        for r in forecast_fund(f):
            session.add(ForecastModel(**r)); n += 1
    session.commit()
    return len(funds), n
