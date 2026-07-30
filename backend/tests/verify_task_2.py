import time
from core.data_utils.structures import DynamicWaitConfig, SearchPhase
from core.engines.dynamic_logic import compute_dynamic_window, is_valid_transfer

def test_phase_windows():
    config = DynamicWaitConfig()
    journey = 600 # 10 hours
    
    # Phase 1: STRICT (0.5x)
    min1, max1 = compute_dynamic_window(journey, config, phase=SearchPhase.STRICT)
    # base max_w for 600m is ~154m. STRICT -> 77m.
    print(f"STRICT window: {min1}-{max1}")
    assert max1 < 100
    
    # Phase 2: MODERATE (1.0x)
    min2, max2 = compute_dynamic_window(journey, config, phase=SearchPhase.MODERATE)
    print(f"MODERATE window: {min2}-{max2}")
    assert 150 <= max2 <= 160
    
    # Phase 3: RELAXED (2.0x)
    min3, max3 = compute_dynamic_window(journey, config, phase=SearchPhase.RELAXED)
    print(f"RELAXED window: {min3}-{max3}")
    assert 300 <= max3 <= 320

def test_phase_validation():
    config = DynamicWaitConfig()
    journey = 600
    
    # A transfer with 120m wait
    # Valid in MODERATE/RELAXED, but NOT in STRICT (max 77)
    assert is_valid_transfer(600, 720, journey, config, phase=SearchPhase.STRICT) is False
    assert is_valid_transfer(600, 720, journey, config, phase=SearchPhase.MODERATE) is True
    
    # A transfer with 280m wait (ratio 280/880 ~= 0.31)
    # Valid in MODERATE (max 154) -> FALSE.
    # Wait... MODERATE max is 154. So 280 is too long.
    # RELAXED max is 308. So 280 is valid.
    assert is_valid_transfer(600, 880, journey, config, phase=SearchPhase.MODERATE) is False
    assert is_valid_transfer(600, 880, journey, config, phase=SearchPhase.RELAXED) is True

def test_relaxed_ratio():
    config = DynamicWaitConfig()
    # Journey 100m, Wait 100m -> ratio 0.5.
    # STRICT/MODERATE limit is 0.4.
    # RELAXED limit is 0.6.
    # MODERATE max_w for 100m is ~63m. So wait 100 is already > max_w.
    
    # Let's use a very long base max_wait to test ratio independently
    config_loose = DynamicWaitConfig(max_wait_minutes=1000)
    # Journey 100m, Wait 100m. 
    # MODERATE: max_w for 100m with base 1000 is ~263m. Wait 100 is < 263.
    # But ratio 100/200 = 0.5 > 0.4. Should be False.
    assert is_valid_transfer(0, 100, 100, config_loose, phase=SearchPhase.MODERATE) is False
    
    # RELAXED: ratio 0.5 < 0.6. Should be True.
    assert is_valid_transfer(0, 100, 100, config_loose, phase=SearchPhase.RELAXED) is True

if __name__ == "__main__":
    test_phase_windows()
    test_phase_validation()
    test_relaxed_ratio()
    print("TASK 2 VERIFICATION COMPLETE")
