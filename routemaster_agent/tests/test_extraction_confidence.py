from routemaster_agent.intelligence.reliability import compute_extraction_confidence


def test_compute_extraction_confidence_basic():
    assert compute_extraction_confidence(selector_confidence=1.0, retry_count=0, validation_pass_rate=1.0, proxy_health_score=1.0) == 1.0


def test_compute_extraction_confidence_retry_penalty():
    # 0.9 ** 2 == 0.81
    assert compute_extraction_confidence(selector_confidence=1.0, retry_count=2, validation_pass_rate=1.0, proxy_health_score=1.0) == 0.81


def test_compute_extraction_confidence_combined():
    # 0.8 * 0.9 * 0.5 * 0.5 == 0.18
    val = compute_extraction_confidence(selector_confidence=0.8, retry_count=1, validation_pass_rate=0.5, proxy_health_score=0.5)
    assert abs(val - 0.18) < 1e-6
