import os
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from routemaster_agent.intelligence import selector_registry


def _with_temp_registry(tmp_path, func):
    env = os.environ.get('RMA_SELECTOR_REGISTRY')
    try:
        os.environ['RMA_SELECTOR_REGISTRY'] = str(tmp_path)
        yield func()
    finally:
        if env is not None:
            os.environ['RMA_SELECTOR_REGISTRY'] = env
        else:
            del os.environ['RMA_SELECTOR_REGISTRY']


def test_promotion_path(tmp_path):
    # use isolated registry path
    reg_path = tmp_path / 'selector_registry.json'
    # prepare registry with a weak primary and a strong backup
    data = {
        'ntes_schedule': {
            'primary': {'selector': 'table.bad', 'score': 0.2, 'success_count': 10, 'failure_count': 5, 'last_tested': datetime.utcnow().isoformat()},
            'backups': [
                {'selector': 'table.good', 'score': 0.9, 'success_count': 25, 'failure_count': 1, 'last_tested': datetime.utcnow().isoformat()}
            ],
            'semantic_fallback': True,
            'last_updated': datetime.utcnow().isoformat(),
            'last_promotion_timestamp': None,
            'promotion_cooldown_until': None
        }
    }
    reg_path.write_text(json.dumps(data), encoding='utf-8')

    os.environ['RMA_SELECTOR_REGISTRY'] = str(reg_path)
    # ensure registry module resolves to our temp path
    assert selector_registry._get_registry_path() == Path(str(reg_path))
    # ensure the on-disk registry contains our initial data
    raw_before = reg_path.read_text()
    assert 'table.bad' in raw_before and 'table.good' in raw_before

    # record additional primary failures to exceed threshold
    for _ in range(20):
        selector_registry.record_selector_result('ntes_schedule', 'table.bad', False)

    # after recording failures, the registry may have auto-promoted the backup
    raw_after = reg_path.read_text()
    assert 'table.bad' in raw_after

    reg2 = selector_registry.list_registry(Path(str(reg_path)))
    entry2 = reg2.get('ntes_schedule')

    # primary should now be the strong backup (promotion may have been performed)
    assert entry2['primary']['selector'] == 'table.good'

    # previous primary should appear in backups with elevated failure_count
    backups = entry2.get('backups', [])
    assert any(b.get('selector') == 'table.bad' and b.get('failure_count', 0) >= 20 for b in backups)

    # promotion log created in selector_registry module location
    log_path = selector_registry._get_promotion_log_path()
    assert log_path.exists()

    # cleanup env var and promotion log
    del os.environ['RMA_SELECTOR_REGISTRY']
    try:
        log_path.unlink()
    except Exception:
        pass
