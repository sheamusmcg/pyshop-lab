"""Flask application factory. Wires the layers together."""
import sys
if sys.version_info < (3, 10):
    sys.exit('PyShop needs Python 3.10 or newer. You are on '
             f'{sys.version_info.major}.{sys.version_info.minor}. '
             'See the README setup section (step 1).')

import os
from flask import Flask
from pyshop.infrastructure.models import (make_engine, make_session, seed,
                                          CatalogRepository, OrderRepository, ItemModel)
from pyshop.web.catalog import catalog_bp
from pyshop.web.orders import orders_bp
from pyshop.web.forecast import forecast_bp
from pyshop.services.cache import TTLCache


class TestClock:
    """Monotonic clock that tests can advance. Starts at 0."""
    def __init__(self): self.now = 0.0
    def __call__(self): return self.now
    def advance(self, seconds): self.now += seconds


def create_app(db_url=None, seed_data=None):
    """db_url defaults to PYSHOP_DB (env) or in-memory SQLite.

    seed_data defaults to True for in-memory, and for a file database only when
    it is empty - so a harness can reset and seed a file database itself.
    """
    db_url = db_url or os.environ.get("PYSHOP_DB") or "sqlite:///:memory:"
    app = Flask(__name__)
    engine = make_engine(db_url)
    session = make_session(engine)
    if seed_data is None:
        seed_data = session.query(ItemModel).count() == 0
    if seed_data:
        seed(session)
    app.config["REPO"] = CatalogRepository(session)
    app.config["ORDERS"] = OrderRepository(session)
    app.config["SESSION"] = session
    clock = TestClock()
    app.config["CLOCK"] = clock
    app.config["CACHE"] = TTLCache(ttl_seconds=int(os.environ.get("PYSHOP_CACHE_TTL", "300")), clock=clock)
    app.register_blueprint(catalog_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(forecast_bp)
    return app


if __name__ == "__main__":
    port = int(os.environ.get("PYSHOP_PORT", "5001"))
    create_app().run(port=port, debug=False)
