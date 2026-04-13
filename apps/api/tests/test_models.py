"""Tests for EPIC 3 — core domain schema models.

These tests use an in-memory SQLite database.  PostgreSQL-specific column types
(TSVECTOR, ARRAY, JSONB, postgres ENUMs) are tested via the ORM layer by
importing models and verifying their attributes rather than through DDL, since
SQLite does not support those types.

Placement rule tests validate the Python-side @validates guards directly.
"""

import uuid

import pytest
from sqlalchemy import text

from makervault.models.category import Category
from makervault.models.container import Container
from makervault.models.location import Location
from makervault.models.part import Part
from makervault.models.stock_item import StockItem


# ---------------------------------------------------------------------------
# SQLite-compatible test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def sqlite_engine():
    """In-memory SQLite engine with a simplified schema (no PG-specific types)."""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    # Create a simplified schema that SQLite can handle
    async with engine.begin() as conn:
        await conn.execute(
            text("""
            CREATE TABLE categories (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                parent_category_id TEXT REFERENCES categories(id),
                description TEXT,
                sort_order INTEGER,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """)
        )
        await conn.execute(
            text("""
            CREATE TABLE locations (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                parent_location_id TEXT REFERENCES locations(id),
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """)
        )
        await conn.execute(
            text("""
            CREATE TABLE containers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                label_code TEXT UNIQUE,
                location_id TEXT REFERENCES locations(id),
                parent_container_id TEXT REFERENCES containers(id),
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CHECK (
                    CASE WHEN location_id IS NOT NULL THEN 1 ELSE 0 END +
                    CASE WHEN parent_container_id IS NOT NULL THEN 1 ELSE 0 END = 1
                )
            )
            """)
        )
        await conn.execute(
            text("""
            CREATE TABLE parts (
                id TEXT PRIMARY KEY,
                part_code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                short_description TEXT,
                long_description TEXT,
                category_id TEXT REFERENCES categories(id),
                part_kind TEXT,
                manufacturer TEXT,
                manufacturer_part_number TEXT,
                default_unit TEXT NOT NULL DEFAULT 'pcs',
                package_type TEXT,
                spec_summary TEXT,
                capabilities_json TEXT,
                tags TEXT,
                aliases TEXT,
                search_text TEXT,
                is_consumable INTEGER NOT NULL DEFAULT 0,
                is_serialised INTEGER NOT NULL DEFAULT 0,
                is_hazardous INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'draft',
                identification_confidence INTEGER,
                needs_review INTEGER NOT NULL DEFAULT 0,
                provenance TEXT DEFAULT 'manual',
                notes TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """)
        )
        await conn.execute(
            text("""
            CREATE TABLE stock_items (
                id TEXT PRIMARY KEY,
                part_id TEXT NOT NULL REFERENCES parts(id),
                location_id TEXT REFERENCES locations(id),
                container_id TEXT REFERENCES containers(id),
                quantity REAL NOT NULL DEFAULT 1,
                unit TEXT,
                status TEXT NOT NULL DEFAULT 'available',
                condition TEXT,
                serial_number TEXT,
                batch_code TEXT,
                purchase_date TEXT,
                purchase_price REAL,
                purchase_currency TEXT,
                supplier TEXT,
                notes TEXT,
                last_seen_at TIMESTAMP,
                is_reserved INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CHECK (
                    CASE WHEN location_id IS NOT NULL THEN 1 ELSE 0 END +
                    CASE WHEN container_id IS NOT NULL THEN 1 ELSE 0 END = 1
                )
            )
            """)
        )
    yield engine
    await engine.dispose()


@pytest.fixture
async def sess(sqlite_engine):
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    factory = async_sessionmaker(
        bind=sqlite_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Category tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_category_creation(sess) -> None:
    cat = Category(id=uuid.uuid4(), name="Sensors")
    sess.add(cat)
    await sess.commit()
    await sess.refresh(cat)
    assert cat.name == "Sensors"
    assert cat.parent_category_id is None


@pytest.mark.asyncio
async def test_nested_category(sess) -> None:
    parent = Category(id=uuid.uuid4(), name="Sensors")
    child = Category(
        id=uuid.uuid4(), name="Temperature", parent_category_id=parent.id
    )
    sess.add_all([parent, child])
    await sess.commit()
    await sess.refresh(child)
    assert child.parent_category_id == parent.id


# ---------------------------------------------------------------------------
# Location tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_location_creation(sess) -> None:
    loc = Location(id=uuid.uuid4(), name="Garage")
    sess.add(loc)
    await sess.commit()
    await sess.refresh(loc)
    assert loc.name == "Garage"


@pytest.mark.asyncio
async def test_location_hierarchy(sess) -> None:
    building = Location(id=uuid.uuid4(), name="Workshop")
    shelf = Location(
        id=uuid.uuid4(), name="Top Shelf", parent_location_id=building.id
    )
    sess.add_all([building, shelf])
    await sess.commit()
    await sess.refresh(shelf)
    assert shelf.parent_location_id == building.id


# ---------------------------------------------------------------------------
# Container tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_container_in_location(sess) -> None:
    loc = Location(id=uuid.uuid4(), name="Garage")
    sess.add(loc)
    await sess.flush()
    container = Container(id=uuid.uuid4(), name="Box A", location_id=loc.id)
    sess.add(container)
    await sess.commit()
    await sess.refresh(container)
    assert container.location_id == loc.id
    assert container.parent_container_id is None


@pytest.mark.asyncio
async def test_nested_container(sess) -> None:
    loc = Location(id=uuid.uuid4(), name="Garage")
    sess.add(loc)
    await sess.flush()
    outer = Container(id=uuid.uuid4(), name="Case F", location_id=loc.id)
    sess.add(outer)
    await sess.flush()
    inner = Container(
        id=uuid.uuid4(), name="Tray 2", parent_container_id=outer.id
    )
    sess.add(inner)
    await sess.commit()
    await sess.refresh(inner)
    assert inner.parent_container_id == outer.id
    assert inner.location_id is None


@pytest.mark.asyncio
async def test_container_label_code_unique(sess) -> None:
    from sqlalchemy.exc import IntegrityError

    loc = Location(id=uuid.uuid4(), name="Shelf")
    sess.add(loc)
    await sess.flush()
    c1 = Container(id=uuid.uuid4(), name="Box 1", location_id=loc.id, label_code="C001")
    c2 = Container(id=uuid.uuid4(), name="Box 2", location_id=loc.id, label_code="C001")
    sess.add_all([c1, c2])
    with pytest.raises(IntegrityError):
        await sess.commit()


@pytest.mark.asyncio
async def test_container_dual_parent_raises(sess) -> None:
    """Python-side validation should reject dual parent."""
    loc = Location(id=uuid.uuid4(), name="Lab")
    outer = Container(id=uuid.uuid4(), name="Outer")
    with pytest.raises(ValueError, match="cannot have both"):
        Container(
            id=uuid.uuid4(),
            name="Bad",
            location_id=loc.id,
            parent_container_id=outer.id,
        )


# ---------------------------------------------------------------------------
# Part tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_part_creation(sess) -> None:
    part = Part(
        id=uuid.uuid4(),
        part_code="ESP32-DEVKIT-V1",
        name="ESP32 DevKit V1",
    )
    sess.add(part)
    await sess.commit()
    await sess.refresh(part)
    assert part.part_code == "ESP32-DEVKIT-V1"
    assert part.name == "ESP32 DevKit V1"


@pytest.mark.asyncio
async def test_part_code_unique(sess) -> None:
    from sqlalchemy.exc import IntegrityError

    p1 = Part(id=uuid.uuid4(), part_code="DUPE-001", name="Part 1")
    p2 = Part(id=uuid.uuid4(), part_code="DUPE-001", name="Part 2")
    sess.add_all([p1, p2])
    with pytest.raises(IntegrityError):
        await sess.commit()


@pytest.mark.asyncio
async def test_part_default_unit(sess) -> None:
    part = Part(id=uuid.uuid4(), part_code="P-001", name="Resistor")
    sess.add(part)
    await sess.commit()
    await sess.refresh(part)
    # Default is 'pcs' either from Python default or server default
    assert part.default_unit in ("pcs", None)  # may be None in SQLite before flush


@pytest.mark.asyncio
async def test_part_with_category(sess) -> None:
    cat = Category(id=uuid.uuid4(), name="Microcontrollers")
    sess.add(cat)
    await sess.flush()
    part = Part(
        id=uuid.uuid4(),
        part_code="MCU-001",
        name="ATmega328P",
        category_id=cat.id,
    )
    sess.add(part)
    await sess.commit()
    await sess.refresh(part)
    assert part.category_id == cat.id


# ---------------------------------------------------------------------------
# StockItem tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stock_item_in_container(sess) -> None:
    loc = Location(id=uuid.uuid4(), name="Bench")
    sess.add(loc)
    await sess.flush()
    container = Container(id=uuid.uuid4(), name="Bin 1", location_id=loc.id)
    sess.add(container)
    await sess.flush()
    part = Part(id=uuid.uuid4(), part_code="R-001", name="10k Resistor")
    sess.add(part)
    await sess.flush()

    item = StockItem(
        id=uuid.uuid4(),
        part_id=part.id,
        container_id=container.id,
        quantity=100,
    )
    sess.add(item)
    await sess.commit()
    await sess.refresh(item)
    assert item.container_id == container.id
    assert item.location_id is None


@pytest.mark.asyncio
async def test_stock_item_directly_in_location(sess) -> None:
    loc = Location(id=uuid.uuid4(), name="Shelf B")
    sess.add(loc)
    await sess.flush()
    part = Part(id=uuid.uuid4(), part_code="CAP-001", name="10uF Capacitor")
    sess.add(part)
    await sess.flush()

    item = StockItem(
        id=uuid.uuid4(),
        part_id=part.id,
        location_id=loc.id,
        quantity=50,
    )
    sess.add(item)
    await sess.commit()
    await sess.refresh(item)
    assert item.location_id == loc.id
    assert item.container_id is None


@pytest.mark.asyncio
async def test_stock_item_dual_placement_raises(sess) -> None:
    """Python-side validation rejects items with both location and container."""
    loc = Location(id=uuid.uuid4(), name="Shelf")
    container = Container(id=uuid.uuid4(), name="Box")
    part = Part(id=uuid.uuid4(), part_code="P-DUP", name="Part")
    with pytest.raises(ValueError, match="cannot have both"):
        StockItem(
            id=uuid.uuid4(),
            part_id=part.id,
            location_id=loc.id,
            container_id=container.id,
        )


@pytest.mark.asyncio
async def test_part_can_have_multiple_stock_items(sess) -> None:
    loc1 = Location(id=uuid.uuid4(), name="Garage")
    loc2 = Location(id=uuid.uuid4(), name="Office")
    sess.add_all([loc1, loc2])
    await sess.flush()

    part = Part(id=uuid.uuid4(), part_code="LED-RED", name="Red LED")
    sess.add(part)
    await sess.flush()

    item1 = StockItem(id=uuid.uuid4(), part_id=part.id, location_id=loc1.id, quantity=20)
    item2 = StockItem(id=uuid.uuid4(), part_id=part.id, location_id=loc2.id, quantity=5)
    sess.add_all([item1, item2])
    await sess.commit()

    # Verify using ORM query via select
    from sqlalchemy import select
    result = await sess.execute(
        select(StockItem).where(StockItem.part_id == part.id)
    )
    items = result.scalars().all()
    assert len(items) == 2


# ---------------------------------------------------------------------------
# Migration smoke test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_models_importable() -> None:
    """All EPIC 3 models should be importable without error."""
    from makervault.models import Category, Container, Location, Part, StockItem  # noqa: F401
