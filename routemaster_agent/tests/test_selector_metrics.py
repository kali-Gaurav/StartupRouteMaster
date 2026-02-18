import os
from pathlib import Path

from routemaster_agent.intelligence import selector_registry
from routemaster_agent import metrics


def test_selector_success_and_failure_metrics(tmp_path):
    os.environ['RMA_SELECTOR_REGISTRY'] = str(tmp_path / 'selector_registry.json')

    selector = "input[name='demo']"
    selector_registry.record_selector_result('metric_page', selector, True)
    val = metrics.RMA_SELECTOR_SUCCESS_TOTAL.labels(page_type='metric_page', selector=selector)._value.get()
    assert val >= 1

    selector_registry.record_selector_result('metric_page', selector, False)
    val_fail = metrics.RMA_SELECTOR_FAILURE_TOTAL.labels(page_type='metric_page', selector=selector)._value.get()
    assert val_fail >= 1

    del os.environ['RMA_SELECTOR_REGISTRY']
