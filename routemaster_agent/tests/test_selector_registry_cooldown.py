import os
import json
from datetime import datetime
from pathlib import Path

from routemaster_agent.intelligence import selector_registry


def test_promotion_cooldown(tmp_path):
    reg_path = tmp_path / 'selector_registry.json'
    data = {
        'ntes_schedule': {
            'primary': {'selector': 'table.bad', 'score': 0.2, 'success_count': 5, 'failure_count': 2, 'last_tested': datetime.utcnow().isoformat()},
            'backups': [
                {'selector': 'table.good', 'score': 0.9, 'success_count': 30, 'failure_count': 1, 'last_tested': datetime.utcnow().isoformat()}
            ],
            'semantic_fallback': True,
            'last_updated': datetime.utcnow().isoformat(),
            'last_promotion_timestamp': None,
            'promotion_cooldown_until': None
        }
    }
    reg_path.write_text(json.dumps(data), encoding='utf-8')
    os.environ['RMA_SELECTOR_REGISTRY'] = str(reg_path)

    # trigger promotion (record_selector_result calls evaluate_promotion internally)
    for _ in range(10):
        selector_registry.record_selector_result('ntes_schedule', 'table.bad', False)

    # primary should have been promoted by the internal evaluation
    assert selector_registry.get_primary_selector('ntes_schedule') == 'table.good'

    # immediate re-evaluation should NOT promote again (cooldown active)
    promoted2 = selector_registry.evaluate_promotion('ntes_schedule')
    assert promoted2 is False

    del os.environ['RMA_SELECTOR_REGISTRY']
