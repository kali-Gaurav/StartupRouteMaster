import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from routemaster_agent.metrics import (
    RMA_SELECTOR_FALLBACK_TOTAL,
    RMA_SELECTOR_PRIMARY_FAILURES_TOTAL,
    RMA_SELECTOR_SEMANTIC_SUCCESS_TOTAL,
)

# additional metrics imported lazily to avoid circular imports
try:
    from routemaster_agent.metrics import (
        RMA_SELECTOR_PROMOTIONS_TOTAL,
        RMA_SELECTOR_FAILURE_RATE,
        RMA_SELECTOR_ACTIVE_PRIMARY,
    )
except Exception:
    RMA_SELECTOR_PROMOTIONS_TOTAL = None
    RMA_SELECTOR_FAILURE_RATE = None
    RMA_SELECTOR_ACTIVE_PRIMARY = None


def _get_registry_path() -> Path:
    return Path(os.getenv('RMA_SELECTOR_REGISTRY', Path(__file__).resolve().parents[1] / 'intelligence' / 'selector_registry.json'))


def _get_promotion_log_path() -> Path:
    return Path(os.getenv('RMA_SELECTOR_PROMOTION_LOG', Path(__file__).resolve().parents[1] / 'intelligence' / 'selector_promotion_log.json'))

# Promotion config
PROMOTION_FAILURE_RATE_THRESHOLD = float(os.getenv('RMA_SELECTOR_PROMOTION_FAILURE_RATE', '0.15'))
PROMOTION_BACKUP_SUCCESS_RATE = float(os.getenv('RMA_SELECTOR_PROMOTION_BACKUP_SUCCESS', '0.90'))
PROMOTION_BACKUP_MIN_SAMPLES = int(os.getenv('RMA_SELECTOR_PROMOTION_MIN_SAMPLES', '20'))
PROMOTION_COOLDOWN_HOURS = int(os.getenv('RMA_SELECTOR_PROMOTION_COOLDOWN_HOURS', '24'))


def _load(path: Optional[Path] = None) -> Dict[str, Any]:
    if path is None:
        path = _get_registry_path()
    if path.exists():
        try:
            return json.loads(path.read_text(encoding='utf-8') or '{}')
        except Exception:
            return {}
    return {}


def _save(reg: Dict[str, Any], path: Optional[Path] = None):
    if path is None:
        path = _get_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(reg, indent=2), encoding='utf-8')


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def get_entry(page_type: str) -> Dict[str, Any]:
    reg = _load()
    return reg.get(page_type, {})


def get_primary_selector(page_type: str) -> Optional[str]:
    entry = get_entry(page_type)
    primary = entry.get('primary') or {}
    return primary.get('selector')


def _ensure_entry(page_type: str):
    reg = _load()
    if page_type not in reg:
        reg[page_type] = {
            'primary': {'selector': None, 'score': 0.0, 'success_count': 0, 'failure_count': 0, 'last_tested': None},
            'backups': [],
            'semantic_fallback': True,
            'last_updated': _now_iso(),
            'last_promotion_timestamp': None,
            'promotion_cooldown_until': None,
        }
        _save(reg)
    return reg[page_type]


def record_selector_result(page_type: str, selector: str, success: bool):
    """Record a runtime result for a selector. If selector matches primary, update primary counters; if matches a backup update backup counters.
    This also triggers promotion evaluation.
    """
    reg = _load()
    entry = reg.get(page_type)
    if not entry:
        entry = _ensure_entry(page_type)
        reg = _load()
        entry = reg[page_type]

    primary = entry.get('primary', {})
    updated = False
    if primary.get('selector') == selector:
        if success:
            primary['success_count'] = primary.get('success_count', 0) + 1
        else:
            primary['failure_count'] = primary.get('failure_count', 0) + 1
        primary['last_tested'] = _now_iso()
        entry['primary'] = primary
        updated = True
    else:
        # try to find a matching backup
        for b in entry.get('backups', []):
            if b.get('selector') == selector:
                if success:
                    b['success_count'] = b.get('success_count', 0) + 1
                else:
                    b['failure_count'] = b.get('failure_count', 0) + 1
                b['last_tested'] = _now_iso()
                updated = True
                break
        if not updated:
            # unknown selector -> add as backup with one sample
            newb = {'selector': selector, 'score': None, 'success_count': 1 if success else 0, 'failure_count': 0 if success else 1, 'last_tested': _now_iso()}
            entry.setdefault('backups', []).append(newb)
            updated = True

    entry['last_updated'] = _now_iso()
    reg[page_type] = entry
    _save(reg)

    # update selector failure rate metric for page_type
    try:
        if RMA_SELECTOR_FAILURE_RATE is not None:
            p = entry.get('primary', {})
            succ = p.get('success_count', 0)
            fail = p.get('failure_count', 0)
            total = succ + fail
            rate = (fail / total) if total else 0.0
            RMA_SELECTOR_FAILURE_RATE.labels(page_type=page_type).set(round(rate, 4))
    except Exception:
        pass

    # evaluate promotion after recording
    try:
        evaluate_promotion(page_type)
    except Exception:
        pass


def register_candidate_test(page_type: str, selector: str, score: float, success: bool):
    """Called by TestRunner to record test results (adds/updates backup statistics)."""
    reg = _load()
    entry = reg.get(page_type) or _ensure_entry(page_type)
    found = False
    for b in entry.get('backups', []):
        if b.get('selector') == selector:
            b['score'] = score
            if success:
                b['success_count'] = b.get('success_count', 0) + 1
            else:
                b['failure_count'] = b.get('failure_count', 0) + 1
            b['last_tested'] = _now_iso()
            found = True
            break
    if not found:
        entry.setdefault('backups', []).append({'selector': selector, 'score': score, 'success_count': 1 if success else 0, 'failure_count': 0 if success else 1, 'last_tested': _now_iso()})
    entry['last_updated'] = _now_iso()
    reg[page_type] = entry
    _save(reg)

    # update failure metric and consider promotion
    try:
        if RMA_SELECTOR_FAILURE_RATE is not None:
            p = entry.get('primary', {})
            succ = p.get('success_count', 0)
            fail = p.get('failure_count', 0)
            total = succ + fail
            rate = (fail / total) if total else 0.0
            RMA_SELECTOR_FAILURE_RATE.labels(page_type=page_type).set(round(rate, 4))
    except Exception:
        pass
    try:
        evaluate_promotion(page_type)
    except Exception:
        pass


def evaluate_promotion(page_type: str):
    """Check promotion rules and promote a backup to primary when conditions met."""
    reg = _load()
    entry = reg.get(page_type)
    if not entry:
        return False

    # cooldown check
    cooldown_until = entry.get('promotion_cooldown_until')
    if cooldown_until:
        try:
            if datetime.fromisoformat(cooldown_until) > datetime.utcnow():
                return False
        except Exception:
            pass

    primary = entry.get('primary', {})
    p_succ = primary.get('success_count', 0)
    p_fail = primary.get('failure_count', 0)
    p_total = p_succ + p_fail
    p_failure_rate = (p_fail / p_total) if p_total else 0.0

    # find best backup by success_rate
    best_backup = None
    for b in entry.get('backups', []):
        b_succ = b.get('success_count', 0)
        b_fail = b.get('failure_count', 0)
        b_total = b_succ + b_fail
        b_success_rate = (b_succ / b_total) if b_total else 0.0
        # require minimum samples
        if b_total >= PROMOTION_BACKUP_MIN_SAMPLES and b_success_rate >= PROMOTION_BACKUP_SUCCESS_RATE:
            if not best_backup or b_success_rate > ((best_backup.get('success_count', 0) / (best_backup.get('success_count', 0) + best_backup.get('failure_count', 0))) if (best_backup.get('success_count', 0) + best_backup.get('failure_count', 0)) else 0):
                best_backup = b

    if p_failure_rate > PROMOTION_FAILURE_RATE_THRESHOLD and best_backup:
        # create an on-disk snapshot of the registry before performing the promotion
        try:
            reg_path = _get_registry_path()
            if reg_path.exists():
                ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                backup_path = reg_path.parent / f"selector_registry_backup_{ts}.json"
                try:
                    backup_path.write_text(reg_path.read_text(encoding='utf-8'), encoding='utf-8')
                except Exception:
                    # best-effort; continue even if backup fails
                    pass
        except Exception:
            pass

        # perform promotion: move best_backup -> primary, old primary -> backups
        old_primary = primary.copy()
        new_primary = {
            'selector': best_backup.get('selector'),
            'score': best_backup.get('score') or 0.0,
            'success_count': 0,  # reset counters after promotion
            'failure_count': 0,
            'last_tested': _now_iso()
        }
        # remove best_backup from backups
        backups = [b for b in entry.get('backups', []) if b.get('selector') != best_backup.get('selector')]
        # add old_primary to backups (preserve its counters)
        backups.insert(0, old_primary)
        entry['primary'] = new_primary
        entry['backups'] = backups
        entry['last_promotion_timestamp'] = _now_iso()
        entry['promotion_cooldown_until'] = (datetime.utcnow() + timedelta(hours=PROMOTION_COOLDOWN_HOURS)).isoformat()
        entry['last_updated'] = _now_iso()
        reg[page_type] = entry
        _save(reg)

        # log promotion event
        try:
            log_path = _get_promotion_log_path()
            log_path.parent.mkdir(parents=True, exist_ok=True)
            ev = {
                'page_type': page_type,
                'old_primary': old_primary.get('selector'),
                'new_primary': new_primary.get('selector'),
                'timestamp': _now_iso(),
                'primary_failure_rate': p_failure_rate,
                'backup_sample_size': best_backup.get('success_count', 0) + best_backup.get('failure_count', 0)
            }
            try:
                existing = json.loads(log_path.read_text(encoding='utf-8') or '[]')
            except Exception:
                existing = []
            existing.append(ev)
            log_path.write_text(json.dumps(existing, indent=2), encoding='utf-8')
        except Exception:
            pass

        # update metrics
        try:
            if RMA_SELECTOR_PROMOTIONS_TOTAL is not None:
                RMA_SELECTOR_PROMOTIONS_TOTAL.labels(page_type=page_type).inc()
            if RMA_SELECTOR_ACTIVE_PRIMARY is not None:
                # set gauge for active primary
                RMA_SELECTOR_ACTIVE_PRIMARY.labels(page_type=page_type, selector=new_primary.get('selector')).set(1)
        except Exception:
            pass

        return True

    return False


def list_registry(path: Optional[Path] = None) -> Dict[str, Any]:
    return _load(path or _get_registry_path())


# Backup / retention / rollback utilities
def _find_backup_files(reg_path: Optional[Path] = None):
    path = reg_path or _get_registry_path()
    parent = path.parent
    pattern = "selector_registry_backup_*.json"
    files = sorted(parent.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files


def cleanup_backups(keep_last: int = 50, keep_days: int = 14, path: Optional[Path] = None):
    """Delete old selector_registry backup files, keeping the newest `keep_last` or any within `keep_days` days."""
    files = _find_backup_files(path)
    keep_cutoff = None
    try:
        from datetime import datetime, timedelta
        keep_cutoff = datetime.utcnow() - timedelta(days=int(keep_days))
    except Exception:
        keep_cutoff = None

    removed = []
    for idx, f in enumerate(files):
        keep_by_count = idx < int(keep_last)
        keep_by_age = False
        if keep_cutoff is not None:
            try:
                mtime = __import__('datetime').datetime.utcfromtimestamp(f.stat().st_mtime)
                keep_by_age = mtime >= keep_cutoff
            except Exception:
                keep_by_age = False
        if not (keep_by_count or keep_by_age):
            try:
                f.unlink()
                removed.append(str(f))
            except Exception:
                pass
    return removed


def rollback_to_backup(backup_path: str, path: Optional[Path] = None):
    """Rollback the active registry to a selected backup file.

    - Creates a pre-rollback snapshot (selector_registry_prerollback_YYYYMMDD_HHMMSS.json)
    - Overwrites the active registry with the backup contents
    - Returns the path to the written registry file
    """
    reg_path = path or _get_registry_path()
    b = Path(backup_path)
    if not b.exists():
        raise FileNotFoundError(f"backup not found: {backup_path}")

    # create pre-rollback snapshot
    try:
        ts = __import__('datetime').datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        pre_path = reg_path.parent / f"selector_registry_prerollback_{ts}.json"
        if reg_path.exists():
            pre_path.write_text(reg_path.read_text(encoding='utf-8'), encoding='utf-8')
    except Exception:
        pass

    # perform rollback (copy backup into registry path)
    try:
        content = b.read_text(encoding='utf-8')
        reg_path.write_text(content, encoding='utf-8')
    except Exception as e:
        raise

    return str(reg_path)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Selector registry utilities (list/cleanup/rollback)')
    parser.add_argument('--list-backups', action='store_true', help='List available registry backups')
    parser.add_argument('--cleanup', action='store_true', help='Run backup retention cleanup')
    parser.add_argument('--keep-last', type=int, default=50, help='Number of newest backups to keep')
    parser.add_argument('--keep-days', type=int, default=14, help='Number of days to keep backups')
    parser.add_argument('--rollback', type=str, help='Rollback registry from specified backup file path')
    args = parser.parse_args()

    if args.list_backups:
        for p in _find_backup_files():
            print(p)
        raise SystemExit(0)

    if args.cleanup:
        removed = cleanup_backups(keep_last=args.keep_last, keep_days=args.keep_days)
        for p in removed:
            print('removed', p)
        raise SystemExit(0)

    if args.rollback:
        path = rollback_to_backup(args.rollback)
        print('rolled back to', path)
        raise SystemExit(0)

    parser.print_help()
