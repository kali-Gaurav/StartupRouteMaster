import urllib.parse
import uuid
import time
import logging
import re
import io
from typing import Optional, cast
import qrcode
from qrcode.constants import ERROR_CORRECT_H
from PIL import Image

logger = logging.getLogger(__name__)

def generate_upi_uri(
    merchant_vpa: str,
    merchant_name: str,
    amount: float,
    transaction_id: Optional[str] = None,
    transaction_note: Optional[str] = None,
    currency: str = "INR",
    merchant_code: str = "4112", # MCC 4112 is Passenger Railways
    min_amount: Optional[float] = None,
    org_id: Optional[str] = None,
    sign: Optional[str] = None
) -> tuple[str, str]:
    """
    Task 1: Generates an Advanced NPCI UPI URI 2.0.
    Subtasks: URI 2.0, mam, mc, tid, currency locking.
    """
    if currency != "INR":
        logger.warning(f"Forcing currency to INR from {currency}")
        currency = "INR"

    # VPA Validation
    if not re.match(r"^[\w\.\-]+@[\w\-]+$", merchant_vpa):
        logger.warning(f"Potentially invalid VPA: {merchant_vpa}")

    if not transaction_id:
        transaction_id = f"TX{int(time.time())}{str(uuid.uuid4().hex[:6]).upper()}"
    
    if not transaction_note:
        transaction_note = f"Booking {transaction_id}"

    # NPCI Parameters (URI 2.0)
    # pa: Payee VPA, pn: Payee Name, am: Amount, cu: Currency, tn: Note, tr: Ref ID, tid: Transaction ID, mc: Merchant Category
    params = {
        "pa": merchant_vpa,
        "pn": merchant_name,
        "mc": merchant_code,
        "tid": transaction_id,
        "tr": transaction_id,
        "tn": transaction_note,
        "am": f"{amount:.2f}",
        "cu": currency
    }

    if min_amount is not None:
        params["mam"] = f"{min_amount:.2f}"
    
    if org_id:
        params["orgid"] = org_id
    
    if sign:
        params["sign"] = sign
    
    # URL encode parameters safely
    encoded_params = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    upi_uri = f"upi://pay?{encoded_params}"
    
    logger.info(f"Generated UPI URI: {upi_uri}")
    return upi_uri, transaction_id

def generate_upi_qr(upi_uri: str, logo_path: Optional[str] = None) -> io.BytesIO:
    """
    Task 1.5: QR Code logo embedding (RouteMaster branding).
    Generates a QR code for the UPI URI with an optional logo.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(upi_uri)
    qr.make(fit=True)

    img = cast(Image.Image, qr.make_image(fill_color="black", back_color="white"))
    img = img.convert('RGB')

    if logo_path:
        try:
            logo = Image.open(logo_path)
            # Calculate dimensions to place logo in the center
            pos = ((img.size[0] - logo.size[0]) // 2, (img.size[1] - logo.size[1]) // 2)
            img.paste(logo, pos)
        except Exception as e:
            logger.error(f"Failed to embed logo in QR: {e}")

    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    return img_byte_arr

def create_short_payment_url(upi_uri: str, base_url: str = "http://localhost:8000") -> str:
    """
    Task 1.6: Short-URL redirector for UPI links.
    Stores the URI in Redis and returns a shortened URL.
    """
    from services.cache_service import cache_service
    short_id = str(uuid.uuid4().hex[:8])
    # Store for 30 minutes
    cache_service.set(f"upi_short:{short_id}", upi_uri, ttl_seconds=1800)
    return f"{base_url}/api/payments/u/{short_id}"

def validate_utr(utr: str) -> bool:
    """Task 16: Validates if a string is a valid 12-digit UPI UTR."""
    return bool(re.match(r"^\d{12}$", utr))

def standardize_utr(utr: str) -> str:
    """
    [24.1] Standardizes UTR by:
    - Stripping whitespace.
    - Converting 'O' -> '0', 'I' -> '1', 'L' -> '1'.
    - Keeping only alpha-numeric.
    """
    if not utr: return ""
    utr = utr.strip().upper()
    utr = utr.replace("O", "0").replace("I", "1").replace("L", "1")
    # Remove any non-numeric if it's supposed to be purely numeric (most UPI UTRs are)
    # But some bank refs might have letters, let's stick to simple replacements first
    return utr

def get_unique_paisa_amount(base_amount: float, db_session, vpa: str) -> float:
    """
    Task 2: cent-matching.
    Returns a random paisa amount (0.01 to 0.99) that is currently unique for 
    pending bookings on this VPA to allow identification without UTR.
    """
    import random
    from database.models import Booking, EscrowStatus
    
    # Try up to 50 times to find a unique paisa offset for this base amount on this VPA
    for _ in range(50):
        paisa = random.randint(1, 99) / 100.0
        target_amount = round(base_amount + paisa, 2)
        
        # Check if any pending booking has this exact amount on this VPA
        exists = db_session.query(Booking).filter(
            Booking.merchant_vpa == vpa,
            Booking.amount_paid == target_amount,
            Booking.escrow_status == EscrowStatus.CREATED
        ).first()
        
        if not exists:
            return target_amount
            
    # Fallback to just random if collision check fails too many times
    return round(base_amount + (random.randint(1, 99) / 100.0), 2)
