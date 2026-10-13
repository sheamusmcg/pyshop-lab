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
    assert len(repo.list_items()) == 4

def test_brand_filter_returns_only_that_brand(repo):
    items = repo.list_items(brand_id=1)
    assert {i.name for i in items} == {"Azure Mug", "Azure Tee"}

def test_count_matches_filter(repo):
    assert repo.count_items(brand_id=1) == 2
    assert repo.count_items(type_id=1) == 2
    assert repo.count_items() == 4
