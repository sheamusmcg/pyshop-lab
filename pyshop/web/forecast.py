"""Forecast and report endpoints. REPRESENTATIVE EXAMPLE.

GET  /forecast/<fund_id>            cached per fund (TTL from app config)
PUT  /forecast/<fund_id>            {"scenario","period","metric","value"} - the supported
                                    update path; MUST invalidate that fund's cache
GET  /report/holdings?as_of=YYYY-MM-DD   holdings valuation per fund (rarely used report)
GET  /cache/stats                   hit/miss counts (test visibility)
POST /clock/advance {"seconds": n}  test-only: advance the injectable clock
"""
from datetime import date
from flask import Blueprint, jsonify, request, current_app, render_template
from sqlalchemy import select
from pyshop.infrastructure.models import ForecastModel, FundModel
from pyshop.services.pricing import PricingV2, PricingLegacy, PricingUnavailable

forecast_bp = Blueprint("forecast", __name__)


def _rows(session, fund_id):
    rows = session.scalars(select(ForecastModel).where(ForecastModel.fund_id == fund_id)
                           .order_by(ForecastModel.scenario, ForecastModel.period, ForecastModel.metric)).all()
    return [{"scenario": r.scenario, "period": r.period, "metric": r.metric, "value": r.value} for r in rows]


@forecast_bp.get("/forecast/<int:fund_id>")
def get_forecast(fund_id):
    cache, session = current_app.config["CACHE"], current_app.config["SESSION"]
    key = f"forecast:{fund_id}"
    cached = cache.get(key)
    if cached is not None:
        return jsonify({"fund_id": fund_id, "rows": cached, "from_cache": True})
    rows = _rows(session, fund_id)
    if not rows:
        return jsonify({"error": "no forecast for fund"}), 404
    cache.set(key, rows)
    return jsonify({"fund_id": fund_id, "rows": rows, "from_cache": False})


@forecast_bp.put("/forecast/<int:fund_id>")
def update_forecast(fund_id):
    """Supported update path. Writes the row and invalidates the cached forecast."""
    body = request.get_json(silent=True) or {}
    session, cache = current_app.config["SESSION"], current_app.config["CACHE"]
    row = session.scalar(select(ForecastModel).where(
        ForecastModel.fund_id == fund_id, ForecastModel.scenario == body.get("scenario"),
        ForecastModel.period == body.get("period"), ForecastModel.metric == body.get("metric")))
    if row is None:
        return jsonify({"error": "no such forecast row"}), 404
    try:
        row.value = float(body["value"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "value required"}), 400
    session.commit()
    cache.invalidate(f"forecast:{fund_id}")
    return jsonify({"fund_id": fund_id, "updated": True, "value": row.value})


@forecast_bp.get("/report/holdings")
def holdings_report():
    """Holdings valuation: called NAV x price per fund. An infrequently used
    report. It was written before the pricing migration and still prices
    through the previous client."""
    session = current_app.config["SESSION"]
    as_of = date.fromisoformat(request.args.get("as_of", "2026-10-30"))
    region = request.args.get("region")
    pricing = PricingLegacy(session)
    q = select(FundModel)
    if region:
        q = q.where(FundModel.region == region)
    out = []
    for f in session.scalars(q.order_by(FundModel.id)).all():
        price = pricing.price(f.id, as_of)
        units = round(f.commitment * f.called_pct / 100.0, 4)
        out.append({"fund": f.code, "units": units, "price": price,
                    "value": round(units * price, 2) if price is not None else None})
    return jsonify({"as_of": as_of.isoformat(), "region": region, "pricing_service": pricing.name,
                    "rows": out, "total_value": round(sum(r["value"] or 0 for r in out), 2)})


@forecast_bp.get("/price/<int:fund_id>")
def get_price(fund_id):
    """Latest price for a fund, cached per fund.

    Freshness policy (illustrative, stated so it can be tested):
      - A cached price is served for up to the TTL.
      - If the pricing service is unavailable, a cached price may be served
        past its TTL for up to 24h, flagged stale=true. With no cached price,
        the response is 503.
    The stale-fallback window is a separate, longer-lived entry.
    """
    cache, session = current_app.config["CACHE"], current_app.config["SESSION"]
    as_of = date.fromisoformat(request.args.get("as_of", "2026-10-30"))
    key = f"price:{fund_id}:{as_of.isoformat()}"
    cached = cache.get(key)
    if cached is not None:
        return jsonify({"fund_id": fund_id, "as_of": as_of.isoformat(), "price": cached, "from_cache": True, "stale": False})
    try:
        price = PricingV2(session).price(fund_id, as_of)
    except PricingUnavailable:
        fallback = current_app.config["STALE"].get(key)
        if fallback is None:
            return jsonify({"error": "pricing unavailable and no cached price"}), 503
        return jsonify({"fund_id": fund_id, "as_of": as_of.isoformat(), "price": fallback, "from_cache": True, "stale": True})
    cache.set(key, price)
    current_app.config["STALE"].set(key, price)
    return jsonify({"fund_id": fund_id, "as_of": as_of.isoformat(), "price": price, "from_cache": False, "stale": False})


@forecast_bp.get("/cache/stats")
def cache_stats():
    return jsonify(current_app.config["CACHE"].stats())


@forecast_bp.post("/clock/advance")
def clock_advance():
    """Test-only. Advances the injectable clock so cache expiry is deterministic."""
    secs = float((request.get_json(silent=True) or {}).get("seconds", 0))
    current_app.config["CLOCK"].advance(secs)
    return jsonify({"now": current_app.config["CLOCK"]()})


@forecast_bp.get("/funds/<int:fund_id>")
def fund_page(fund_id):
    """UI view: the fund's forecast, read through the same cached path as the API."""
    session = current_app.config["SESSION"]
    fund = session.get(FundModel, fund_id)
    if fund is None:
        return "not found", 404
    resp = get_forecast(fund_id)
    data = resp.get_json() if not isinstance(resp, tuple) else {}
    rows = data.get("rows", [])
    return render_template("fund.html", fund=fund, rows=rows, from_cache=data.get("from_cache"))
