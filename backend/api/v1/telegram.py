"""
RouteMaster Telegram Bot
========================
Handles incoming messages from Telegram and replies with train routes.

Bot: @RoutemasternagarindustrisBot (from TELEGRAM_BOT_TOKEN in .env)

Message formats supported:
  "Delhi Mumbai"                    → search today
  "Delhi Mumbai 15 June"            → search specific date
  "Delhi Mumbai 2026-06-15"         → ISO date
  "NDLS BCT"                        → station codes
  "live 12951"                      → live train status
  "pnr 1234567890"                  → PNR status
  "/start"                          → welcome message
  "/help"                           → usage guide

Webhook registration:
  POST https://api.telegram.org/bot{TOKEN}/setWebhook
  {"url": "https://routemaster-api.onrender.com/api/v1/telegram/webhook"}

The bot auto-registers its webhook on first startup.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import date, datetime, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, Request, Response

logger = logging.getLogger("routemaster.telegram")
router = APIRouter(prefix="/telegram", tags=["telegram"])

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Station name → code mapping (subset for NLP)
NAME_TO_CODE = {
    "delhi": "NDLS", "new delhi": "NDLS", "ndls": "NDLS",
    "mumbai": "BCT", "bombay": "BCT", "mumbai central": "BCT", "bct": "BCT", "mmct": "BCT",
    "kolkata": "HWH", "calcutta": "HWH", "howrah": "HWH", "hwh": "HWH",
    "chennai": "MAS", "madras": "MAS", "mas": "MAS",
    "bengaluru": "SBC", "bangalore": "SBC", "sbc": "SBC",
    "hyderabad": "SC", "secunderabad": "SC", "sc": "SC",
    "pune": "PUNE",
    "ahmedabad": "ADI", "adi": "ADI",
    "jaipur": "JP", "jp": "JP",
    "lucknow": "LKO", "lko": "LKO",
    "patna": "PNBE", "pnbe": "PNBE",
    "varanasi": "BSB", "banaras": "BSB", "bsb": "BSB",
    "kanpur": "CNB", "cnb": "CNB",
    "prayagraj": "PRYJ", "allahabad": "PRYJ",
    "gorakhpur": "GKP",
    "agra": "AGC",
    "bhopal": "BPL",
    "nagpur": "NGP",
    "surat": "ST",
    "amritsar": "ASR",
    "guwahati": "GHY",
    "ranchi": "HTE",
    "bhubaneswar": "BBS",
    "kochi": "ERS", "ernakulam": "ERS",
    "thiruvananthapuram": "TVC", "trivandrum": "TVC",
    "visakhapatnam": "VSKP", "vizag": "VSKP",
}

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


async def send_message(chat_id: int, text: str, parse_mode: str = "HTML"):
    """Send a message via Telegram Bot API."""
    if not BOT_TOKEN:
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{TELEGRAM_API}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
            )
    except Exception as e:
        logger.warning(f"Telegram send failed: {e}")


def parse_city_name(text: str) -> Optional[str]:
    """Try to match a city/station name to a code."""
    t = text.lower().strip()
    if t.upper() in [c.upper() for c in NAME_TO_CODE.values()]:
        return t.upper()
    return NAME_TO_CODE.get(t)


def parse_date_from_text(tokens: list[str]) -> Optional[date]:
    """Try to parse a date like '15 June', 'tomorrow', '2026-06-15' from token list."""
    text = " ".join(tokens).lower()

    # ISO format
    iso_match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if iso_match:
        try:
            return datetime.strptime(iso_match.group(), "%Y-%m-%d").date()
        except ValueError:
            pass

    # "tomorrow"
    if "tomorrow" in text:
        return date.today() + timedelta(days=1)
    if "today" in text:
        return date.today()

    # "15 June" or "June 15"
    for i, token in enumerate(tokens):
        if token.isdigit() and 1 <= int(token) <= 31:
            day = int(token)
            # Look for month nearby
            for j in range(max(0, i - 2), min(len(tokens), i + 3)):
                month_num = MONTH_MAP.get(tokens[j].lower().rstrip(","))
                if month_num:
                    year = date.today().year
                    try:
                        d = date(year, month_num, day)
                        if d < date.today():
                            d = date(year + 1, month_num, day)
                        return d
                    except ValueError:
                        pass
    return None


def parse_route_query(text: str) -> Optional[dict]:
    """
    Parse a free-text route query into {from, to, date}.
    Handles: "Delhi Mumbai", "NDLS BCT 15 June", "Delhi to Mumbai tomorrow"
    """
    # Clean "to" connectors
    cleaned = re.sub(r"\b(to|se|ke liye|→|->)\b", " ", text, flags=re.I)
    tokens = [t.strip() for t in cleaned.split() if t.strip()]
    if len(tokens) < 2:
        return None

    # Try pairs of consecutive tokens/phrases as station names
    from_code = None
    to_code = None
    remaining_tokens = []

    # Try 2-word combos first, then single words
    for width in [2, 1]:
        if from_code and to_code:
            break
        for i in range(len(tokens) - width + 1):
            phrase = " ".join(tokens[i:i + width])
            code = parse_city_name(phrase)
            if code:
                if from_code is None:
                    from_code = code
                    remaining_tokens = tokens[:i] + tokens[i + width:]
                elif to_code is None and code != from_code:
                    to_code = code
                    break

    if not from_code or not to_code:
        return None

    travel_date = parse_date_from_text(remaining_tokens) or date.today()
    return {"from": from_code, "to": to_code, "date": travel_date}


async def handle_route_search(chat_id: int, query: dict):
    """Run a route search and format the response."""
    from_code = query["from"]
    to_code = query["to"]
    travel_date = query["date"]

    await send_message(chat_id, f"🔍 Searching trains from <b>{from_code}</b> to <b>{to_code}</b> on {travel_date.strftime('%d %b %Y')}...")

    try:
        from core.route_engine.data_provider import DataProvider
        dp = DataProvider()
        trains = dp.find_direct_trains(from_code, to_code, travel_date, limit=5)
        dp.close()
    except Exception as e:
        await send_message(chat_id, f"❌ Search failed: {e}")
        return

    if not trains:
        await send_message(chat_id, (
            f"😕 No direct trains found from <b>{from_code}</b> to <b>{to_code}</b> on {travel_date.strftime('%d %b')}.\n\n"
            f"💡 Try the full search: <a href='https://routemaster.vercel.app/?from={from_code}&to={to_code}'>routemaster.vercel.app</a>"
        ))
        return

    lines = [
        f"🚂 <b>Trains: {from_code} → {to_code}</b>",
        f"📅 {travel_date.strftime('%A, %d %b %Y')}",
        f"Found <b>{len(trains)}</b> direct train(s)\n",
    ]

    for i, t in enumerate(trains[:5], 1):
        dep = str(t.departure_time or "")[:5]
        arr = str(t.arrival_time or "")[:5]
        dur_h = t.duration_minutes // 60
        dur_m = t.duration_minutes % 60
        dur_str = f"{dur_h}h {dur_m}m" if dur_m else f"{dur_h}h"

        irctc_date = travel_date.strftime("%d/%m/%Y")
        irctc_url = (
            f"https://www.irctc.co.in/nget/train-search?"
            f"fromStn={from_code}&toStn={to_code}&jrnyDate={irctc_date}"
            f"&jrnyClass=SL&trainNo={t.route_id}&jrnySrc=P&ticketType=E"
        )

        lines.append(
            f"<b>{i}. {t.train_name}</b> ({t.route_id})\n"
            f"   🕐 {dep} → {arr} ({dur_str})\n"
            f"   🎟️ <a href='{irctc_url}'>Book on IRCTC</a>"
        )

    lines.append(f"\n🌐 <a href='https://routemaster.vercel.app/?from={from_code}&to={to_code}'>See all routes + transfers</a>")
    await send_message(chat_id, "\n".join(lines))


async def handle_live_status(chat_id: int, train_no: str):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(f"https://rappid.in/apis/train.php?train_no={train_no}")
            data = res.json()
        if not data.get("success"):
            await send_message(chat_id, f"❌ No live data for train {train_no}. It may not be running today.")
            return

        stops = data.get("data", [])
        current = next((s for s in stops if s.get("is_current_station")), None)
        delay_info = current.get("delay", "On Time") if current else "On Time"
        current_name = current.get("station_name", "—") if current else "Not running"
        next_stop = None
        for i, s in enumerate(stops):
            if s.get("is_current_station") and i + 1 < len(stops):
                next_stop = stops[i + 1].get("station_name")

        text = (
            f"🚂 <b>Train {train_no} — Live Status</b>\n"
            f"📌 Current: <b>{current_name}</b>\n"
            f"⏭️ Next: {next_stop or '—'}\n"
            f"⏱️ Status: {delay_info}\n"
            f"🔄 {data.get('updated_time', '')}\n\n"
            f"🌐 <a href='https://routemaster.vercel.app/track/{train_no}'>Full tracking</a>"
        )
        await send_message(chat_id, text)
    except Exception as e:
        await send_message(chat_id, f"❌ Could not fetch live status: {e}")


WELCOME_MSG = """👋 <b>Welcome to Route Master Bot!</b>

I help you find Indian Railways train routes instantly.

<b>Search routes:</b>
• Delhi Mumbai
• NDLS BCT 15 June
• Delhi to Bengaluru tomorrow

<b>Live status:</b>
• live 12951

<b>PNR status:</b>
• pnr 1234567890

<b>Commands:</b>
/help — Show this guide
/start — Welcome message

🌐 Full search: routemaster.vercel.app"""

HELP_MSG = """📖 <b>Route Master Bot Guide</b>

<b>Train Search:</b>
Just type: <code>Delhi Mumbai</code>
Or with date: <code>NDLS BCT 15 June</code>

<b>Live Train Status:</b>
Type: <code>live 12951</code>

<b>PNR Status:</b>
Type: <code>pnr 1234567890</code>

<b>Station codes (shortcuts):</b>
New Delhi = NDLS, Mumbai = BCT
Chennai = MAS, Kolkata = HWH
Bengaluru = SBC, Hyderabad = SC

<b>Tips:</b>
• Use station codes for accurate results
• Dates: "15 June", "tomorrow", "2026-06-15"
• I search for today's trains by default

🌐 routemaster.vercel.app"""


@router.post("/webhook")
async def telegram_webhook(request: Request):
    """Receive and process Telegram webhook updates."""
    if not BOT_TOKEN:
        return Response(content="Bot token not configured", status_code=200)

    try:
        update = await request.json()
    except Exception:
        return Response(status_code=200)

    message = update.get("message") or update.get("edited_message")
    if not message:
        return Response(status_code=200)

    chat_id = message.get("chat", {}).get("id")
    text = (message.get("text") or "").strip()

    if not chat_id or not text:
        return Response(status_code=200)

    text_lower = text.lower()

    # Commands
    if text_lower in ("/start", "start"):
        await send_message(chat_id, WELCOME_MSG)
    elif text_lower in ("/help", "help"):
        await send_message(chat_id, HELP_MSG)

    # Live status
    elif text_lower.startswith("live ") or text_lower.startswith("/live "):
        train_no = re.sub(r"^(live|/live)\s+", "", text, flags=re.I).strip()
        if train_no and train_no.isdigit():
            await handle_live_status(chat_id, train_no)
        else:
            await send_message(chat_id, "❌ Please provide a train number. Example: <code>live 12951</code>")

    # PNR status
    elif text_lower.startswith("pnr ") or text_lower.startswith("/pnr "):
        pnr = re.sub(r"^(pnr|/pnr)\s+", "", text, flags=re.I).strip()
        if len(pnr) == 10 and pnr.isdigit():
            await send_message(chat_id, f"🎟️ Check your PNR status here:\n🌐 routemaster.vercel.app/pnr/{pnr}\n\n(Direct IRCTC PNR lookup requires API key)")
        else:
            await send_message(chat_id, "❌ PNR must be 10 digits. Example: <code>pnr 1234567890</code>")

    # Route search
    else:
        query = parse_route_query(text)
        if query:
            await handle_route_search(chat_id, query)
        else:
            await send_message(chat_id, (
                "🤔 I couldn't understand that.\n\n"
                "Try: <code>Delhi Mumbai</code> or <code>NDLS BCT 15 June</code>\n"
                "Or type /help for the full guide."
            ))

    return Response(status_code=200)


@router.post("/register-webhook")
async def register_webhook():
    """Register the Telegram webhook. Call once after deploy."""
    if not BOT_TOKEN:
        return {"error": "TELEGRAM_BOT_TOKEN not set"}
    base_url = os.getenv("RENDER_EXTERNAL_URL", os.getenv("FRONTEND_URL", "https://routemaster-api.onrender.com"))
    webhook_url = f"{base_url.rstrip('/')}/api/v1/telegram/webhook"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{TELEGRAM_API}/setWebhook",
                json={"url": webhook_url, "drop_pending_updates": True},
            )
            data = r.json()
        return {"registered": data.get("ok"), "webhook_url": webhook_url, "telegram": data}
    except Exception as e:
        return {"error": str(e)}


@router.get("/info")
async def bot_info():
    """Get bot info and webhook status."""
    if not BOT_TOKEN:
        return {"configured": False, "message": "TELEGRAM_BOT_TOKEN not set in environment"}
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            me = await client.get(f"{TELEGRAM_API}/getMe")
            webhook = await client.get(f"{TELEGRAM_API}/getWebhookInfo")
        return {
            "configured": True,
            "bot": me.json().get("result", {}),
            "webhook": webhook.json().get("result", {}),
        }
    except Exception as e:
        return {"configured": True, "error": str(e)}
