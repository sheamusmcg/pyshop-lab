"""Fixture helper for regression scenarios. Changes controlled state in the
scenario database (PYSHOP_DB). Test tooling, not an application feature.

    python -m pyshop.batch.fixture set-price --fund 1 --date 2026-10-30 --price 103.00
    python -m pyshop.batch.fixture set-setting --key pricing-v2.unavailable --value 1
"""
import argparse, os
from datetime import date
from sqlalchemy import select
from pyshop.infrastructure.models import make_engine, make_session, FundPriceModel, SettingModel

def main(argv=None):
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("set-price"); sp.add_argument("--fund", type=int, required=True); sp.add_argument("--date", required=True); sp.add_argument("--price", type=float, required=True)
    ss = sub.add_parser("set-setting"); ss.add_argument("--key", required=True); ss.add_argument("--value", required=True)
    a = ap.parse_args(argv)
    s = make_session(make_engine(os.environ["PYSHOP_DB"]))
    if a.cmd == "set-price":
        row = s.scalar(select(FundPriceModel).where(FundPriceModel.fund_id == a.fund, FundPriceModel.price_date == date.fromisoformat(a.date)))
        if row is None:
            row = FundPriceModel(fund_id=a.fund, price_date=date.fromisoformat(a.date), price=a.price, source="fixture"); s.add(row)
        else:
            row.price = a.price; row.source = "fixture"
        s.commit(); print(f"fixture: fund {a.fund} price on {a.date} = {a.price}")
    else:
        row = s.get(SettingModel, a.key)
        if row is None: s.add(SettingModel(key=a.key, value=a.value))
        else: row.value = a.value
        s.commit(); print(f"fixture: {a.key} = {a.value}")

if __name__ == "__main__":
    main()
