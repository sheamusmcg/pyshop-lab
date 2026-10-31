"""Run the forecast for all funds (or --fund ids) and store results.

    python -m pyshop.calc.run_forecast [--fund 1 --fund 2]
Prints: funds processed, rows written. Exit 0 on completion.
"""
import argparse, os
from pyshop.infrastructure.models import make_engine, make_session, seed, ItemModel
from pyshop.calc.forecast import run_all

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--fund", type=int, action="append")
    a = ap.parse_args(argv)
    s = make_session(make_engine(os.environ.get("PYSHOP_DB", "sqlite:///:memory:")))
    if s.query(ItemModel).count() == 0: seed(s)
    funds, rows = run_all(s, a.fund)
    print(f"run_forecast: funds={funds} rows={rows}")

if __name__ == "__main__":
    main()
