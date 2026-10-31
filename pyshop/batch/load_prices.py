"""Nightly price load. REPRESENTATIVE EXAMPLE of a batch process.

    python -m pyshop.batch.load_prices --file data/prices_2026-10-31.csv --as-of 2026-10-31 [--region apac]

Reads a CSV of (fund_code, price), validates each row against the pricing
service for that region, and writes fund_prices rows for the as-of date.
Rows whose CSV price differs from the service's reference price by more than
the tolerance are REJECTED and recorded in load_rejections.

Parameters select execution paths:
  --region (optional) limits the load to one region. Regions are priced by
  the regional pricing client (see _client_for_region).
  --tolerance (default 1.0) is the reconciliation threshold.

Exit code 0 on completion. Prints a one-line summary: loaded, rejected.
"""
import argparse, csv, os, sys
from datetime import date
from sqlalchemy import select
from pyshop.infrastructure.models import (make_engine, make_session, seed, FundModel,
                                          FundPriceModel, LoadRejectionModel, ItemModel)
from pyshop.services.pricing import PricingV2, PricingLegacy


def _client_for_region(session, region):
    """Regional pricing. All regions moved to PricingV2 in the 2025 migration,
    except that the APAC feed was left on the previous client pending vendor
    sign-off. (This is the incident: a rarely used parameter selects the
    deprecated service.)"""
    if region == "apac":
        return PricingLegacy(session)
    return PricingV2(session)


def run(session, csv_path, as_of, region=None, tolerance=1.0):
    funds = {f.code: f for f in session.scalars(select(FundModel)).all()}
    loaded = rejected = 0
    with open(csv_path, newline="") as fh:
        for row in csv.DictReader(fh):
            fund = funds.get(row["fund_code"])
            if fund is None:
                continue
            if region and fund.region != region:
                continue
            client = _client_for_region(session, fund.region)
            reference = client.price(fund.id, as_of)
            price = float(row["price"])
            if reference is not None and abs(price - reference) > tolerance:
                session.add(LoadRejectionModel(fund_id=fund.id, price_date=as_of, price=price,
                                               reference=reference, reason="outside tolerance"))
                rejected += 1
                continue
            session.add(FundPriceModel(fund_id=fund.id, price_date=as_of, price=price,
                                       source=f"load:{client.name}"))
            loaded += 1
    session.commit()
    return loaded, rejected


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--as-of", required=True)
    ap.add_argument("--region", default=None, choices=["amer", "emea", "apac"])
    ap.add_argument("--tolerance", type=float, default=1.0)
    args = ap.parse_args(argv)
    db = os.environ.get("PYSHOP_DB", "sqlite:///:memory:")
    session = make_session(make_engine(db))
    if session.query(ItemModel).count() == 0:
        seed(session)
    loaded, rejected = run(session, args.file, date.fromisoformat(args.as_of), args.region, args.tolerance)
    print(f"load_prices: as_of={args.as_of} region={args.region or 'all'} loaded={loaded} rejected={rejected}")


if __name__ == "__main__":
    main()
