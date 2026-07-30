import asyncio
import json
import sys
from pathlib import Path

# ensure project root is on sys.path so `routemaster_agent` can be imported when
# running this script directly
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from routemaster_agent.core.reasoning_controller import ReasoningController


class DummyVision:
    def __init__(self, context=None):
        self.context = context

    async def analyze_page_structure(self, page):
        return {'context': self.context, 'title': 'dummy'}


class FileRetriever:
    def __init__(self, skills):
        self._skills = skills

    async def retrieve_skills(self, context, task=None, max_results=3):
        # return skills that match context first
        matches = [s for s in self._skills if s.get('context') == context]
        if not matches:
            return self._skills[:max_results]
        return matches[:max_results]


class DummyExecutor:
    def __init__(self, behavior='success'):
        # behavior: 'success', 'fail', 'raise'
        self.behavior = behavior

    async def execute_skill(self, skill, page=None):
        if self.behavior == 'raise':
            raise RuntimeError('simulated execution error')
        if self.behavior == 'fail':
            return {'success': False, 'error': 'step failed'}
        return {'success': True, 'steps_executed': 1, 'total_steps': 1}


class DummyGemini:
    def __init__(self):
        self.called = False

    async def propose_actions(self, page, task):
        self.called = True
        return [{'type': 'click', 'selector': '#fallback'}]


async def run_integration_tests():
    reg_path = Path('datasets/mock_skill_registry.json')
    assert reg_path.exists(), 'mock skill registry not found at datasets/mock_skill_registry.json'
    registry = json.loads(reg_path.read_text(encoding='utf-8'))
    skills = registry.get('skills', [])

    # Scenario 1: Skill executes successfully (high confidence)
    vision = DummyVision(context='search_form')
    retriever = FileRetriever(skills)
    executor = DummyExecutor(behavior='success')
    gemini = DummyGemini()
    rc = ReasoningController(skill_retriever=retriever, skill_executor=executor, gemini_client=gemini, vision_ai=vision, skill_registry_path=str(reg_path))

    res1 = await rc.reason_and_act(page=None, task='search', threshold=0.65)
    print('Scenario 1 result:', res1)
    assert res1.get('success') is True
    assert res1.get('from_skill') is not None
    assert gemini.called is False

    # Reload registry to check EMA update
    reg_after_1 = json.loads(reg_path.read_text(encoding='utf-8'))
    s1 = next((s for s in reg_after_1['skills'] if s['skill_id'] == 'mock_search_1'), None)
    assert s1 and s1['metrics']['success_rate'] != 0.85

    # Scenario 2: Low confidence -> Gemini fallback
    vision2 = DummyVision(context='results_page')
    gemini2 = DummyGemini()
    rc2 = ReasoningController(skill_retriever=retriever, skill_executor=executor, gemini_client=gemini2, vision_ai=vision2, skill_registry_path=str(reg_path))
    res2 = await rc2.reason_and_act(page=None, task='inspect', threshold=0.65)
    print('Scenario 2 result:', res2)
    assert res2.get('fallback') is True
    assert gemini2.called is True

    # Scenario 3: Skill executes but fails -> fallback to Gemini
    vision3 = DummyVision(context='search_form')
    retriever3 = FileRetriever(skills)
    executor3 = DummyExecutor(behavior='fail')
    gemini3 = DummyGemini()
    rc3 = ReasoningController(skill_retriever=retriever3, skill_executor=executor3, gemini_client=gemini3, vision_ai=vision3, skill_registry_path=str(reg_path))
    res3 = await rc3.reason_and_act(page=None, task='search', threshold=0.65)
    print('Scenario 3 result:', res3)
    assert res3.get('fallback') is True
    assert gemini3.called is True

    # Scenario 4: Execution raises exception -> gemini fallback
    executor4 = DummyExecutor(behavior='raise')
    gemini4 = DummyGemini()
    rc4 = ReasoningController(skill_retriever=retriever3, skill_executor=executor4, gemini_client=gemini4, vision_ai=vision3, skill_registry_path=str(reg_path))
    try:
        res4 = await rc4.reason_and_act(page=None, task='search', threshold=0.65)
        print('Scenario 4 result:', res4)
        # if execution raised, controller should have attempted fallback
        assert res4.get('fallback') is True
        assert gemini4.called is True
    except Exception as e:
        print('Scenario 4 raised unexpectedly:', e)
        raise

    print('\nAll integration scenarios passed.')


if __name__ == '__main__':
    asyncio.run(run_integration_tests())
