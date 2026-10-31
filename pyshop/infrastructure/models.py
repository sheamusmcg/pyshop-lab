"""SQLAlchemy ORM models + repository. Mirrors eShopOnWeb's Infrastructure.

Maps the domain entities to database tables, and provides the repository the
web layer calls. The DB provider is swappable - integration tests use SQLite
in-memory (mirrors eShopOnWeb's EF Core in-memory provider).
"""
from sqlalchemy import create_engine, Integer, String, Float, ForeignKey
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class BrandModel(Base):
    __tablename__ = "brands"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))


class TypeModel(Base):
    __tablename__ = "types"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))


class ItemModel(Base):
    __tablename__ = "items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    price: Mapped[float] = mapped_column(Float)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"))
    type_id: Mapped[int] = mapped_column(ForeignKey("types.id"))
    stock: Mapped[int] = mapped_column(Integer, default=0)


class OrderModel(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    total: Mapped[float] = mapped_column(Float)


class OrderLineModel(Base):
    __tablename__ = "order_lines"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[float] = mapped_column(Float)


class OutOfStock(Exception):
    pass


class OrderRepository:
    """Places orders. Mirrors eShopOnWeb's OrderService + repository.

    place_order records the order and its lines at the item's current price,
    and reduces each item's stock by the quantity ordered. The response total
    and the stored total come from the same calculation.
    """

    def __init__(self, session):
        self.session = session

    def place_order(self, lines):
        """lines: list of (item_id, quantity). Returns the stored OrderModel."""
        from sqlalchemy import select
        items = {}
        for item_id, qty in lines:
            item = self.session.get(ItemModel, item_id)
            if item is None:
                raise KeyError(item_id)
            if item.stock < qty:
                raise OutOfStock(item_id)
            items[item_id] = item
        order = OrderModel(total=0.0)
        self.session.add(order)
        self.session.flush()
        total = 0.0
        for item_id, qty in lines:
            item = items[item_id]
            self.session.add(OrderLineModel(order_id=order.id, item_id=item_id,
                                            quantity=qty, unit_price=item.price))
            item.stock -= qty
            total += item.price * qty
        order.total = round(total, 2)
        self.session.commit()
        return order

    def get_order(self, order_id):
        return self.session.get(OrderModel, order_id)

    def order_lines(self, order_id):
        from sqlalchemy import select
        return self.session.scalars(
            select(OrderLineModel).where(OrderLineModel.order_id == order_id)).all()


class CatalogRepository:
    """Reads catalog items with filtering and pagination.

    Filtering goes through the domain predicates in domain/catalog_filter.py:
    the list uses item_matches, the count uses filter_predicate_for_count.
    Those two predicates are duplicates and must stay in sync - add a new
    filter to one but not the other and the list and the page count drift
    (see domain/catalog_filter.py for the gotcha).
    """
    PAGE_SIZE = 10  # list paging only; count must apply the SAME filters as the list

    def __init__(self, session):
        self.session = session

    def list_items(self, brand_id=None, type_id=None, page=1):
        from sqlalchemy import select
        from pyshop.domain.catalog_filter import item_matches
        rows = self.session.scalars(select(ItemModel)).all()
        matched = [it for it in rows if item_matches(it, brand_id, type_id)]
        start = (page - 1) * self.PAGE_SIZE
        return matched[start:start + self.PAGE_SIZE]

    def count_items(self, brand_id=None, type_id=None):
        from sqlalchemy import select
        from pyshop.domain.catalog_filter import filter_predicate_for_count
        rows = self.session.scalars(select(ItemModel)).all()
        return sum(1 for it in rows if filter_predicate_for_count(it, brand_id, type_id))


def make_engine(url="sqlite:///:memory:"):
    # In-memory SQLite gives each connection its own empty database by default.
    # StaticPool keeps one shared connection so the seeded tables are visible to
    # every request (including the threaded dev server); check_same_thread lets
    # that one connection be used across Flask's worker threads.
    if url == "sqlite:///:memory:":
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    if url.startswith("sqlite:///"):
        # File-backed SQLite (used by the regression harness, which resets and
        # inspects the database between runs). Allow use across Flask threads.
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url)


def make_session(engine):
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def seed(session):
    """Seed data: 4 brands, 3 types, 30 items with stock. Prices 6.50-29.00."""
    brands = [BrandModel(id=1, name="Azure"), BrandModel(id=2, name="Visual Studio"),
              BrandModel(id=3, name=".NET"), BrandModel(id=4, name="Python")]
    types = [TypeModel(id=1, name="Mug"), TypeModel(id=2, name="T-Shirt"), TypeModel(id=3, name="Sticker")]
    # (name, price, brand_id, type_id, stock) - deterministic, no randomness.
    rows = [
        ("Azure Mug", 8.50, 1, 1, 10), ("Azure Tee", 12.00, 1, 2, 25), ("Azure Sticker", 6.50, 1, 3, 100),
        ("Azure Mug XL", 15.00, 1, 1, 8), ("Azure Hoodie Tee", 24.00, 1, 2, 5), ("Azure Pin Sticker", 7.00, 1, 3, 60),
        ("VS Mug", 15.00, 2, 1, 12), ("VS Tee", 19.50, 2, 2, 20), ("VS Sticker", 6.75, 2, 3, 80),
        ("VS Mug Black", 16.25, 2, 1, 9), ("VS Tee Long Sleeve", 22.00, 2, 2, 7), ("VS Code Sticker", 8.00, 2, 3, 70),
        (".NET Mug", 10.00, 3, 1, 15), (".NET Tee", 18.00, 3, 2, 18), (".NET Sticker", 6.50, 3, 3, 90),
        (".NET Mug Purple", 14.99, 3, 1, 11), (".NET Tee Vintage", 20.00, 3, 2, 6), (".NET Bot Sticker", 7.25, 3, 3, 55),
        ("Python Mug", 9.75, 4, 1, 14), ("Python Tee", 17.50, 4, 2, 22), ("Python Sticker", 6.99, 4, 3, 120),
        ("Python Mug Blue", 13.00, 4, 1, 10), ("Python Tee Dark", 21.00, 4, 2, 9), ("Python Logo Sticker", 7.50, 4, 3, 65),
        ("Azure Mug Mini", 9.99, 1, 1, 30), ("VS Mug Mini", 10.50, 2, 1, 28), (".NET Mug Mini", 9.00, 3, 1, 26),
        ("Python Mug Mini", 10.25, 4, 1, 24), ("Azure Tee Kids", 11.00, 1, 2, 16), ("Python Tee Premium", 29.00, 4, 2, 3),
    ]
    items = [ItemModel(id=i, name=n, price=pr, brand_id=b, type_id=t, stock=st)
             for i, (n, pr, b, t, st) in enumerate(rows, start=1)]
    session.add_all(brands + types + items)
    session.commit()
