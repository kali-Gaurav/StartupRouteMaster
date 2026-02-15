import re
from datetime import datetime

TIME_PATTERNS = ["%H:%M", "%I:%M %p", "%H.%M"]


def _try_parse_time(s: str):
    if not s:
        return None
    s = s.strip()
    if s in ("--", "Arr", "Dep", "Source", "Destination"):
        return None
    # normalize common variants
    s = s.replace('.', ':')
    s = re.sub(r"\s+(AM|PM|am|pm)$", lambda m: m.group(0).upper(), s)
    for p in TIME_PATTERNS:
        try:
            dt = datetime.strptime(s, p)
            return dt.strftime("%H:%M")
        except Exception:
            continue
    # if looks like HHMM
    m = re.match(r"^(\d{3,4})$", s)
    if m:
        t = m.group(1)
        if len(t) == 3:
            hh = int(t[0])
            mm = int(t[1:])
        else:
            hh = int(t[:2])
            mm = int(t[2:])
        try:
            return f"{hh:02d}:{mm:02d}"
        except Exception:
            return None
    return None


def normalize_station_name(name: str):
    if not name:
        return None
    name = name.strip()
    # collapse multiple spaces
    name = re.sub(r"\s+", " ", name)
    # standard representation: UPPER
    return name.upper()


def parse_distance_km(val: str):
    if val is None:
        return None
    try:
        v = str(val).strip().lower().replace('km', '').strip()
        if v == '':
            return None
        return float(v)
    except Exception:
        return None


def to_int(v):
    try:
        if v is None:
            return None
        return int(str(v).strip())
    except Exception:
        return None


def clean_station_row(row: dict, seq_hint: int = None):
    """Cleans one station row extracted from NTES schedule."""
    out = {}
    out['sequence'] = to_int(row.get('sequence')) or seq_hint
    out['station_code'] = (row.get('station_code') or row.get('code') or row.get('station') or '').strip().upper() or None
    out['station_name'] = normalize_station_name(row.get('station_name') or row.get('name'))
    out['day'] = to_int(row.get('day'))
    out['arrival'] = _try_parse_time(row.get('arrival'))
    out['departure'] = _try_parse_time(row.get('departure'))
    out['halt_minutes'] = to_int(row.get('halt') or row.get('halt_minutes'))
    out['distance_km'] = parse_distance_km(row.get('distance'))
    out['platform'] = row.get('platform')
    return out


def clean_schedule(schedule_obj: dict):
    """Normalize entire schedule object and validate sequences."""
    if not schedule_obj or 'schedule' not in schedule_obj:
        return schedule_obj

    stations = schedule_obj.get('schedule') or []
    cleaned = []
    for i, s in enumerate(stations, start=1):
        cleaned.append(clean_station_row(s, seq_hint=i))

    # ensure no duplicate sequence numbers; if duplicates, rebuild sequentially
    seqs = [s.get('sequence') for s in cleaned]
    if len(set(seqs)) != len(seqs) or None in seqs:
        for idx, s in enumerate(cleaned, start=1):
            s['sequence'] = idx

    # validate arrival <= departure when both present (best-effort)
    for s in cleaned:
        arr = s.get('arrival')
        dep = s.get('departure')
        if arr and dep:
            try:
                at = datetime.strptime(arr, "%H:%M")
                dt = datetime.strptime(dep, "%H:%M")
                if at > dt:
                    # swap if obviously inverted
                    s['arrival'], s['departure'] = s['departure'], s['arrival']
            except Exception:
                pass

    schedule_obj['schedule'] = cleaned
    # normalize train-level metadata
    schedule_obj['train_no'] = str(schedule_obj.get('train_no') or schedule_obj.get('train_number') or '').strip()
    schedule_obj['name'] = schedule_obj.get('name') or schedule_obj.get('train_name')
    schedule_obj['source'] = normalize_station_name(schedule_obj.get('source'))
    schedule_obj['destination'] = normalize_station_name(schedule_obj.get('destination'))
    return schedule_obj


def clean_live_status(live_obj: dict):
    if not live_obj:
        return live_obj
    out = {}
    out['train_number'] = live_obj.get('train_no') or live_obj.get('train_number')
    out['current_station'] = normalize_station_name(live_obj.get('current_station'))
    # parse delay minutes if string contains digits
    delay_raw = live_obj.get('delay')
    delay = None
    if isinstance(delay_raw, (int, float)):
        delay = int(delay_raw)
    elif isinstance(delay_raw, str):
        m = re.search(r"(\d+)", delay_raw)
        if m:
            delay = int(m.group(1))
    out['delay_minutes'] = delay or 0
    out['status'] = live_obj.get('status') or ('Delayed' if out['delay_minutes'] > 0 else 'On Time')
    out['next_station'] = normalize_station_name(live_obj.get('next_station'))
    out['eta_next'] = _try_parse_time(live_obj.get('eta_next'))
    out['timestamp'] = live_obj.get('timestamp') or datetime.utcnow().isoformat()
    return out