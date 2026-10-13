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
    return create_engine(url)


def make_session(engine):
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def seed(session):
    """Seed data. Prices 8.50-19.50, mirroring eShopOnWeb's seed range."""
    brands = [BrandModel(id=1, name="Azure"), BrandModel(id=2, name="Visual Studio")]
    types = [TypeModel(id=1, name="Mug"), TypeModel(id=2, name="T-Shirt")]
    items = [
        ItemModel(id=1, name="Azure Mug", price=8.50, brand_id=1, type_id=1),
        ItemModel(id=2, name="Azure Tee", price=12.00, brand_id=1, type_id=2),
        ItemModel(id=3, name="VS Mug", price=15.00, brand_id=2, type_id=1),
        ItemModel(id=4, name="VS Tee", price=19.50, brand_id=2, type_id=2),
    ]
    session.add_all(brands + types + items)
    session.commit()
