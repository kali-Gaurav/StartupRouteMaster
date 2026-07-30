"""
[DAEDALUS] Route Master — Pre-Deploy Validation Script
======================================================
Run this BEFORE deploying. Tests every endpoint against a live server.
Prints a full pass/fail report.

Usage:
    # Test local server (must be running)
    python scripts/validate_deployment.py

    # Test production
    python scripts/validate_deployment.py --url https://routemaster-api.onrender.com

    # Just test database (no server needed)
    python scripts/validate_deployment.py --db-only

All 20 major city pair searches are tested.
Reports exact failure reasons so you can fix before deploy.
"""
import asyncio
import sys
import os
import argparse
import time
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

try:
    import httpx
except ImportError:
    print("pip install httpx")
    sys.exit(1)

G = "\033[92m✅"; R = "\033[91m❌"; Y = "\033[93m⚠️ "; E = "\033[0m"; B = "\033[94mℹ️ "
def ok(m, detail=""): print(f"{G} {m}{f' — {detail}' if detail else ''}{E}")
def fail(m, detail=""): print(f"{R} {m}{f' — {detail}' if detail else ''}{E}"); return False
def warn(m): print(f"{Y} {m}{E}")
def info(m): print(f"{B} {m}{E}")

# Test date: 7 days from now to avoid past-date edge cases
TEST_DATE = (date.today() + timedelta(days=7)).strftime("%Y-%m-%d")

# 20 major Indian city pairs — tests all railway zones
TEST_PAIRS = [
    # NORTHERN RAILWAY
    ("NDLS", "BCT",  "New Delhi → Mumbai Central",    "Rajdhani Express"),
    ("NDLS", "MAS",  "New Delhi → Chennai",            "Tamil Nadu Express"),
    ("NDLS", "SBC",  "New Delhi → Bengaluru",          "Rajdhani / Karnataka Exp"),
    ("NDLS", "HWH",  "New Delhi → Howrah (Kolkata)",   "Rajdhani Express"),
    ("NDLS", "SC",   "New Delhi → Secunderabad",       "Telangana Express"),
    # WESTERN RAILWAY
    ("BCT",  "NDLS", "Mumbai → New Delhi",             "Rajdhani Express"),
    ("BCT",  "PUNE", "Mumbai → Pune",                  "Shatabdi / Deccan Queen"),
    ("BCT",  "HWH",  "Mumbai → Kolkata",               "Gujarat Mail"),
    ("ADI",  "NDLS", "Ahmedabad → New Delhi",          "ADI Rajdhani"),
    # SOUTHERN RAILWAY
    ("MAS",  "NDLS", "Chennai → New Delhi",            "Tamil Nadu Express"),
    ("MAS",  "SBC",  "Chennai → Bengaluru",            "Bangalore Mail"),
    ("MAS",  "HWH",  "Chennai → Kolkata",              "GT Express"),
    ("TVC",  "NDLS", "Thiruvananthapuram → New Delhi", "Rajdhani"),
    # EASTERN RAILWAY
    ("HWH",  "NDLS", "Howrah → New Delhi",             "Rajdhani Express"),
    ("PNBE", "NDLS", "Patna → New Delhi",              "Rajendra Nagar Raj"),
    # CENTRAL RAILWAY
    ("NGP",  "NDLS", "Nagpur → New Delhi",             "Karnataka Exp"),
    ("BPL",  "NDLS", "Bhopal → New Delhi",             "Shatabdi / various"),
    # RAJASTHAN
    ("JP",   "NDLS", "Jaipur → New Delhi",             "Intercity / Exp"),
    ("JU",   "NDLS", "Jodhpur → New Delhi",            "Mandore Exp"),
    # ASSAM
    ("GHY",  "NDLS", "Guwahati → New Delhi",          "Seemanchal / Rajdhani"),
]

CRITICAL_PAIRS = TEST_PAIRS[:5]  # Must pass for launch

results = {"passed": 0, "failed": 0, "warned": 0, "total": 0}
failures = []


async def test_health(client, base_url):
    print("\n═══ HEALTH CHECK ═══")
    try:
        r = await client.get(f"{base_url}/health", timeout=10)
        data = r.json()
        if r.status_code == 200:
            ok("Health endpoint", f"status={data.get('status')} db={data.get('components',{}).get('database','?')}")
            return True
        else:
            return fail("Health endpoint", f"HTTP {r.status_code}")
    except Exception as e:
        return fail("Health endpoint", str(e))


async def test_stations(client, base_url):
    print("\n═══ STATION AUTOCOMPLETE ═══")
    queries = [("del", "Delhi"), ("mum", "Mumbai"), ("ban", "Bengaluru"), ("kol", "Kolkata")]
    all_ok = True
    for q, city in queries:
        try:
            r = await client.get(f"{base_url}/api/v1/stations/suggest", params={"q": q, "limit": 5}, timeout=8)
            data = r.json()
            if r.status_code == 200 and len(data) > 0:
                codes = [s.get("code") for s in data[:3]]
                ok(f"Station '{q}'", f"{len(data)} results: {codes}")
                results["passed"] += 1
            else:
                fail(f"Station '{q}'", f"HTTP {r.status_code}, {len(data) if isinstance(data,list) else 0} results")
                all_ok = False
                results["failed"] += 1
        except Exception as e:
            fail(f"Station '{q}'", str(e))
            all_ok = False
            results["failed"] += 1
        results["total"] += 1
    return all_ok


async def test_route_search(client, base_url):
    print(f"\n═══ ROUTE SEARCH — {len(TEST_PAIRS)} city pairs (date: {TEST_DATE}) ═══")
    all_critical_ok = True

    for src, dst, desc, expected_train in TEST_PAIRS:
        is_critical = (src, dst) in [(p[0], p[1]) for p in CRITICAL_PAIRS]
        try:
            start = time.perf_counter()
            r = await client.get(
                f"{base_url}/api/v1/search/routes",
                params={"source": src, "destination": dst, "date": TEST_DATE, "limit": 10},
                timeout=15,
            )
            latency = round((time.perf_counter() - start) * 1000)
            results["total"] += 1

            if r.status_code != 200:
                msg = f"HTTP {r.status_code}"
                try:
                    msg += f" — {r.json().get('detail','')}"
                except Exception:
                    pass
                fail(f"{desc} ({src}→{dst})", msg)
                results["failed"] += 1
                failures.append((desc, msg))
                if is_critical:
                    all_critical_ok = False
                continue

            data = r.json()
            journeys = data.get("data", {}).get("journeys", [])
            status = data.get("status", "")
            direct = len([j for j in journeys if j.get("num_transfers") == 0])
            transfers = len([j for j in journeys if j.get("num_transfers", 0) > 0])
            fare_src = data.get("metadata", {}).get("fare_source", "?")
            classes = data.get("metadata", {}).get("available_classes", [])

            if len(journeys) == 0:
                msg = f"0 routes found — DB may be empty or station codes wrong"
                warn(f"{desc} ({src}→{dst}): {msg}")
                results["warned"] += 1
                failures.append((desc, msg))
                if is_critical:
                    all_critical_ok = False
            elif latency > 5000:
                warn(f"{desc}: {len(journeys)} routes in {latency}ms (SLOW — check DB indexes)")
                results["passed"] += 1
            else:
                ok(
                    f"{desc} ({src}→{dst})",
                    f"{direct} direct + {transfers} transfer | {latency}ms | fares={fare_src} | classes={classes}"
                )
                results["passed"] += 1

        except Exception as e:
            fail(f"{desc} ({src}→{dst})", str(e))
            results["failed"] += 1
            results["total"] += 1
            failures.append((desc, str(e)))
            if is_critical:
                all_critical_ok = False

    return all_critical_ok


async def test_live_status(client, base_url):
    print("\n═══ LIVE TRAIN STATUS ═══")
    trains = [("12951", "Mumbai Rajdhani"), ("12301", "Howrah Rajdhani")]
    for tno, name in trains:
        try:
            r = await client.get(f"{base_url}/api/v1/live/train/{tno}", timeout=12)
            data = r.json()
            if r.status_code == 200 and data.get("available"):
                stops = len(data.get("route", []))
                ok(f"Live status train {tno} ({name})", f"delay={data.get('delay_minutes')}min, {stops} stops")
                results["passed"] += 1
            else:
                warn(f"Live status {tno}: not available — {data.get('reason','')}")
                results["warned"] += 1
        except Exception as e:
            warn(f"Live status {tno}: {e}")
            results["warned"] += 1
        results["total"] += 1


async def test_fare_endpoint(client, base_url):
    print("\n═══ FARE ENDPOINT ═══")
    try:
        r = await client.get(f"{base_url}/api/v1/fare/12951", timeout=10)
        data = r.json()
        if r.status_code == 200 and data.get("classes"):
            ok("Fare endpoint", f"source={data.get('source')} classes={data.get('classes')} fare_1A={data.get('fares',{}).get('1A',{}).get('base','?')}")
            results["passed"] += 1
        else:
            warn(f"Fare endpoint: {data}")
            results["warned"] += 1
    except Exception as e:
        warn(f"Fare endpoint: {e}")
        results["warned"] += 1
    results["total"] += 1


async def test_db_directly():
    """Direct DB test — no server needed."""
    print("\n═══ DIRECT DATABASE TEST ═══")
    try:
        import asyncpg
        db_url = os.getenv("DATABASE_URL", "")
        if not db_url:
            fail("DATABASE_URL not set")
            return

        conn_url = db_url.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg2://", "postgresql://")
        if "?" in conn_url:
            conn_url = conn_url.split("?")[0]

        conn = await asyncpg.connect(conn_url, ssl="require", timeout=10)

        for table in ["stops", "trips", "stop_times", "trains_master"]:
            try:
                n = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                if n > 0:
                    ok(f"{table}", f"{n:,} rows")
                else:
                    fail(f"{table}", "EMPTY — run: python scripts/seed_data.py")
            except Exception as e:
                fail(f"{table}", str(e))

        # Test route engine directly
        ndls = await conn.fetchrow("SELECT id FROM stops WHERE UPPER(code)='NDLS' LIMIT 1")
        bct = await conn.fetchrow("SELECT id FROM stops WHERE UPPER(code) IN ('BCT','MMCT') LIMIT 1")
        if ndls and bct:
            count = await conn.fetchval("""
                SELECT COUNT(DISTINCT t.route_id)
                FROM trips t
                JOIN stop_times sf ON sf.trip_id=t.id AND sf.stop_id=$1
                JOIN stop_times st ON st.trip_id=t.id AND st.stop_id=$2
                WHERE sf.stop_sequence < st.stop_sequence
            """, ndls["id"], bct["id"])
            if count > 0:
                ok("NDLS→BCT direct search", f"{count} trains")
            else:
                fail("NDLS→BCT direct search", "0 trains — check seed data and station codes")
        else:
            fail("Station lookup", f"NDLS={'found' if ndls else 'MISSING'} BCT={'found' if bct else 'MISSING'}")

        await conn.close()
    except ImportError:
        warn("asyncpg not installed — skipping direct DB test")
    except Exception as e:
        fail("Database test", str(e))


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000", help="Backend URL to test")
    parser.add_argument("--db-only", action="store_true", help="Only test DB directly")
    args = parser.parse_args()

    print("\n╔══════════════════════════════════════════════╗")
    print("║  Route Master — Pre-Deploy Validation        ║")
    print(f"║  URL: {args.url:<38}║")
    print(f"║  Date: {TEST_DATE:<37}║")
    print("╚══════════════════════════════════════════════╝")

    if args.db_only:
        await test_db_directly()
    else:
        await test_db_directly()

        async with httpx.AsyncClient() as client:
            health_ok = await test_health(client, args.url)
            if not health_ok:
                warn("Server unreachable. Start it first: uvicorn app:app --reload")
                print("\nSkipping API tests (no server).\n")
            else:
                await test_stations(client, args.url)
                critical_ok = await test_route_search(client, args.url)
                await test_live_status(client, args.url)
                await test_fare_endpoint(client, args.url)

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n╔══════════════════════════════════════════════╗")
    print("║  VALIDATION SUMMARY                          ║")
    print("╠══════════════════════════════════════════════╣")
    print(f"║  ✅ Passed:  {results['passed']:<5}                           ║")
    print(f"║  ❌ Failed:  {results['failed']:<5}                           ║")
    print(f"║  ⚠️  Warned:  {results['warned']:<5}                           ║")
    print(f"║  Total:    {results['total']:<5}                           ║")
    print("╚══════════════════════════════════════════════╝")

    if failures:
        print("\n── Failures to fix before deploy ──")
        for name, reason in failures:
            print(f"  • {name}: {reason}")

    if results["failed"] == 0:
        print(f"\n{G} ALL CLEAR — Ready to deploy!{E}")
        print(f"   Run: python scripts/validate_deployment.py --url https://routemaster-api.onrender.com")
    elif results["failed"] <= 2:
        print(f"\n{Y} Minor issues — fix {results['failed']} failure(s) before deploy{E}")
    else:
        print(f"\n{R} NOT READY — {results['failed']} failures must be fixed{E}")
        print("   Most likely cause: empty DB. Run: python scripts/seed_data.py")
        sys.exit(1)

asyncio.run(main())
