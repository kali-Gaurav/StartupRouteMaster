import asyncio
import sys
from pathlib import Path

# ensure project root is importable
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.async_api import async_playwright
import json

from routemaster_agent.core.reasoning_controller import ReasoningController
from routemaster_agent.skills.skill_retrieval import SkillExecutor


class DummyVision:
    def __init__(self, context):
        self.context = context

    async def analyze_page_structure(self, page):
        return {'context': self.context, 'title': 'dummy'}


class FileRetriever:
    def __init__(self, skills):
        self._skills = skills

    async def retrieve_skills(self, context, task=None, max_results=3):
        matches = [s for s in self._skills if s.get('context') == context]
        if not matches:
            return self._skills[:max_results]
        return matches[:max_results]


class DummyGemini:
    def __init__(self):
        self.called = False

    async def propose_actions(self, page, task):
        self.called = True
        return [{'type': 'click', 'selector': '#fallback'}]


class DummyNavigator:
    async def fill_input_and_trigger_event(self, page, locator, value):
        # locator is a Playwright Locator
        await locator.fill(value)
        try:
            await locator.dispatch_event('input')
        except Exception:
            pass

    async def handle_dropdown_selection(self, page, selector, value):
        await page.select_option(selector, value)

    async def smart_scroll(self, page, max_scrolls=5):
        # no-op for smoke test
        return


async def run_smoke():
    reg_path = Path('datasets/mock_skill_registry.json')
    assert reg_path.exists(), 'mock skill registry missing'
    registry = json.loads(reg_path.read_text(encoding='utf-8'))
    # create a working copy of registry to avoid mutating the on-disk registry used elsewhere
    working = {'skills': []}
    for s in registry.get('skills', []):
        s_copy = dict(s)
        # normalize action sequence
        if 'actions' in s_copy and 'action_sequence' not in s_copy:
            s_copy['action_sequence'] = s_copy['actions']
        # reset key metrics for deterministic smoke test
        if s_copy.get('skill_id') == 'mock_search_1':
            s_copy.setdefault('metrics', {})['success_rate'] = 0.85
        working['skills'].append(s_copy)

    skills = working['skills']
    # write working registry to a temp file to pass into controllers
    import tempfile
    tmpf = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
    tmpf.write(json.dumps(working, indent=2).encode('utf-8'))
    tmpf.flush()
    tmpf.close()
    tmp_reg_path = tmpf.name

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        html = '''
        <html><body>
        <form id="searchForm">
          <input id="fromStation" />
          <input id="toStation" />
          <button id="searchButton" type="button">Search</button>
          <button id="maybeFails" type="button">Maybe Fails</button>
        </form>
        <div id="results"></div>
        <script>
        document.getElementById('searchButton').addEventListener('click', function(){
            document.getElementById('results').textContent = 'results-ready';
        });
        document.getElementById('maybeFails').addEventListener('click', function(){
            throw new Error('simulated click failure');
        });
        </script>
        </body></html>
        '''

        await page.set_content(html)

        # Scenario A: high-confidence skill executes
        vision = DummyVision('search_form')
        retriever = FileRetriever(skills)
        executor = SkillExecutor(navigator_ai=DummyNavigator())
        gemini = DummyGemini()

        rc = ReasoningController(skill_retriever=retriever, skill_executor=executor, gemini_client=gemini, vision_ai=vision, skill_registry_path=str(tmp_reg_path))

        # fix skill format for executor (action_sequence expected)
        for s in skills:
            if 'actions' in s and 'action_sequence' not in s:
                s['action_sequence'] = s['actions']

        res = await rc.reason_and_act(page=page, task='search', threshold=0.65)
        print('Playwright scenario A:', res)

        # Verify that results div updated
        cont = await page.text_content('#results')
        print('Results div content:', cont)

        # Scenario B: low confidence -> gemini
        vision2 = DummyVision('results_page')
        rc2 = ReasoningController(skill_retriever=retriever, skill_executor=executor, gemini_client=gemini, vision_ai=vision2, skill_registry_path=str(tmp_reg_path))
        res2 = await rc2.reason_and_act(page=page, task='inspect', threshold=0.65)
        print('Playwright scenario B:', res2)

        # Scenario C: flaky skill triggers failure -> gemini fallback
        # try clicking the flaky button via skill
        vision3 = DummyVision('search_form')
        # ensure flaky skill is highest by tweaking metrics temporarily
        for s in skills:
            if s.get('skill_id') == 'mock_fail_1':
                s.setdefault('metrics', {})['success_rate'] = 0.99

        rc3 = ReasoningController(skill_retriever=retriever, skill_executor=executor, gemini_client=gemini, vision_ai=vision3, skill_registry_path=str(tmp_reg_path))
        # attempt run; flaky button click will raise in page JS, but Playwright click will surface as error
        res3 = await rc3.reason_and_act(page=page, task='search', threshold=0.65)
        print('Playwright scenario C:', res3)

        await browser.close()


if __name__ == '__main__':
    asyncio.run(run_smoke())
