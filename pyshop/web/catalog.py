"""Flask catalog blueprint. Mirrors eShopOnWeb's Web/Pages catalog.

Serves the storefront catalog page with brand and type filter dropdowns.
The price-range filter (the lab feature) gets wired in HERE, next to the
existing brand/type filters, plus the service/view-model layer below.
"""
from flask import Blueprint, render_template, request, current_app

catalog_bp = Blueprint("catalog", __name__)

# Preset price bands (docs/spec.md, Proposed design). Key -> (label, min, max).
# min is inclusive, max is exclusive (R5); None means open-ended.
PRICE_BANDS = {
    "under-10": ("Under $10", None, 10.0),
    "10-15": ("$10\u2013$15", 10.0, 15.0),
    "15-20": ("$15\u2013$20", 15.0, 20.0),
    "20-plus": ("$20 and over", 20.0, None),
}


def price_bounds(price_key):
    """Map a band key to (min, max). An unrecognized key means no price filter."""
    band = PRICE_BANDS.get(price_key)
    if band is None:
        return None, None
    return band[1], band[2]


def build_view_model(repo, brand_id, type_id, page, price_key=None):
    """View-model: shapes repository data for the template.

    Mirrors eShopOnWeb's CatalogIndexViewModel. The price filter's UI labels
    live here; the domain stays generic (min/max).
    """
    price_min, price_max = price_bounds(price_key)
    items = repo.list_items(brand_id=brand_id, type_id=type_id, page=page,
                            price_min=price_min, price_max=price_max)
    total = repo.count_items(brand_id=brand_id, type_id=type_id,
                             price_min=price_min, price_max=price_max)
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": repo.PAGE_SIZE,
        "brand_id": brand_id,
        "type_id": type_id,
        "price_key": price_key if price_key in PRICE_BANDS else None,
        "price_bands": [(key, band[0]) for key, band in PRICE_BANDS.items()],
    }


@catalog_bp.route("/")
def index():
    repo = current_app.config["REPO"]
    brand_id = request.args.get("brand", type=int)
    type_id = request.args.get("type", type=int)
    price_key = request.args.get("price")
    page = request.args.get("page", default=1, type=int)
    vm = build_view_model(repo, brand_id, type_id, page, price_key)
    return render_template("catalog.html", **vm)
