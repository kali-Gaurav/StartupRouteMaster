from typing import Dict, Any, List
from routemaster_agent.database.db import SessionLocal
from routemaster_agent.database.models import TrainStation, ScheduleChangeLog
from datetime import datetime


def _station_key(s: Dict[str, Any]) -> str:
    return f"{s.get('sequence')}|{s.get('station_code') or ''}".upper()


def compare_schedule_to_db(schedule_obj: Dict[str, Any]) -> Dict[str, Any]:
    """Compare extracted schedule_obj against DB train_stations and return a diff.
    Diff includes: added_stations, removed_stations, changed_times, sequence_gaps, station_count_delta
    """
    train_no = schedule_obj.get('train_no') or schedule_obj.get('train_number')
    extracted = schedule_obj.get('schedule') or []

    session = SessionLocal()
    try:
        db_rows = session.query(TrainStation).filter(TrainStation.train_number == train_no).order_by(TrainStation.sequence).all()
        db_list = [
            {
                'sequence': r.sequence,
                'station_code': (r.station_code or '').upper(),
                'arrival': r.arrival,
                'departure': r.departure,
            }
            for r in db_rows
        ]
    finally:
        session.close()

    extracted_keys = {_station_key(s): s for s in extracted}
    db_keys = {_station_key(s): s for s in db_list}

    added = []
    removed = []
    changed = []

    # detect added and changed
    for k, s in extracted_keys.items():
        if k not in db_keys:
            added.append(s)
        else:
            dbs = db_keys[k]
            # compare arrival/departure - treat None/empty as equal
            if (str(s.get('arrival') or '') != str(dbs.get('arrival') or '')) or (str(s.get('departure') or '') != str(dbs.get('departure') or '')):
                changed.append({'sequence': s.get('sequence'), 'station_code': s.get('station_code'), 'old': dbs, 'new': s})

    # detect removed
    for k, s in db_keys.items():
        if k not in extracted_keys:
            removed.append(s)

    seqs = [int(s.get('sequence')) for s in extracted if s.get('sequence') is not None]
    sequence_gaps = []
    if seqs:
        expected = list(range(1, max(seqs) + 1))
        missing = [x for x in expected if x not in seqs]
        if missing:
            sequence_gaps = missing

    diff = {
        'train_number': train_no,
        'timestamp': datetime.utcnow().isoformat(),
        'added_stations': added,
        'removed_stations': removed,
        'changed_stations': changed,
        'sequence_gaps': sequence_gaps,
        'db_count': len(db_list),
        'extracted_count': len(extracted),
    }

    return diff


def log_change_if_any(schedule_obj: Dict[str, Any]) -> Dict[str, Any]:
    diff = compare_schedule_to_db(schedule_obj)
    # persist only when there is meaningful change
    meaningful = bool(diff['added_stations'] or diff['removed_stations'] or diff['changed_stations'] or diff['sequence_gaps'])
    if meaningful:
        session = SessionLocal()
        try:
            entry = ScheduleChangeLog(
                train_number=diff['train_number'],
                detected_at=datetime.utcnow(),
                diff=diff,
                resolved=False,
            )
            session.add(entry)
            session.commit()
            session.refresh(entry)
            diff['logged_id'] = entry.id
        finally:
            session.close()
    else:
        diff['logged_id'] = None
    return diff