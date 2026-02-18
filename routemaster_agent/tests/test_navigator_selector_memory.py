import os
import pytest
from pathlib import Path
from playwright.async_api import async_playwright

from routemaster_agent.core.navigator_ai import NavigatorAI
from routemaster_agent.intelligence import selector_registry


@pytest.mark.asyncio
async def test_find_element_records_selector_in_registry(tmp_path):
    reg_path = tmp_path / 'selector_registry.json'
    os.environ['RMA_SELECTOR_REGISTRY'] = str(reg_path)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        html = '''
        <html><body>
          <label for="train_no">Train Number</label>
          <input id="train_no" name="train_no" placeholder="Enter train number" />
        </body></html>
        '''
        await page.set_content(html)

        nav = NavigatorAI()
        loc = await nav.find_element_by_visual_label(page, "Train Number", element_type="input", page_type="test_page")
        assert loc is not None

        # registry should contain a backup selector entry for 'test_page'
        reg = selector_registry.list_registry(Path(str(reg_path)))
        assert 'test_page' in reg
        entry = reg['test_page']
        # backups should include either a name/placeholder based selector
        backups = entry.get('backups', [])
        assert any(('train_no' in (b.get('selector') or '') or 'placeholder' in (b.get('selector') or '')) for b in backups)

        await browser.close()

    del os.environ['RMA_SELECTOR_REGISTRY']


@pytest.mark.asyncio
async def test_find_button_records_selector_in_registry(tmp_path):
    reg_path = tmp_path / 'selector_registry_btn.json'
    os.environ['RMA_SELECTOR_REGISTRY'] = str(reg_path)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        html = '''
        <html><body>
          <button id="search-btn">Get Schedule</button>
        </body></html>
        '''
        await page.set_content(html)

        nav = NavigatorAI()
        btn = await nav.find_button_by_intent(page, "Get Schedule", page_type="test_page_btn")
        assert btn is not None

        reg = selector_registry.list_registry(Path(str(reg_path)))
        assert 'test_page_btn' in reg
        entry = reg['test_page_btn']
        backups = entry.get('backups', [])
        assert any('Get Schedule' in (b.get('selector') or '') or 'search-btn' in (b.get('selector') or '') for b in backups)

        await browser.close()

    del os.environ['RMA_SELECTOR_REGISTRY']


@pytest.mark.asyncio
async def test_record_primary_failure_on_not_found(tmp_path):
    reg_path = tmp_path / 'selector_registry_fail.json'
    os.environ['RMA_SELECTOR_REGISTRY'] = str(reg_path)

    # create registry entry with a primary selector that won't be found on page
    reg_entry = {
        'primary': {'selector': "input[name='not_there']", 'score': 0.0, 'success_count': 0, 'failure_count': 0, 'last_tested': None},
        'backups': [],
        'semantic_fallback': True,
        'last_updated': None,
        'last_promotion_timestamp': None,
        'promotion_cooldown_until': None
    }
    selector_registry._save({'ntes_test': reg_entry}, Path(str(reg_path)))

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        html = '<html><body><div>No inputs here</div></body></html>'
        await page.set_content(html)

        nav = NavigatorAI()
        res = await nav.find_element_by_visual_label(page, 'Train Number', element_type='input', page_type='ntes_test')
        assert res is None

        reg = selector_registry.list_registry(Path(str(reg_path)))
        entry = reg['ntes_test']
        # primary failure_count should have incremented
        assert entry['primary']['failure_count'] >= 1

        await browser.close()

    del os.environ['RMA_SELECTOR_REGISTRY']
