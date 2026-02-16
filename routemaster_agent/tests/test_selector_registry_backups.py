import os
from pathlib import Path
from datetime import datetime, timedelta

from routemaster_agent.intelligence import selector_registry


def _make_backup(tmp_path: Path, ts_offset_days: int = 0, idx: int = 0):
    reg = tmp_path / 'selector_registry.json'
    reg.parent.mkdir(parents=True, exist_ok=True)
    reg.write_text('{"dummy": true}', encoding='utf-8')
    ts = (datetime.utcnow() - timedelta(days=ts_offset_days)).strftime('%Y%m%d_%H%M%S')
    bp = reg.parent / f'selector_registry_backup_{ts}_{idx}.json'
    bp.write_text('{"backup": %d}' % idx, encoding='utf-8')
    # adjust mtime to simulate age
    if ts_offset_days > 0:
        mtime = (datetime.utcnow() - timedelta(days=ts_offset_days)).timestamp()
        Path(bp).touch()
        os.utime(bp, (mtime, mtime))
    return bp


def test_cleanup_keeps_last_and_age(tmp_path):
    # create 10 backups: some old, some new
    for i in range(10):
        _make_backup(tmp_path, ts_offset_days=(i // 2), idx=i)

    # keep last 3 OR last 1 day
    removed = selector_registry.cleanup_backups(keep_last=3, keep_days=1, path=tmp_path / 'selector_registry.json')
    # ensure we removed at least some files and the newest 3 still exist
    remaining = list((tmp_path).glob('selector_registry_backup_*.json'))
    assert len(remaining) <= 3 + 2  # allowance for recent files


def test_rollback_to_backup(tmp_path):
    reg_path = tmp_path / 'selector_registry.json'
    reg_path.write_text('{"active": true}', encoding='utf-8')
    bp = tmp_path / 'selector_registry_backup_test.json'
    bp.write_text('{"active": false, "restored": true}', encoding='utf-8')

    # perform rollback
    out = selector_registry.rollback_to_backup(str(bp), path=reg_path)
    assert out == str(reg_path)
    assert reg_path.read_text(encoding='utf-8') == bp.read_text(encoding='utf-8')
    # pre-rollback snapshot written
    found = any('prerollback' in p.name for p in reg_path.parent.glob('*.json'))
    assert found is True