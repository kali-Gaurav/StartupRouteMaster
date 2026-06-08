"""
Fraud Detection Service Module.
Provides fraud detection and prevention functionality.
"""

from services.security.fraud import FraudDetectionService

# Create a singleton instance for convenience
fraud_service = FraudDetectionService()

__all__ = ["FraudDetectionService", "fraud_service"]