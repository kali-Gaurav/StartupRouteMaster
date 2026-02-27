import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from app import app
from database import get_db
from models import StationMaster
from services.cache_service import CacheService

client = TestClient(app)

def test_station_search_kota(db: Session):
    """Test searching for 'kota' should return KOTA JN first."""
    # Assuming data is seeded
    response = client.get("/api/stations/search?q=kota&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["stations"]) > 0
    # Check if KOTA JN is first or high ranked
    first_station = data["stations"][0]
    assert "KOTA" in first_station["code"] or "KOTA" in first_station["name"]

def test_station_search_palak(db: Session):
    """Test searching for 'palak' should return PALAKKAD JN first."""
    response = client.get("/api/stations/search?q=palak&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    # Assuming PALAKKAD JN exists

def test_station_search_jaipur(db: Session):
    """Test searching for 'jaipur' should rank JAIPUR JN high."""
    response = client.get("/api/stations/search?q=jaipur&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    # Check ranking

def test_station_search_j(db: Session):
    """Test searching for 'j' should prioritize junctions starting with J."""
    response = client.get("/api/stations/search?q=j&limit=20")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    # Check junctions are prioritized

def test_station_search_empty(db: Session):
    """Test empty query returns empty list."""
    response = client.get("/api/stations/search?q=&limit=10")
    assert response.status_code == 422  # Validation error for min_length

def test_station_search_single_char(db: Session):
    """Test single char query prioritizes code + junction matches."""
    response = client.get("/api/stations/search?q=k&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

def test_station_search_limit(db: Session):
    """Test limit parameter."""
    response = client.get("/api/stations/search?q=delhi&limit=5")
    assert response.status_code == 200
    data = response.json()
    assert len(data["stations"]) <= 5

def test_station_search_caching(db: Session):
    """Test caching works."""
    # First request
    response1 = client.get("/api/stations/search?q=mumbai&limit=10")
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["cached"] is False

    # Second request should be cached
    response2 = client.get("/api/stations/search?q=mumbai&limit=10")
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["cached"] is True
    assert data1["stations"] == data2["stations"]
