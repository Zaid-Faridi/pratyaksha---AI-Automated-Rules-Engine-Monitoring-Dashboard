"""
Pytest configuration and shared test fixtures for Pratyaksha Backend.
Uses an isolated in-memory SQLite database for test execution.
"""

import sys
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import Base, get_db
from app.main import app
from app.models import (
    Centre,
    Camera,
    SanctionedInventory,
    Batch,
    AttendanceRecord,
)

# In-memory SQLite engine with StaticPool to retain tables across the test session
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_session():
    """Create fresh database tables for each test and tear down afterwards."""
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def standard_setup(db_session):
    """Convenience fixture creating a standard centre, camera, inventory, and batch."""
    centre = Centre(
        id="centre_test_01",
        name="Test Skilling Centre",
        state="Maharashtra",
        district="Pune",
        lat=18.5204,
        lng=73.8567,
        scheme="PMKVY 4.0",
    )
    db_session.add(centre)

    camera = Camera(
        id="cam_test_01",
        centre_id="centre_test_01",
        zone_names=["classroom", "workshop"],
        status="online",
    )
    db_session.add(camera)

    inventory_items = [
        SanctionedInventory(centre_id="centre_test_01", zone="classroom", item="chair", expected_count=20),
        SanctionedInventory(centre_id="centre_test_01", zone="classroom", item="computer", expected_count=10),
    ]
    db_session.add_all(inventory_items)

    batch = Batch(
        id="batch_test_01",
        centre_id="centre_test_01",
        name="Computer Literacy Level 3",
        start_time="09:00",
        end_time="13:00",
        days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
        zone="classroom",
    )
    db_session.add(batch)

    db_session.commit()
    return {
        "centre": centre,
        "camera": camera,
        "batch": batch,
    }
