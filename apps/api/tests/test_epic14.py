"""Tests for Epic 14 — Assisted part intake, matching, and code generation.

Covers:
- normalise_description:       basic tokenisation
- normalise_description:       package extraction
- normalise_description:       value extraction
- normalise_description:       kind-prefix inference
- score_candidate:             exact match scores high
- score_candidate:             unrelated part scores low (false-positive guard)
- suggest_part_code:           generates expected prefix
- suggest_part_code:           increments sequence on collision
- suggest_part_code:           empty DB → first code
- find_candidates:             returns ranked matches
- find_candidates:             unrelated parts not in top results
- suggest_storage:             returns storage from historical patterns
- suggest_storage:             returns empty list with no stock
- POST /api/intake/match:      full workflow returns candidates + code + storage
- POST /api/intake/match:      empty description → 422
- POST /api/intake/suggest-code: returns unique code
- POST /api/intake/suggest-code: second call with same prefix gets next seq
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from makervault.database import get_db_session
from makervault.main import app
from makervault.services.intake_service import (
    NormalisedDescription,
    find_candidates,
    normalise_description,
    score_candidate,
    suggest_part_code,
    suggest_storage,
)

# ---------------------------------------------------------------------------
# SQLite in-memory fixtures
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def e14_engine():
    engine = create_async_engine(SQLITE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE categories (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                parent_category_id TEXT,
                description TEXT,
                sort_order INTEGER,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        await conn.execute(text("""
            CREATE TABLE locations (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                parent_location_id TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        await conn.execute(text("""
            CREATE TABLE containers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                label_code TEXT UNIQUE,
                location_id TEXT,
                parent_container_id TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        await conn.execute(text("""
            CREATE TABLE parts (
                id TEXT PRIMARY KEY,
                part_code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                short_description TEXT,
                long_description TEXT,
                category_id TEXT,
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
                category TEXT,
                subcategory TEXT,
                family TEXT,
                form_factor TEXT,
                interface TEXT,
                voltage TEXT,
                logic_level TEXT,
                pins TEXT,
                capabilities TEXT,
                use_cases TEXT,
                key_specs TEXT,
                protection_features TEXT,
                special_flags TEXT,
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
        """))
        await conn.execute(text("""
            CREATE TABLE stock_items (
                id TEXT PRIMARY KEY,
                part_id TEXT NOT NULL,
                location_id TEXT,
                container_id TEXT,
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
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
    yield engine
    await engine.dispose()


@pytest.fixture
async def e14_session(e14_engine) -> AsyncSession:
    factory = async_sessionmaker(
        bind=e14_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with factory() as session:
        yield session


@pytest.fixture
async def e14_client(e14_session: AsyncSession) -> AsyncClient:
    async def _override_db():
        try:
            yield e14_session
            await e14_session.commit()
        except Exception:
            await e14_session.rollback()
            raise

    app.dependency_overrides[get_db_session] = _override_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    app.dependency_overrides.pop(get_db_session, None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _insert_part(
    session: AsyncSession,
    *,
    part_id: str | None = None,
    part_code: str,
    name: str,
    short_description: str | None = None,
    manufacturer_part_number: str | None = None,
    aliases: str | None = None,
) -> str:
    pid = part_id or str(uuid.uuid4())
    await session.execute(
        text(
            "INSERT INTO parts (id, part_code, name, short_description, "
            "manufacturer_part_number, aliases, is_active) "
            "VALUES (:id, :pc, :name, :sd, :mpn, :aliases, 1)"
        ),
        {
            "id": pid,
            "pc": part_code,
            "name": name,
            "sd": short_description,
            "mpn": manufacturer_part_number,
            "aliases": aliases,
        },
    )
    await session.commit()
    return pid


async def _insert_location(session: AsyncSession, name: str) -> str:
    loc_id = str(uuid.uuid4())
    await session.execute(
        text("INSERT INTO locations (id, name) VALUES (:id, :name)"),
        {"id": loc_id, "name": name},
    )
    await session.commit()
    return loc_id


async def _insert_stock(
    session: AsyncSession,
    part_id: str,
    location_id: str,
    qty: float = 5,
) -> str:
    si_id = str(uuid.uuid4())
    await session.execute(
        text(
            "INSERT INTO stock_items (id, part_id, location_id, quantity, status) "
            "VALUES (:id, :pid, :lid, :qty, 'available')"
        ),
        {"id": si_id, "pid": part_id, "lid": location_id, "qty": qty},
    )
    await session.commit()
    return si_id


# ===========================================================================
# normalise_description
# ===========================================================================


def test_normalise_basic_tokens():
    nd = normalise_description("10k Resistor 0603")
    assert "resistor" in nd.tokens or "10k" in nd.tokens


def test_normalise_package_extraction():
    nd = normalise_description("100nF capacitor 0805")
    assert nd.package_hint == "0805"


def test_normalise_value_extraction():
    nd = normalise_description("10k ohm resistor")
    # value hint should capture "10k"
    assert any("10" in v for v in nd.value_hints) or "10k" in nd.tokens


def test_normalise_kind_prefix_resistor():
    nd = normalise_description("resistor 10k 0603")
    assert nd.kind_prefix == "PAS-RES"


def test_normalise_kind_prefix_capacitor():
    nd = normalise_description("capacitor 100nF")
    assert nd.kind_prefix == "PAS-CAP"


def test_normalise_kind_prefix_mcu():
    nd = normalise_description("ESP32 dev board")
    assert nd.kind_prefix == "MCU-DEV"
    assert nd.family == "ESP32"


def test_normalise_kind_prefix_sensor():
    nd = normalise_description("MPU-6050 IMU gyroscope breakout")
    assert nd.kind_prefix == "SEN-IMU"
    assert nd.family == "MPU6050"


def test_normalise_kind_prefix_usb_breakout():
    nd = normalise_description("Micro USB breakout board")
    assert nd.kind_prefix == "CON-USB"
    assert nd.family == "USBMICRO"


def test_normalise_no_mcu_for_generic_breakout():
    """A plain breakout board without MCU family should not become MCU."""
    nd = normalise_description("breakout board adapter")
    assert nd.kind_prefix != "MCU-DEV"


def test_normalise_stop_words_removed():
    nd = normalise_description("a the resistor for the PCB")
    assert "the" not in nd.tokens
    assert "a" not in nd.tokens
    assert "for" not in nd.tokens


# ===========================================================================
# score_candidate
# ===========================================================================


def test_score_exact_name_match():
    nd = normalise_description("10k resistor 0603")
    score = score_candidate(
        part_name="10k Resistor 0603",
        part_aliases=None,
        part_mpn=None,
        part_short_desc=None,
        normed=nd,
    )
    assert score >= 40, f"Expected high score, got {score}"


def test_score_unrelated_part_low():
    """False-positive guard: completely unrelated part should score < minimum."""
    nd = normalise_description("10k resistor 0603")
    score = score_candidate(
        part_name="HDMI Cable 2m",
        part_aliases=None,
        part_mpn=None,
        part_short_desc=None,
        normed=nd,
    )
    assert score < 20, f"Expected low score for unrelated part, got {score}"


def test_score_mpn_match_bonus():
    nd = normalise_description("DHT22 temperature sensor")
    score_with_mpn = score_candidate(
        part_name="Temperature Sensor",
        part_aliases=None,
        part_mpn="DHT22",
        part_short_desc=None,
        normed=nd,
    )
    score_without_mpn = score_candidate(
        part_name="Temperature Sensor",
        part_aliases=None,
        part_mpn=None,
        part_short_desc=None,
        normed=nd,
    )
    assert score_with_mpn > score_without_mpn


def test_score_alias_match_bonus():
    nd = normalise_description("ESP32 microcontroller")
    score_with_alias = score_candidate(
        part_name="Development Board",
        part_aliases=["ESP32", "ESP32-DevKit"],
        part_mpn=None,
        part_short_desc=None,
        normed=nd,
    )
    score_no_alias = score_candidate(
        part_name="Development Board",
        part_aliases=None,
        part_mpn=None,
        part_short_desc=None,
        normed=nd,
    )
    assert score_with_alias > score_no_alias


# ===========================================================================
# suggest_part_code
# ===========================================================================


@pytest.mark.anyio
async def test_suggest_code_empty_db(e14_session):
    code = await suggest_part_code("10k resistor 0603", e14_session)
    assert "RES" in code
    assert code.endswith("-001")


@pytest.mark.anyio
async def test_suggest_code_increments_on_collision(e14_session):
    # First call
    code1 = await suggest_part_code("10k resistor 0603", e14_session)
    # Insert the generated code so it's now "taken"
    await _insert_part(e14_session, part_code=code1, name="Existing Resistor")
    # Second call must generate a different code
    code2 = await suggest_part_code("10k resistor 0603", e14_session)
    assert code2 != code1
    assert code2.endswith("-002")


@pytest.mark.anyio
async def test_suggest_code_mcu_prefix(e14_session):
    code = await suggest_part_code("ESP32 microcontroller dev board", e14_session)
    assert "MCU" in code


@pytest.mark.anyio
async def test_suggest_code_unique_across_calls(e14_session):
    code1 = await suggest_part_code("capacitor 100nF 0402", e14_session)
    await _insert_part(e14_session, part_code=code1, name="Cap 1")
    code2 = await suggest_part_code("capacitor 100nF 0402", e14_session)
    await _insert_part(e14_session, part_code=code2, name="Cap 2")
    code3 = await suggest_part_code("capacitor 100nF 0402", e14_session)
    assert len({code1, code2, code3}) == 3


# ===========================================================================
# find_candidates
# ===========================================================================


@pytest.mark.anyio
async def test_find_candidates_returns_match(e14_session):
    await _insert_part(
        e14_session,
        part_code="RES-001",
        name="10k Resistor",
        short_description="SMD resistor 10kΩ",
    )
    candidates = await find_candidates("10k resistor", e14_session, limit=5)
    assert any(c["name"] == "10k Resistor" for c in candidates)


@pytest.mark.anyio
async def test_find_candidates_confidence_ordering(e14_session):
    await _insert_part(e14_session, part_code="RES-001", name="10k Resistor 0603")
    await _insert_part(e14_session, part_code="CAP-001", name="100nF Capacitor 0402")
    candidates = await find_candidates("10k resistor 0603", e14_session, limit=5)
    if len(candidates) >= 2:
        assert candidates[0]["confidence"] >= candidates[1]["confidence"]


@pytest.mark.anyio
async def test_find_candidates_false_positive_guard(e14_session):
    """Unrelated part should not appear in top candidates."""
    await _insert_part(e14_session, part_code="CABLE-001", name="HDMI Cable 2m")
    candidates = await find_candidates("10k resistor 0603", e14_session, limit=5)
    # HDMI Cable should not be in results (or if it is, score should be low)
    hdmi = next((c for c in candidates if "HDMI" in c["name"]), None)
    assert hdmi is None or hdmi["confidence"] < 20


@pytest.mark.anyio
async def test_find_candidates_mpn_match(e14_session):
    await _insert_part(
        e14_session,
        part_code="SENSOR-001",
        name="Temperature and Humidity Sensor",
        manufacturer_part_number="DHT22",
    )
    candidates = await find_candidates("DHT22 sensor", e14_session, limit=5)
    assert any(c["manufacturer_part_number"] == "DHT22" for c in candidates)


# ===========================================================================
# suggest_storage
# ===========================================================================


@pytest.mark.anyio
async def test_suggest_storage_empty_returns_empty(e14_session):
    suggestions = await suggest_storage("10k resistor", e14_session)
    assert suggestions == []


@pytest.mark.anyio
async def test_suggest_storage_returns_historical_location(e14_session):
    loc_id = await _insert_location(e14_session, "Resistor Drawer")
    pid = await _insert_part(e14_session, part_code="RES-HIST", name="Resistor 10k")
    await _insert_stock(e14_session, pid, loc_id)

    suggestions = await suggest_storage("resistor 10k", e14_session)
    assert any(s["name"] == "Resistor Drawer" for s in suggestions)


@pytest.mark.anyio
async def test_suggest_storage_score_positive(e14_session):
    loc_id = await _insert_location(e14_session, "Cap Box")
    pid = await _insert_part(e14_session, part_code="CAP-HIST", name="Capacitor 100nF")
    await _insert_stock(e14_session, pid, loc_id)

    suggestions = await suggest_storage("capacitor 100nF", e14_session)
    for s in suggestions:
        assert 0 <= s["score"] <= 100


# ===========================================================================
# API endpoints — POST /api/intake/match
# ===========================================================================


@pytest.mark.anyio
async def test_intake_match_returns_structure(e14_client):
    resp = await e14_client.post(
        "/api/intake/match", json={"description": "10k resistor 0603"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "candidates" in data
    assert "suggested_part_code" in data
    assert "storage_suggestions" in data
    assert "normalised_tokens" in data
    assert isinstance(data["candidates"], list)
    assert isinstance(data["suggested_part_code"], str)
    assert len(data["suggested_part_code"]) > 0


@pytest.mark.anyio
async def test_intake_match_finds_existing_part(e14_client, e14_session):
    await _insert_part(e14_session, part_code="RES-MATCH-001", name="10k Resistor 0603")
    resp = await e14_client.post(
        "/api/intake/match", json={"description": "10k resistor 0603"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert any(c["part_code"] == "RES-MATCH-001" for c in data["candidates"])


@pytest.mark.anyio
async def test_intake_match_code_has_res_prefix(e14_client):
    resp = await e14_client.post(
        "/api/intake/match", json={"description": "resistor 4.7k 0402"}
    )
    assert resp.status_code == 200
    assert "RES" in resp.json()["suggested_part_code"]


@pytest.mark.anyio
async def test_intake_match_empty_description_rejected(e14_client):
    resp = await e14_client.post("/api/intake/match", json={"description": ""})
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_intake_match_with_storage_suggestion(e14_client, e14_session):
    loc_id = await _insert_location(e14_session, "Resistor Box")
    pid = await _insert_part(e14_session, part_code="RES-STOR", name="Resistor 10k")
    await _insert_stock(e14_session, pid, loc_id)

    resp = await e14_client.post(
        "/api/intake/match", json={"description": "resistor 10k"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert any(s["name"] == "Resistor Box" for s in data["storage_suggestions"])


# ===========================================================================
# API endpoints — POST /api/intake/suggest-code
# ===========================================================================


@pytest.mark.anyio
async def test_intake_suggest_code_basic(e14_client):
    resp = await e14_client.post(
        "/api/intake/suggest-code", json={"description": "LED red 5mm"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "suggested_part_code" in data
    assert "LED" in data["suggested_part_code"]


@pytest.mark.anyio
async def test_intake_suggest_code_unique(e14_client, e14_session):
    resp1 = await e14_client.post(
        "/api/intake/suggest-code", json={"description": "capacitor 10uF 0805"}
    )
    code1 = resp1.json()["suggested_part_code"]
    # Reserve the code
    await _insert_part(e14_session, part_code=code1, name="Cap existing")
    resp2 = await e14_client.post(
        "/api/intake/suggest-code", json={"description": "capacitor 10uF 0805"}
    )
    code2 = resp2.json()["suggested_part_code"]
    assert code1 != code2


@pytest.mark.anyio
async def test_intake_suggest_code_empty_rejected(e14_client):
    resp = await e14_client.post("/api/intake/suggest-code", json={"description": ""})
    assert resp.status_code == 422
