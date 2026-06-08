"""
RouteMaster SEO — City Pair Route Pages
=========================================
GET /api/v1/routes/{from_slug}/{to_slug}

Powers the SEO pages like /trains/new-delhi-to-mumbai.
Returns structured route data + SEO metadata.

Slug format: "new-delhi" maps to station code via CITY_TO_CODE lookup.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from datetime import date, datetime

logger = logging.getLogger("routemaster.v1.seo")
router = APIRouter(prefix="/routes", tags=["seo-routes"])

# City name → primary station code mapping
CITY_SLUG_TO_CODE: dict[str, str] = {
    # North India
    "new-delhi": "NDLS",
    "delhi": "NDLS",
    "old-delhi": "DLI",
    "hazrat-nizamuddin": "NZM",
    # West
    "mumbai": "BCT",
    "mumbai-central": "BCT",
    "csmt-mumbai": "CSTM",
    "pune": "PUNE",
    "ahmedabad": "ADI",
    "surat": "ST",
    "vadodara": "BRC",
    "rajkot": "RJT",
    "nashik": "NK",
    # South
    "chennai": "MAS",
    "bengaluru": "SBC",
    "bangalore": "SBC",
    "hyderabad": "SC",
    "secunderabad": "SC",
    "coimbatore": "CBE",
    "madurai": "MDU",
    "thiruvananthapuram": "TVC",
    "kochi": "ERS",
    "ernakulam": "ERS",
    "kozhikode": "CLT",
    "vijayawada": "BZA",
    "visakhapatnam": "VSKP",
    "tirupati": "TPTY",
    "mysuru": "MYS",
    "mysore": "MYS",
    # East
    "kolkata": "HWH",
    "howrah": "HWH",
    "bhubaneswar": "BBS",
    "patna": "PNBE",
    "guwahati": "GHY",
    "ranchi": "HTE",
    "jamshedpur": "TATA",
    # Central
    "bhopal": "BPL",
    "indore": "INDB",
    "nagpur": "NGP",
    "jabalpur": "JBP",
    "raipur": "R",
    # Rajasthan / UP
    "jaipur": "JP",
    "jodhpur": "JU",
    "udaipur": "UDZ",
    "kota": "KOTA",
    "ajmer": "AII",
    "lucknow": "LKO",
    "varanasi": "BSB",
    "kanpur": "CNB",
    "prayagraj": "PRYJ",
    "allahabad": "PRYJ",
    "gorakhpur": "GKP",
    "agra": "AGC",
    "mathura": "MTJ",
    # Punjab / Haryana
    "amritsar": "ASR",
    "ludhiana": "LDH",
    "chandigarh": "CDG",
    "ambala": "UMB",
    "jammu": "JAT",
    # Others
    "gwalior": "GWL",
    "jhansi": "JHS",
    "itarsi": "ET",
    "dhanbad": "DHN",
    "asansol": "ASN",
    "jalpaiguri": "NJP",
    "gaya": "GAYA",
}

# Top 100 city pairs for sitemap
TOP_PAIRS = [
    ("new-delhi", "mumbai"),          ("mumbai", "new-delhi"),
    ("new-delhi", "kolkata"),          ("kolkata", "new-delhi"),
    ("new-delhi", "chennai"),          ("chennai", "new-delhi"),
    ("new-delhi", "bengaluru"),        ("bengaluru", "new-delhi"),
    ("new-delhi", "hyderabad"),        ("hyderabad", "new-delhi"),
    ("mumbai", "kolkata"),             ("kolkata", "mumbai"),
    ("mumbai", "chennai"),             ("chennai", "mumbai"),
    ("mumbai", "bengaluru"),           ("bengaluru", "mumbai"),
    ("mumbai", "pune"),                ("pune", "mumbai"),
    ("new-delhi", "jaipur"),           ("jaipur", "new-delhi"),
    ("new-delhi", "lucknow"),          ("lucknow", "new-delhi"),
    ("new-delhi", "patna"),            ("patna", "new-delhi"),
    ("new-delhi", "varanasi"),         ("varanasi", "new-delhi"),
    ("new-delhi", "amritsar"),         ("amritsar", "new-delhi"),
    ("new-delhi", "agra"),             ("agra", "new-delhi"),
    ("new-delhi", "chandigarh"),       ("chandigarh", "new-delhi"),
    ("new-delhi", "guwahati"),         ("guwahati", "new-delhi"),
    ("kolkata", "chennai"),            ("chennai", "kolkata"),
    ("kolkata", "bengaluru"),          ("bengaluru", "kolkata"),
    ("kolkata", "hyderabad"),          ("hyderabad", "kolkata"),
    ("chennai", "bengaluru"),          ("bengaluru", "chennai"),
    ("chennai", "hyderabad"),          ("hyderabad", "chennai"),
    ("mumbai", "ahmedabad"),           ("ahmedabad", "mumbai"),
    ("mumbai", "surat"),               ("surat", "mumbai"),
    ("mumbai", "hyderabad"),           ("hyderabad", "mumbai"),
    ("mumbai", "vadodara"),            ("vadodara", "mumbai"),
    ("new-delhi", "bhopal"),           ("bhopal", "new-delhi"),
    ("new-delhi", "nagpur"),           ("nagpur", "new-delhi"),
    ("new-delhi", "gwalior"),          ("gwalior", "new-delhi"),
    ("new-delhi", "jodhpur"),          ("jodhpur", "new-delhi"),
    ("bengaluru", "hyderabad"),        ("hyderabad", "bengaluru"),
    ("bengaluru", "thiruvananthapuram"), ("thiruvananthapuram", "bengaluru"),
    ("chennai", "thiruvananthapuram"), ("thiruvananthapuram", "chennai"),
    ("mumbai", "kota"),                ("kota", "mumbai"),
    ("new-delhi", "kota"),             ("kota", "new-delhi"),
    ("patna", "kolkata"),              ("kolkata", "patna"),
    ("bhubaneswar", "kolkata"),        ("kolkata", "bhubaneswar"),
    ("visakhapatnam", "chennai"),      ("chennai", "visakhapatnam"),
    ("vijayawada", "chennai"),         ("chennai", "vijayawada"),
    ("pune", "hyderabad"),             ("hyderabad", "pune"),
    ("lucknow", "kolkata"),            ("kolkata", "lucknow"),
    ("guwahati", "kolkata"),           ("kolkata", "guwahati"),
    ("jaipur", "mumbai"),              ("mumbai", "jaipur"),
    ("coimbatore", "chennai"),         ("chennai", "coimbatore"),
    ("madurai", "chennai"),            ("chennai", "madurai"),
    ("kochi", "chennai"),              ("chennai", "kochi"),
]


def slug_to_code(slug: str) -> Optional[str]:
    """Convert URL slug to station code."""
    return CITY_SLUG_TO_CODE.get(slug.lower().strip())


def code_to_city_name(code: str) -> str:
    """Get display name from station code."""
    reverse = {v: k.replace("-", " ").title() for k, v in CITY_SLUG_TO_CODE.items()}
    return reverse.get(code.upper(), code)


def _redis():
    try:
        import redis as rl
        url = os.getenv("REDIS_URL", "")
        if url:
            return rl.from_url(url, decode_responses=True, socket_connect_timeout=3)
    except Exception:
        pass
    return None


@router.get("/top-pairs")
async def get_top_pairs():
    """Returns top 100 city pairs for sitemap generation."""
    pairs = []
    for from_slug, to_slug in TOP_PAIRS[:100]:
        fc = slug_to_code(from_slug)
        tc = slug_to_code(to_slug)
        if fc and tc:
            pairs.append({
                "from_slug": from_slug,
                "to_slug": to_slug,
                "from_code": fc,
                "to_code": tc,
                "url": f"/trains/{from_slug}-to-{to_slug}",
                "from_name": code_to_city_name(fc),
                "to_name": code_to_city_name(tc),
            })
    return {"pairs": pairs, "total": len(pairs)}


@router.get("/{from_slug}/{to_slug}")
async def get_city_pair_routes(
    from_slug: str,
    to_slug: str,
    date_str: Optional[str] = Query(None, alias="date"),
):
    """
    SEO route page data for a city pair.
    Powers /trains/new-delhi-to-mumbai style pages.
    """
    from_code = slug_to_code(from_slug)
    to_code = slug_to_code(to_slug)

    if not from_code:
        raise HTTPException(status_code=404, detail=f"City '{from_slug}' not recognized.")
    if not to_code:
        raise HTTPException(status_code=404, detail=f"City '{to_slug}' not recognized.")

    travel_date = date.today()
    if date_str:
        try:
            travel_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            pass

    from_name = code_to_city_name(from_code)
    to_name = code_to_city_name(to_code)

    cache_key = f"seo:{from_code}:{to_code}:{travel_date}"
    r = _redis()
    if r:
        try:
            cached = r.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    # Run the search
    try:
        from core.route_engine.data_provider import DataProvider
        dp = DataProvider()
        direct = dp.find_direct_trains(from_code, to_code, travel_date, limit=10)
        transfers = dp.find_hub_trains(from_code, to_code, limit_per_leg=5) if len(direct) < 3 else []

        # Format trains
        def fmt_time(t):
            return str(t or "")[:5] if t else "--:--"

        direct_list = [{
            "train_number": tr.route_id or tr.trip_id,
            "train_name": tr.train_name,
            "departure": fmt_time(tr.departure_time),
            "arrival": fmt_time(tr.arrival_time),
            "duration_hrs": round(tr.duration_minutes / 60, 1),
        } for tr in direct[:10]]

        transfer_list = [{
            "hub": tr.hub_stop.name,
            "train1": tr.leg1.train_name,
            "train2": tr.leg2.train_name,
            "total_hrs": round(tr.total_duration_minutes / 60, 1),
        } for tr in transfers[:5]]

        dp.close()
    except Exception as e:
        logger.warning(f"Route search failed for SEO page {from_code}→{to_code}: {e}")
        direct_list = []
        transfer_list = []

    # Build SEO content
    dist_hint = ""
    duration_hint = ""
    if direct_list:
        min_dur = min(t["duration_hrs"] for t in direct_list)
        duration_hint = f"The fastest train takes about {min_dur} hours."

    result = {
        "from_code": from_code,
        "to_code": to_code,
        "from_name": from_name,
        "to_name": to_name,
        "from_slug": from_slug,
        "to_slug": to_slug,
        "date": str(travel_date),
        "direct_trains": direct_list,
        "transfer_routes": transfer_list,
        "total_direct": len(direct_list),
        "total_options": len(direct_list) + len(transfer_list),
        # SEO metadata
        "seo": {
            "title": f"{direct_list[0]['train_name'] if direct_list else ''} and {len(direct_list)} more trains from {from_name} to {to_name}",
            "h1": f"Trains from {from_name} to {to_name}",
            "description": (
                f"Find all {len(direct_list)} direct trains from {from_name} to {to_name}. "
                f"{duration_hint} "
                f"Check live status, fares, and book on IRCTC in one click. "
                f"Plus {len(transfer_list)} transfer route options."
            ),
            "faq": [
                {
                    "q": f"How many trains run from {from_name} to {to_name}?",
                    "a": f"There are {len(direct_list)} direct trains from {from_name} to {to_name}. "
                         f"Plus {len(transfer_list)} routes with 1 transfer."
                },
                {
                    "q": f"What is the fastest train from {from_name} to {to_name}?",
                    "a": (
                        f"{direct_list[0]['train_name']} ({direct_list[0]['train_number']}) departing at {direct_list[0]['departure']} takes {direct_list[0]['duration_hrs']} hours."
                        if direct_list else f"Search above for current schedules from {from_name} to {to_name}."
                    )
                },
                {
                    "q": f"How do I book a train ticket from {from_name} to {to_name}?",
                    "a": f"Click 'Book on IRCTC' next to any train. You'll be taken to IRCTC's website with all details pre-filled."
                },
            ]
        },
        # IRCTC deep link
        "book_url": (
            f"https://www.irctc.co.in/nget/train-search?"
            f"fromStn={from_code}&toStn={to_code}&jrnyDate={travel_date.strftime('%d/%m/%Y')}&jrnyClass=SL&jrnySrc=P&ticketType=E"
        ),
    }

    if r and direct_list:
        try:
            r.setex(cache_key, 3600, json.dumps(result))
        except Exception:
            pass

    return result
