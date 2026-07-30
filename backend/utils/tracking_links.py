import itsdangerous
from database.config import Config
from typing import Optional

class TrackingLinkGenerator:
    """
    Generates secure, time-limited, non-auth URLs for family members to track an SOS incident.
    """
    def __init__(self):
        self.serializer = itsdangerous.URLSafeTimedSerializer(Config.SUPABASE_SERVICE_KEY)
        self.salt = "sos-family-tracking"

    def generate_token(self, event_id: str) -> str:
        """Creates a signed token for the SOS event."""
        return self.serializer.dumps(event_id, salt=self.salt)

    def verify_token(self, token: str, max_age: int = 86400) -> Optional[str]:
        """Verifies the token and returns the event_id if valid."""
        try:
            return self.serializer.loads(token, salt=self.salt, max_age=max_age)
        except itsdangerous.BadSignature:
            return None

    def get_family_url(self, event_id: str) -> str:
        """Returns the full URL for the family tracking page."""
        token = self.generate_token(event_id)
        # Using the frontend URL base
        base_url = "https://routemaster.app/emergency/view"
        return f"{base_url}/{token}"

tracking_link_gen = TrackingLinkGenerator()
