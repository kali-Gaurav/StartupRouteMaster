"""
Schedule Drift Analyzer
Small utilities to compute schedule diffs and simple drift metrics (avg time shift, volatility).
"""
from typing import List, Dict


def compute_time_shift(old_schedule: List[Dict], new_schedule: List[Dict]) -> Dict:
    """Return average absolute time shift (minutes) per station present in both schedules.
    Expects schedule rows with 'station_code' and 'arrival'/'departure' as HH:MM strings.
    """
    def to_minutes(t: str):
        try:
            h, m = map(int, t.split(':'))
            return h * 60 + m
        except Exception:
            return None

    old_map = {r.get('station_code'): r for r in old_schedule or []}
    shifts = []
    for nr in new_schedule or []:
        code = nr.get('station_code')
        if not code or code not in old_map:
            continue
        old_r = old_map[code]
        old_arr = to_minutes(old_r.get('arrival') or old_r.get('departure') or '')
        new_arr = to_minutes(nr.get('arrival') or nr.get('departure') or '')
        if old_arr is not None and new_arr is not None:
            shifts.append(abs(new_arr - old_arr))
    avg_shift = sum(shifts) / len(shifts) if shifts else 0.0
    return {'avg_shift_minutes': round(avg_shift, 2), 'samples': len(shifts)}
