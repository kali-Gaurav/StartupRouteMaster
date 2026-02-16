import os
import json
from datetime import datetime, timedelta
from pathlib import Path

from routemaster_agent.intelligence import selector_registry
from routemaster_agent import metrics


def _write_registry(path: Path, entry: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'ntes_schedule': entry}, indent=2), encoding='utf-8')


def test_threshold_boundary_no_promotion_on_equal(tmp_path):
    # failure_rate == PROMOTION_FAILURE_RATE_THRESHOLD (0.15) should NOT promote (strict >)
    reg_path = tmp_path / 'selector_registry.json'
    primary = {'selector': 'primary.sel', 'score': 0.1, 'success_count': 85, 'failure_count': 15, 'last_tested': datetime.utcnow().isoformat()}
    backups = [{'selector': 'backup.good', 'score': 0.95, 'success_count': 20, 'failure_count': 0, 'last_tested': datetime.utcnow().isoformat()}]
    entry = {'primary': primary, 'backups': backups, 'semantic_fallback': True, 'last_updated': datetime.utcnow().isoformat(), 'last_promotion_timestamp': None, 'promotion_cooldown_until': None}
    _write_registry(reg_path, entry)

    os.environ['RMA_SELECTOR_REGISTRY'] = str(reg_path)

    # equal to threshold -> no promotion
    assert selector_registry.evaluate_promotion('ntes_schedule') is False

    # nudge failure rate slightly above threshold and promotion should occur
    reg = selector_registry.list_registry(reg_path)
    reg_entry = reg['ntes_schedule']
    reg_entry['primary']['failure_count'] = 16
    selector_registry._save({'ntes_schedule': reg_entry}, reg_path)

    assert selector_registry.evaluate_promotion('ntes_schedule') is True

    del os.environ['RMA_SELECTOR_REGISTRY']


def test_backup_min_sample_guard(tmp_path):
    reg_path = tmp_path / 'selector_registry.json'
    primary = {'selector': 'primary.sel', 'score': 0.1, 'success_count': 10, 'failure_count': 5, 'last_tested': datetime.utcnow().isoformat()}
    # backup has perfect success but too few samples (3 < 20)
    backups = [{'selector': 'backup.small', 'score': 0.99, 'success_count': 3, 'failure_count': 0, 'last_tested': datetime.utcnow().isoformat()}]
    entry = {'primary': primary, 'backups': backups, 'semantic_fallback': True, 'last_updated': datetime.utcnow().isoformat(), 'last_promotion_timestamp': None, 'promotion_cooldown_until': None}
    _write_registry(reg_path, entry)

    os.environ['RMA_SELECTOR_REGISTRY'] = str(reg_path)

    # primary failure rate > threshold, but backup sample size below PROMOTION_BACKUP_MIN_SAMPLES
    assert selector_registry.evaluate_promotion('ntes_schedule') is False

    # increase backup sample size to meet minimum -> should promote
    reg = selector_registry.list_registry(reg_path)
    reg_entry = reg['ntes_schedule']
    reg_entry['backups'][0]['success_count'] = 25
    selector_registry._save({'ntes_schedule': reg_entry}, reg_path)

    assert selector_registry.evaluate_promotion('ntes_schedule') is True

    del os.environ['RMA_SELECTOR_REGISTRY']


def test_cooldown_expiry_allows_promotion(tmp_path):
    reg_path = tmp_path / 'selector_registry.json'
    primary = {'selector': 'primary.sel', 'score': 0.1, 'success_count': 5, 'failure_count': 10, 'last_tested': datetime.utcnow().isoformat()}
    backups = [{'selector': 'backup.good', 'score': 0.9, 'success_count': 30, 'failure_count': 0, 'last_tested': datetime.utcnow().isoformat()}]
    # set a cooldown in the past to simulate expiry
    entry = {'primary': primary, 'backups': backups, 'semantic_fallback': True, 'last_updated': datetime.utcnow().isoformat(), 'last_promotion_timestamp': None, 'promotion_cooldown_until': (datetime.utcnow() - timedelta(hours=1)).isoformat()}
    _write_registry(reg_path, entry)

    os.environ['RMA_SELECTOR_REGISTRY'] = str(reg_path)

    assert selector_registry.evaluate_promotion('ntes_schedule') is True

    del os.environ['RMA_SELECTOR_REGISTRY']


def test_promotion_increments_metric_and_creates_backup(tmp_path):
    reg_path = tmp_path / 'selector_registry.json'
    primary = {'selector': 'primary.sel', 'score': 0.1, 'success_count': 1, 'failure_count': 10, 'last_tested': datetime.utcnow().isoformat()}
    backups = [{'selector': 'backup.good', 'score': 0.95, 'success_count': 30, 'failure_count': 0, 'last_tested': datetime.utcnow().isoformat()}]
    entry = {'primary': primary, 'backups': backups, 'semantic_fallback': True, 'last_updated': datetime.utcnow().isoformat(), 'last_promotion_timestamp': None, 'promotion_cooldown_until': None}
    _write_registry(reg_path, entry)

    os.environ['RMA_SELECTOR_REGISTRY'] = str(reg_path)

    # capture metric before promotion
    before = metrics.RMA_SELECTOR_PROMOTIONS_TOTAL.labels(page_type='ntes_schedule')._value.get()

    promoted = selector_registry.evaluate_promotion('ntes_schedule')
    assert promoted is True

    # metric incremented
    after = metrics.RMA_SELECTOR_PROMOTIONS_TOTAL.labels(page_type='ntes_schedule')._value.get()
    assert after == before + 1

    # registry backup file exists in same directory
    backups = list(reg_path.parent.glob('selector_registry_backup_*.json'))
    assert len(backups) >= 1

    del os.environ['RMA_SELECTOR_REGISTRY']
