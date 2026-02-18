import json
import asyncio
import pytest
from pathlib import Path

from routemaster_agent.core.reasoning_controller import ReasoningController


class DummyVision:
    def __init__(self, context=None):
        self.context = context

    async def analyze_page_structure(self, page):
        return {'context': self.context, 'title': 'dummy'}


class DummyRetriever:
    def __init__(self, skills):
        self._skills = skills

    async def retrieve_skills(self, context, task=None, max_results=3):
        return self._skills


class DummyExecutor:
    def __init__(self, will_succeed=True):
        self.will_succeed = will_succeed

    async def execute_skill(self, skill, page=None):
        return {'success': self.will_succeed, 'steps_executed': 1, 'total_steps': 1}


class DummyGemini:
    def __init__(self):
        self.called = False

    async def propose_actions(self, page, task):
        self.called = True
        return [{'type': 'click', 'selector': '#fallback'}]


@pytest.mark.asyncio
async def test_skill_first_execution(tmp_path):
    # Create a dummy registry file
    registry = {
        'skills': [
            {
                'skill_id': 's1',
                'skill_name': 'ntes_search_1',
                'context': 'ntes_schedule',
                'metrics': {'success_rate': 0.9, 'avg_time_ms': 100},
            }
        ]
    }
    reg_file = tmp_path / 'skill_registry.json'
    reg_file.write_text(json.dumps(registry), encoding='utf-8')

    # Prepare components
    skills = registry['skills']
    retriever = DummyRetriever(skills)
    executor = DummyExecutor(will_succeed=True)
    gemini = DummyGemini()
    vision = DummyVision(context='ntes_schedule')

    rc = ReasoningController(skill_retriever=retriever, skill_executor=executor, gemini_client=gemini, vision_ai=vision, skill_registry_path=str(reg_file))

    result = await rc.reason_and_act(page=None, task='search_trains', threshold=0.65)
    assert result.get('success') is True
    assert result.get('from_skill') == 'ntes_search_1'

    # Verify registry was updated (EMA applied)
    updated = json.loads(reg_file.read_text(encoding='utf-8'))
    assert updated['skills'][0]['metrics']['success_rate'] != 0.9


@pytest.mark.asyncio
async def test_fallback_to_gemini_when_low_confidence(tmp_path):
    registry = {
        'skills': [
            {
                'skill_id': 's1',
                'skill_name': 'ntes_search_1',
                'context': 'ntes_schedule',
                'metrics': {'success_rate': 0.3, 'avg_time_ms': 100},
            }
        ]
    }
    reg_file = tmp_path / 'skill_registry.json'
    reg_file.write_text(json.dumps(registry), encoding='utf-8')

    skills = registry['skills']
    retriever = DummyRetriever(skills)
    executor = DummyExecutor(will_succeed=True)
    gemini = DummyGemini()
    vision = DummyVision(context='ntes_schedule')

    rc = ReasoningController(skill_retriever=retriever, skill_executor=executor, gemini_client=gemini, vision_ai=vision, skill_registry_path=str(reg_file))
    result = await rc.reason_and_act(page=None, task='search_trains', threshold=0.65)
    assert result.get('fallback') is True
    assert gemini.called is True
