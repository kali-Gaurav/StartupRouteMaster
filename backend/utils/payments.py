import urllib.parse
import uuid
import time
import logging
import re

logger = logging.getLogger(__name__)

def generate_upi_uri(
    merchant_vpa: str,
    merchant_name: str,
    amount: float,
    transaction_id: str = None,
    transaction_note: str = None,
    currency: str = "INR"
) -> tuple[str, str]:
    """
    Task 1: Generates a standard NPCI UPI URI.
    Subtask 1.1: NPCI Format
    Subtask 1.2: Custom notes and IDs
    """
    # VPA Validation
    if not re.match(r"^[\w\.\-]+@[\w\-]+$", merchant_vpa):
        logger.warning(f"Potentially invalid VPA: {merchant_vpa}")

    if not transaction_id:
        transaction_id = f"TX{int(time.time())}{str(uuid.uuid4().hex[:6]).upper()}"
    
    if not transaction_note:
        transaction_note = f"Booking {transaction_id}"

    # NPCI Parameters
    # pa: Payee VPA, pn: Payee Name, am: Amount, cu: Currency, tn: Note, tr: Ref ID
    params = {
        "pa": merchant_vpa,
        "pn": merchant_name,
        "am": f"{amount:.2f}",
        "cu": currency,
        "tn": transaction_note,
        "tr": transaction_id
    }
    
    # URL encode parameters safely
    encoded_params = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    upi_uri = f"upi://pay?{encoded_params}"
    
    logger.info(f"Generated UPI URI: {upi_uri}")
    return upi_uri, transaction_id

def validate_utr(utr: str) -> bool:
    """Task 16: Validates if a string is a valid 12-digit UPI UTR."""
    return bool(re.match(r"^\d{12}$", utr))
