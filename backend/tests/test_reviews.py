from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import pytest

from backend.models import User, Booking, Route, Review

def test_create_review(client: TestClient, db_session: Session):
    """
    Test creating a review for a booking.
    """
    # 1. Create a user and log in
    user_email = "reviewuser@example.com"
    user_password = "password123"
    client.post("/api/users/register", json={"email": user_email, "password": user_password})
    login_response = client.post("/api/users/token", data={"username": user_email, "password": user_password})
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get user from DB to get their ID
    user = db_session.query(User).filter(User.email == user_email).first()
    assert user is not None

    # 3. Create a Route and a Booking for the user
    route = Route(
        source="Station A",
        destination="Station B",
        segments=[{"from": "A", "to": "B"}],
        total_duration="1h",
        total_cost=50.0,
        budget_category="economy"
    )
    db_session.add(route)
    db_session.commit()

    booking = Booking(
        user_id=user.id,
        route_id=route.id,
        travel_date="2025-12-25",
        booking_details={},
        amount_paid=50.0
    )
    db_session.add(booking)
    db_session.commit()

    # 4. Post a review for the booking
    review_response = client.post(
        "/api/reviews/",
        headers=headers,
        json={"booking_id": booking.id, "rating": 5, "comment": "Great trip!"},
    )
    
    assert review_response.status_code == 201
    data = review_response.json()
    assert data["rating"] == 5
    assert data["comment"] == "Great trip!"
    assert data["user_id"] == user.id
    assert data["booking_id"] == booking.id

    # 5. Verify the review is in the database
    review_in_db = db_session.query(Review).filter(Review.id == data["id"]).first()
    assert review_in_db is not None
    assert review_in_db.rating == 5

def test_create_review_for_other_user_booking_fails(client: TestClient, db_session: Session):
    """
    Test that a user cannot create a review for another user's booking.
    """
    # 1. Create user 1 and a booking for them
    user1_email = "user1@example.com"
    client.post("/api/users/register", json={"email": user1_email, "password": "password"})
    user1 = db_session.query(User).filter(User.email == user1_email).first()
    
    route = Route(source="C", destination="D", segments=[], total_duration="1h", total_cost=10)
    db_session.add(route)
    db_session.commit()
    
    booking1 = Booking(user_id=user1.id, route_id=route.id, travel_date="2025-01-01", booking_details={})
    db_session.add(booking1)
    db_session.commit()

    # 2. Create user 2 and log them in
    user2_email = "user2@example.com"
    client.post("/api/users/register", json={"email": user2_email, "password": "password"})
    login_response = client.post("/api/users/token", data={"username": user2_email, "password": "password"})
    token2 = login_response.json()["access_token"]
    headers2 = {"Authorization": f"Bearer {token2}"}

    # 3. User 2 tries to review User 1's booking
    review_response = client.post(
        "/api/reviews/",
        headers=headers2,
        json={"booking_id": booking1.id, "rating": 1, "comment": "Trying to review other's booking"},
    )

    assert review_response.status_code == 404 # As the booking is not found for this user
    assert "Booking not found" in review_response.json()["detail"]
