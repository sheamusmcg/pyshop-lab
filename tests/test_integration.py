"""Integration tests - real (in-memory SQLite) DB + repository.
Mirrors eShopOnWeb IntegrationTests (EF Core in-memory provider)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
from pyshop.infrastructure.models import make_engine, make_session, seed, CatalogRepository

@pytest.fixture
def repo():
    s = make_session(make_engine("sqlite:///:memory:"))
    seed(s)
    return CatalogRepository(s)

def test_lists_all_items(repo):
    assert len(repo.list_items()) == 10   # PAGE_SIZE; 30 seeded

def test_brand_filter_returns_only_that_brand(repo):
    items = repo.list_items(brand_id=1)
    assert all(i.brand_id == 1 for i in items) and len(items) == 8

def test_count_matches_filter(repo):
    assert repo.count_items(brand_id=1) == 8
    assert repo.count_items(type_id=1) == 12
    assert repo.count_items() == 30


# ---- orders ----
def test_place_order_records_order(repo):
    from pyshop.infrastructure.models import OrderRepository
    orders = OrderRepository(repo.session)
    order = orders.place_order([(1, 2)])          # Azure Mug, 8.50
    assert order.total == 17.0
    lines = orders.order_lines(order.id)
    assert [(l.item_id, l.quantity, l.unit_price) for l in lines] == [(1, 2, 8.5)]


def test_order_rejects_insufficient_stock(repo):
    import pytest
    from pyshop.infrastructure.models import OrderRepository, OutOfStock, ItemModel
    orders = OrderRepository(repo.session)
    with pytest.raises(OutOfStock):
        orders.place_order([(30, 4)])             # Python Tee Premium, stock 3
    assert repo.session.get(ItemModel, 30).stock == 3


def test_order_endpoint_round_trip():
    from pyshop.web.app import create_app
    c = create_app("sqlite:///:memory:", seed_data=True).test_client()
    r = c.post("/order", json={"lines": [{"item_id": 7, "quantity": 1}]})   # VS Mug 15.00
    assert r.status_code == 201
    body = r.get_json()
    assert body["total"] == 15.0 and body["lines"][0]["unit_price"] == 15.0
    assert c.get(f"/order/{body['order_id']}").get_json()["total"] == 15.0
    assert c.post("/order", json={"lines": []}).status_code == 400
