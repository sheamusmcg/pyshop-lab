"""Flask application factory. Wires the layers together."""
import sys
if sys.version_info < (3, 10):
    sys.exit('PyShop needs Python 3.10 or newer. You are on '
             f'{sys.version_info.major}.{sys.version_info.minor}. '
             'See the README setup section (step 1).')

from flask import Flask
from pyshop.infrastructure.models import make_engine, make_session, seed, CatalogRepository
from pyshop.web.catalog import catalog_bp


def create_app(db_url="sqlite:///:memory:", seed_data=True):
    app = Flask(__name__)
    engine = make_engine(db_url)
    session = make_session(engine)
    if seed_data:
        seed(session)
    app.config["REPO"] = CatalogRepository(session)
    app.register_blueprint(catalog_bp)
    return app


if __name__ == "__main__":
    create_app().run(port=5001, debug=True)
