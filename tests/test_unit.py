"""Unit tests - the domain filter, no database. Mirrors eShopOnWeb UnitTests."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from pyshop.domain.entities import CatalogItem
from pyshop.domain.catalog_filter import item_matches

def _item(brand_id=1, type_id=1, price=10.0):
    return CatalogItem(id=1, name="x", price=price, brand_id=brand_id, type_id=type_id)

def test_no_filter_matches_everything():
    assert item_matches(_item(), None, None) is True

def test_brand_filter_matches():
    assert item_matches(_item(brand_id=1), brand_id=1, type_id=None) is True
    assert item_matches(_item(brand_id=2), brand_id=1, type_id=None) is False

def test_type_filter_matches():
    assert item_matches(_item(type_id=1), brand_id=None, type_id=1) is True
    assert item_matches(_item(type_id=2), brand_id=None, type_id=1) is False


# Price-range filter
def test_price_filter_matches_item_in_range():
    assert item_matches(_item(price=12.0), None, None, price_min=10.0, price_max=15.0) is True


def test_price_filter_excludes_item_below_range():
    assert item_matches(_item(price=8.5), None, None, price_min=10.0, price_max=15.0) is False


def test_price_filter_open_ended_top_band():
    assert item_matches(_item(price=25.0), None, None, price_min=20.0, price_max=None) is True
