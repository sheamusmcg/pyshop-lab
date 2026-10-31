"""Order endpoints. Mirrors eShopOnWeb's basket checkout / OrderService.

POST /order   {"lines": [{"item_id": 1, "quantity": 2}]}
              -> 201 {"order_id", "total", "lines": [{"item_id","quantity","unit_price"}]}
GET  /order/<id>
              -> 200 same shape, or 404
Errors: 400 for a bad body, 404 unknown item, 409 insufficient stock.
"""
from flask import Blueprint, request, jsonify, current_app
from pyshop.infrastructure.models import OutOfStock

orders_bp = Blueprint("orders", __name__)


def _order_json(repo, order):
    lines = repo.order_lines(order.id)
    return {
        "order_id": order.id,
        "total": order.total,
        "lines": [{"item_id": l.item_id, "quantity": l.quantity, "unit_price": l.unit_price}
                  for l in lines],
    }


@orders_bp.post("/order")
def place_order():
    body = request.get_json(silent=True) or {}
    raw = body.get("lines")
    if not isinstance(raw, list) or not raw:
        return jsonify({"error": "lines required"}), 400
    try:
        lines = [(int(l["item_id"]), int(l["quantity"])) for l in raw]
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "each line needs item_id and quantity"}), 400
    if any(q <= 0 for _, q in lines):
        return jsonify({"error": "quantity must be positive"}), 400
    repo = current_app.config["ORDERS"]
    try:
        order = repo.place_order(lines)
    except KeyError as e:
        return jsonify({"error": f"unknown item {e.args[0]}"}), 404
    except OutOfStock as e:
        return jsonify({"error": f"insufficient stock for item {e.args[0]}"}), 409
    return jsonify(_order_json(repo, order)), 201


@orders_bp.get("/order/<int:order_id>")
def get_order(order_id):
    repo = current_app.config["ORDERS"]
    order = repo.get_order(order_id)
    if order is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(_order_json(repo, order))
