"""Domain entities. Mirrors eShopOnWeb's ApplicationCore/Entities.

Plain dataclasses - no framework, no database. The business shape of a
catalog item, independent of how it's stored or served.
"""
from dataclasses import dataclass


@dataclass
class CatalogBrand:
    id: int
    name: str


@dataclass
class CatalogType:
    id: int
    name: str


@dataclass
class CatalogItem:
    id: int
    name: str
    price: float
    brand_id: int
    type_id: int
    stock: int = 0


@dataclass
class OrderLine:
    item_id: int
    quantity: int
    unit_price: float


@dataclass
class Order:
    id: int
    lines: list
    total: float
