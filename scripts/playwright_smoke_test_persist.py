import asyncio
import sys
from pathlib import Path
import json

# ensure project root is importable
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.async_api import async_playwright
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


class DummyNavigator:
    async def fill_input_and_trigger_event(self, page, locator, value):
        await locator.fill(value)
        try:
            await locator.dispatch_event('input')
        except Exception:
            pass

    async def handle_dropdown_selection(self, page, selector, value):
        await page.select_option(selector, value)

    async def smart_scroll(self, page, max_scrolls=5):
        return


async def run_persist():
    reg_path = Path('datasets/skill_registry.json')
    assert reg_path.exists(), 'persistent registry not found at datasets/skill_registry.json'

    def print_metrics(label):
        data = json.loads(reg_path.read_text(encoding='utf-8'))
        print(f"\n--- {label} registry metrics ---")
        for s in data.get('skills', []):
            print(f"{s.get('skill_name')}: success_rate={s.get('metrics', {}).get('success_rate')}")

    print_metrics('BEFORE')

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        html = '<html><body><input id="from" name="from"><input id="to" name="to"><button id="search">Search</button><div id="results"></div><script>document.getElementById("search").addEventListener("click",()=>{document.getElementById("results").innerText="results-ready"});</script></body></html>'
        await page.set_content(html)

        registry = json.loads(reg_path.read_text(encoding='utf-8'))
        skills = registry.get('skills', [])
        # Ensure action_sequence exists
        for s in skills:
            if 'action_sequence' not in s and 'actions' in s:
                s['action_sequence'] = s['actions']

        retriever = FileRetriever(skills)
        executor = SkillExecutor(navigator_ai=DummyNavigator())
        rc = ReasoningController(skill_retriever=retriever, skill_executor=executor, gemini_client=None, vision_ai=DummyVision('generic_page'), skill_registry_path=str(reg_path))

        res = await rc.reason_and_act(page=page, task='demo', threshold=0.65)
        print('\nExecution result:', res)

        await browser.close()

    print_metrics('AFTER')


if __name__ == '__main__':
    asyncio.run(run_persist())
