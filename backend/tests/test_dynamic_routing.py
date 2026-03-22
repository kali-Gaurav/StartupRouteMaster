import pytest
from datetime import datetime, time, timedelta
from core.data_structures import DynamicWaitConfig
from core.route_engine.dynamic_logic import (
    calculate_journey_duration_heuristic,
    compute_dynamic_window,
    calculate_transfer_comfort,
    is_night_time
)

def test_journey_duration_heuristic():
    # 550 km / 55 km/h = 10 hours = 600 mins
    assert calculate_journey_duration_heuristic(550, 55.0) == 600
    assert calculate_journey_duration_heuristic(0) == 0

def test_dynamic_window_beta_scaling():
    config = DynamicWaitConfig(min_wait_minutes=15, max_wait_minutes=240, beta=0.5)
    
    # Short journey: 2 hours (120 mins)
    # scale_factor = sqrt(120/1440) = sqrt(1/12) ~= 0.28
    # dynamic_max = 240 * 0.28 = 67 mins
    min_w, max_w = compute_dynamic_window(120, config)
    assert min_w == 15
    assert 60 <= max_w <= 80
    
    # Long journey: 24 hours (1440 mins)
    # scale_factor = sqrt(1) = 1
    # dynamic_max = 240 * 1 = 240 mins
    min_w_long, max_w_long = compute_dynamic_window(1440, config)
    assert max_w_long == 240

def test_night_time_detection():
    assert is_night_time(time(2, 30)) is True
    assert is_night_time(time(1, 0)) is True
    assert is_night_time(time(4, 0)) is True
    assert is_night_time(time(0, 30)) is False
    assert is_night_time(time(5, 0)) is False

def test_transfer_comfort_score():
    config = DynamicWaitConfig(night_penalty_multiplier=2.0)
    arr = datetime(2025, 3, 10, 10, 0)
    
    # Ideal transfer: 60 mins wait
    dep_ideal = arr + timedelta(minutes=60)
    score_ideal = calculate_transfer_comfort(arr, dep_ideal, config)
    assert score_ideal == 1.0
    
    # Tight transfer: 20 mins wait
    dep_tight = arr + timedelta(minutes=20)
    score_tight = calculate_transfer_comfort(arr, dep_tight, config)
    assert score_tight < 1.0
    
    # Night wait: 01:00-02:00
    arr_night = datetime(2025, 3, 10, 0, 30)
    dep_night = datetime(2025, 3, 10, 2, 30)
    score_night = calculate_transfer_comfort(arr_night, dep_night, config)
    assert score_night == 0.5 # Penalty of 2.0 -> 1/2 = 0.5
