import pytest
from backend.core.validator.validation_manager import create_validation_manager_with_defaults, ValidationCategory


def test_production_validators_direct_and_manager():
    from backend.core.validator.production_validators import ProductionExcellenceValidator

    pv = ProductionExcellenceValidator()

    assert pv.validate_end_to_end_booking_integration(True, True)
    assert not pv.validate_route_revalidation_before_booking({}, {})

    manager = create_validation_manager_with_defaults()
    config = {
        'booking_flow_successful': True,
        'consistency_ok': True,
        'route_at_selection': {'route_id': 'r1', 'signature': 's1'},
        'booking_result': {'route_id': 'r1'},
    }

    report = manager.validate(config, specific_categories={ValidationCategory.PRODUCTION_EXCELLENCE})
    assert report.all_passed
    assert report.total_checks >= 1
