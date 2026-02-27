import pytest
from core.validator.validation_manager import (
    create_validation_manager_with_defaults,
    ValidationCategory,
    ValidationProfile,
)


def test_resilience_validator_direct_methods():
    from core.validator.resilience_validators import ResilienceValidator

    v = ResilienceValidator()

    # DB unavailable but fallback present -> pass
    assert v.validate_db_unavailable_during_query(db_available=False, fallback_used=True)

    # Partial graph load below threshold -> fail
    assert not v.validate_partial_graph_load(loaded_fraction=0.5)

    # Latency spikes beyond threshold -> fail
    assert not v.validate_network_latency_spikes([10, 2000, 50])

    # Retry policy respected
    assert v.validate_retry_logic_correctness({'max_retries': 5}, observed_retries=3)


def test_resilience_validator_via_manager():
    manager = create_validation_manager_with_defaults()

    config = {
        'db_available': False,
        'fallback_used': True,
        'loaded_fraction': 0.80,
        'recent_latencies_ms': [10, 20, 30],
    }

    report = manager.validate(config, specific_categories={ValidationCategory.RESILIENCE})
    assert report.all_passed
    assert report.total_checks >= 1

    # Now provide failing inputs
    bad_config = {
        'db_available': False,
        'fallback_used': False,  # no fallback -> should fail RT-171
    }
    bad_report = manager.validate(bad_config, specific_categories={ValidationCategory.RESILIENCE})
    assert not bad_report.all_passed
    assert bad_report.failed_checks >= 1
