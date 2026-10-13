"""Catalog filter specification. Mirrors eShopOnWeb's CatalogFilterSpecification.

This is the single place that decides which items match a filter. The web and
infrastructure layers build on it. The price-range filter (the lab feature)
gets added HERE, following the existing brand/type pattern.

NOTE (the deliberate gotcha, mirroring eShopOnWeb's duplicated predicate):
the same predicate also lives in `filter_predicate_for_count` below, used for
the paginated count. A new filter must be added to BOTH or page counts drift.
"""
from typing import Optional


def item_matches(item, brand_id: Optional[int], type_id: Optional[int]) -> bool:
    """The filter predicate. brand_id/type_id of None means 'no filter'."""
    if brand_id is not None and item.brand_id != brand_id:
        return False
    if type_id is not None and item.type_id != type_id:
        return False
    return True


def filter_predicate_for_count(item, brand_id: Optional[int], type_id: Optional[int]) -> bool:
    """DUPLICATE of item_matches, used for the total count / pagination.

    Gotcha: this must stay in sync with item_matches. If you add a price
    filter to item_matches but not here, the item list is filtered but the
    page count is not - page numbers drift. (Same trap as eShopOnWeb's two
    CatalogFilter specifications.)
    """
    if brand_id is not None and item.brand_id != brand_id:
        return False
    if type_id is not None and item.type_id != type_id:
        return False
    return True
