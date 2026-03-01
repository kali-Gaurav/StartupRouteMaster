import os
import logging
import asyncio
import aiohttp

logger = logging.getLogger(__name__)

# It's best to put these in Config, but for MVP we read directly from env
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

async def send_telegram_message(text: str):
    """
    Sends an async fire-and-forget message to the configured Telegram bot.
    """
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram credentials missing. Skipping notification.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }

    try:
        # Non-blocking network request
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=5) as response:
                if response.status != 200:
                    logger.error(f"Telegram API failed with status {response.status}")
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")

def format_booking_alert(booking_id: str, journey: dict, passengers: list, phone: str, email: str) -> str:
    """
    Formats the booking request into a clean Telegram alert.
    """
    source = journey.get("source", "Unknown")
    dest = journey.get("destination", "Unknown")
    date = journey.get("date", "Unknown")

    pax_str = ""
    for i, p in enumerate(passengers):
        pax_str += f"{i+1}. {p.get('name')} ({p.get('age')}{p.get('gender')}) - {p.get('preference')}\n"

    msg = f"""🚨 <b>NEW BOOKING REQUEST</b> 🚨

<b>ID:</b> {booking_id}
<b>Route:</b> {source} ➡️ {dest}
<b>Date:</b> {date}

<b>Contact:</b>
📞 {phone}
📧 {email}

<b>Passengers:</b>
{pax_str}
<b>Action:</b> Please manually book this ticket on IRCTC and send details to the user."""

    return msg
