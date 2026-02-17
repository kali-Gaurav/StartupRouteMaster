import pytest
import asyncio

from routemaster_agent.core.decision_engine import DecisionEngine
from routemaster_agent.core.extractor_ai import ExtractionAI


def test_compare_data_and_significance():
    de = DecisionEngine()

    existing = {
        'a': {'value': '1'},
        'b': {'value': 'two'},
        'c': {'value': 'unchanged'}
    }

    new = {
        'a': {'value': '2'},  # changed
        'b': {'value': 'two'},  # unchanged
        'd': {'value': 'newval'}  # new
    }

    diffs = de._compare_data(new, existing)
    assert 'a' in [c['field'] for c in diffs['changed_fields']]
    assert 'd' in diffs['new_fields']
    assert 'c' in diffs['removed_fields']

    significance = de._calculate_change_significance(diffs)
    # changed fields = 1, unchanged = 1 -> significance 0.5
    assert pytest.approx(significance, rel=1e-3) == 0.5


def test_has_suspicious_changes_detects_status_and_large_number_changes():
    de = DecisionEngine()

    diffs = {
        'changed_fields': [
            {'field': 'status', 'old': 'On Time', 'new': 'Cancelled'},
            {'field': 'distance', 'old': '10', 'new': '1000'},
        ]
    }

    assert de._has_suspicious_changes(diffs) is True

    diffs2 = {'changed_fields': [{'field': 'name', 'old': 'A', 'new': 'B'}]}
    assert de._has_suspicious_changes(diffs2) is False


@pytest.mark.asyncio
async def test_validate_extracted_value_basic_types():
    ea = ExtractionAI()

    assert (await ea._validate_extracted_value('123', 'number'))['passed'] is True
    assert (await ea._validate_extracted_value('12a', 'number'))['passed'] is False

    assert (await ea._validate_extracted_value('2024-01-01', 'date'))['passed'] is True
    assert (await ea._validate_extracted_value('25:61', 'time'))['passed'] is False

    assert (await ea._validate_extracted_value('me@example.com', 'email'))['passed'] is True
    assert (await ea._validate_extracted_value('', 'text'))['passed'] is False
