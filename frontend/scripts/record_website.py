"""CLI: Record real website demonstrations (NTES/IRCTC).

Usage:
  python scripts/record_website.py --site ntes --train-no 12345 --scene-id ntes_search_001
  python scripts/record_website.py --site irctc --origin JAIPUR --dest KOTA --date 18/02/2026 --scene-id irctc_search_001
"""
from __future__ import annotations
import argparse
import asyncio

from routemaster_agent.data.website_recorder import WebsiteRecorder


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--site", required=True, choices=["ntes", "irctc"], help="Which site to record")
    p.add_argument("--scene-id", required=True, help="Scene ID for this recording")
    p.add_argument("--base", default="datasets/raw_scenes", help="Base directory for output")

    # NTES-specific args
    p.add_argument("--train-no", help="Train number for NTES search")

    # IRCTC-specific args
    p.add_argument("--origin", help="Origin station for IRCTC search")
    p.add_argument("--dest", help="Destination station for IRCTC search")
    p.add_argument("--date", help="Journey date for IRCTC search (DD/MM/YYYY)")

    args = p.parse_args()

    recorder = WebsiteRecorder(base_dir=args.base)

    try:
        if args.site == "ntes":
            train_no = args.train_no or "12345"
            print(f"[RECORDING] NTES schedule lookup: train_no={train_no}")
            out = await recorder.record_ntes_schedule(args.scene_id, train_no=train_no)
            print(f"✅ Recorded: {out}")
        elif args.site == "irctc":
            origin = args.origin or "JAIPUR"
            dest = args.dest or "KOTA"
            date = args.date or "18/02/2026"
            print(f"[RECORDING] IRCTC search: {origin} → {dest} on {date}")
            out = await recorder.record_irctc_search(args.scene_id, origin, dest, date)
            print(f"✅ Recorded: {out}")
    except Exception as e:
        print(f"❌ Recording failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    asyncio.run(main())
