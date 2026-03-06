from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class CompanionAppStatus(BaseModel):
    battery_level: float = Field(..., description="Battery percentage (0-100)")
    is_charging: bool = Field(False)
    network_type: str = Field("WIFI", description="WIFI, 4G, 5G")
    signal_strength: int = Field(..., description="Signal strength in dBm")

class BankSMSPayload(BaseModel):
    sender: str = Field(..., description="Bank sender ID e.g. AD-HDFCBK")
    body: str = Field(..., description="Full SMS text. If encrypted=True, this is the ciphertext.")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Time SMS was received on phone")
    device_id: Optional[str] = Field(None, description="Unique ID of the companion app device")
    is_encrypted: bool = Field(False, description="Task 2.7: End-to-end encryption flag")
    iv: Optional[str] = Field(None, description="Initialization Vector if encrypted")
    status: Optional[CompanionAppStatus] = Field(None, description="Task 2.8: Battery/Connectivity status")

class BankWebhookResponse(BaseModel):
    success: bool
    message: str
    utr: Optional[str] = None
    matched: bool = False
    booking_id: Optional[str] = None
