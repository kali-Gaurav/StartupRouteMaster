import pytest
from datetime import datetime
from unittest.mock import MagicMock
from backend.core.route_engine import OptimizedRAPTOR, Route
from backend.core.validator.validation_manager import (
    ValidationManager, ValidationCategory, ValidationProfile,
    create_validation_manager_with_defaults
)
from backend.core.validator.multimodal_validators import MultimodalRoute, ModalitySegment, TransportMode

def test_validation_manager_delegation():
    """Test that OptimizedRAPTOR delegates to ValidationManager correctly."""
    mock_manager = MagicMock(spec=ValidationManager)
    # Mock a successful report
    mock_report = MagicMock()
    mock_report.all_passed = True
    mock_manager.validate.return_value = mock_report
    mock_manager.validate_api_request.return_value = mock_report

    engine = OptimizedRAPTOR(validation_manager=mock_manager)

    # 1. Test multimodal delegation
    mm_route = MultimodalRoute(segments=[], total_cost=0, total_duration_minutes=0, mode_changes=0)
    engine.validate_multimodal_route(mm_route, {'key': 'val'})
    
    mock_manager.validate.assert_called()
    call_args = mock_manager.validate.call_args[0]
    assert call_args[0]['route'] == mm_route
    assert call_args[0]['key'] == 'val'
    assert ValidationCategory.MULTIMODAL in mock_manager.validate.call_args[1]['specific_categories']

    # 2. Test API delegation
    mock_manager.validate_api_request.reset_mock()
    engine.validate_api_and_security(MagicMock(), MagicMock())
    mock_manager.validate_api_request.assert_called_once()

def test_validation_manager_execution_flow():
    """Integration test: Ensuring ValidationManager actually executes validator methods."""
    manager = create_validation_manager_with_defaults()
    
    # Create a dummy multimodal route that should fail RT-054 if we disable TRAIN
    train_segment = ModalitySegment(
        mode=TransportMode.TRAIN,
        from_stop_id=1, to_stop_id=2,
        departure_time=datetime.now(),
        arrival_time=datetime.now(),
        distance_km=10, cost=100, duration_minutes=10
    )
    route = MultimodalRoute(segments=[train_segment], total_cost=100, total_duration_minutes=10, mode_changes=0)
    
    # RUN VALIDATION: Disable TRAIN mode.
    # ValidationManager should find validate_disabled_transport_mode_excluded in MultimodalValidator
    # and execute it because 'disabled_modes' is in config.
    config = {
        'route': route,
        'disabled_modes': [TransportMode.TRAIN]
    }
    
    report = manager.validate(config, specific_categories={ValidationCategory.MULTIMODAL})
    
    # Assertions
    assert report.total_checks > 0
    # Find the RT-054 check result
    res_054 = next((r for r in report.results if r.passed is False), None)
    assert res_054 is not None, "RT-054 should have failed"
    assert not report.all_passed
