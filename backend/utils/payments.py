import urllib.parse
import uuid
import time
import logging
import re
import io
import qrcode
from PIL import Image

logger = logging.getLogger(__name__)

def generate_upi_uri(
    merchant_vpa: str,
    merchant_name: str,
    amount: float,
    transaction_id: str = None,
    transaction_note: str = None,
    currency: str = "INR",
    merchant_code: str = "4112", # MCC 4112 is Passenger Railways
    min_amount: float = None,
    org_id: str = None,
    sign: str = None
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

def generate_upi_qr(upi_uri: str, logo_path: str = None) -> io.BytesIO:
    """
    Task 1.5: QR Code logo embedding (RouteMaster branding).
    Generates a QR code for the UPI URI with an optional logo.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(upi_uri)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white").convert('RGB')

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
    return f"{base_url}/api/payment/u/{short_id}"

def validate_utr(utr: str) -> bool:
    """Task 16: Validates if a string is a valid 12-digit UPI UTR."""
    return bool(re.match(r"^\d{12}$", utr))
