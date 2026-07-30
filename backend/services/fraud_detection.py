"""
Shim module for fraud_detection import compatibility.
The actual implementation is in services.security.fraud
"""

from services.security.fraud import FraudDetectionService

# Create a singleton instance for convenience
fraud_detection_service = FraudDetectionService()

__all__ = ["FraudDetectionService", "fraud_detection_service"]