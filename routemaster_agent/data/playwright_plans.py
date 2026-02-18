"""Utilities: sample recording plan registry for pilot runs."""
from __future__ import annotations
from pathlib import Path
import os

# Locate the examples folder relative to workspace root
_workspace_root = Path(__file__).resolve().parents[2]
PLANS_DIR = _workspace_root / "examples"

NTES_SEARCH = str(PLANS_DIR / "ntes_schedule.json")
IRCTC_SEARCH = str(PLANS_DIR / "irctc_search.json")

# Fallback: create temp plans if examples don't exist
if not NTES_SEARCH or not Path(NTES_SEARCH).exists():
    import json
    temp_dir = _workspace_root / "examples"
    temp_dir.mkdir(exist_ok=True)
    
    ntes_plan = {
        "meta": {"site": "ntes", "job_type": "schedule", "url": "https://enquiry.indianrail.gov.in/mntes/", "task": {"train_number": "12345"}},
        "steps": [
            {"action": {"type": "input", "selector": "input[name='txtTrainNo']", "value": "12345"}},
            {"action": {"type": "click", "selector": "button:has-text('Search')"}}
        ]
    }
    Path(NTES_SEARCH).write_text(json.dumps(ntes_plan, indent=2))

if not IRCTC_SEARCH or not Path(IRCTC_SEARCH).exists():
    import json
    temp_dir = _workspace_root / "examples"
    temp_dir.mkdir(exist_ok=True)
    
    irctc_plan = {
        "meta": {"site": "irctc", "job_type": "search", "url": "https://www.irctc.co.in/nget/train-search", "task": {"origin": "JAIPUR", "dest": "KOTA"}},
        "steps": [
            {"action": {"type": "input", "selector": "input[placeholder='From']", "value": "Jaipur"}},
            {"action": {"type": "input", "selector": "input[placeholder='To']", "value": "Kota"}},
            {"action": {"type": "click", "selector": "button:has-text('Search Trains')"}}
        ]
    }
    Path(IRCTC_SEARCH).write_text(json.dumps(irctc_plan, indent=2))

ALL_PLANS = [NTES_SEARCH, IRCTC_SEARCH]
