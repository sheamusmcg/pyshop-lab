"""Flask catalog blueprint. Mirrors eShopOnWeb's Web/Pages catalog.

Serves the storefront catalog page with brand and type filter dropdowns.
The price-range filter (the lab feature) gets wired in HERE, next to the
existing brand/type filters, plus the service/view-model layer below.
"""
from flask import Blueprint, render_template, request, current_app

catalog_bp = Blueprint("catalog", __name__)


def build_view_model(repo, brand_id, type_id, page):
    """View-model: shapes repository data for the template.

    Mirrors eShopOnWeb's CatalogIndexViewModel. The price filter's UI labels
    (Under $10 etc.) would live here; the domain stays generic (min/max).
    """
    items = repo.list_items(brand_id=brand_id, type_id=type_id, page=page)
    total = repo.count_items(brand_id=brand_id, type_id=type_id)
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": repo.PAGE_SIZE,
        "brand_id": brand_id,
        "type_id": type_id,
    }


@catalog_bp.route("/")
def index():
    repo = current_app.config["REPO"]
    brand_id = request.args.get("brand", type=int)
    type_id = request.args.get("type", type=int)
    page = request.args.get("page", default=1, type=int)
    vm = build_view_model(repo, brand_id, type_id, page)
    return render_template("catalog.html", **vm)
