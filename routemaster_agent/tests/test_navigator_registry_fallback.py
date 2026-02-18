import os
import pytest
from pathlib import Path
from playwright.async_api import async_playwright

from routemaster_agent.core.navigator_ai import NavigatorAI
from routemaster_agent.intelligence import selector_registry


@pytest.mark.asyncio
async def test_navigator_uses_primary_selector_if_present(tmp_path):
    reg_path = tmp_path / 'selector_registry.json'
    os.environ['RMA_SELECTOR_REGISTRY'] = str(reg_path)

    # create registry entry with primary selector matching the page
    selector_registry._save({'promo_test': {'primary': {'selector': "input[name='from']", 'score': 0.0, 'success_count': 0, 'failure_count': 0, 'last_tested': None}, 'backups': [], 'semantic_fallback': True, 'last_updated': None, 'last_promotion_timestamp': None, 'promotion_cooldown_until': None}} , Path(str(reg_path)))

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content("<html><body><input name='from' placeholder='From station' /></body></html>")

        nav = NavigatorAI()
        loc = await nav.find_element_by_visual_label(page, 'From station', element_type='input', page_type='promo_test')
        assert loc is not None

        reg = selector_registry.list_registry(Path(str(reg_path)))
        # primary should have recorded a success
        assert reg['promo_test']['primary']['success_count'] >= 1

        await browser.close()

    del os.environ['RMA_SELECTOR_REGISTRY']


@pytest.mark.asyncio
async def test_navigator_tries_backups_when_primary_fails(tmp_path):
    reg_path = tmp_path / 'selector_registry_bak.json'
    os.environ['RMA_SELECTOR_REGISTRY'] = str(reg_path)

    # primary points to non-existing selector; backup points to real element
    selector_registry._save({'promo_test': {'primary': {'selector': "input[name='not_there']", 'score': 0.0, 'success_count': 0, 'failure_count': 0, 'last_tested': None}, 'backups': [{'selector': "input[name='from']", 'score': None, 'success_count': 0, 'failure_count': 0, 'last_tested': None}], 'semantic_fallback': True, 'last_updated': None, 'last_promotion_timestamp': None, 'promotion_cooldown_until': None}} , Path(str(reg_path)))

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content("<html><body><input name='from' placeholder='From station' /></body></html>")

        nav = NavigatorAI()
        loc = await nav.find_element_by_visual_label(page, 'From station', element_type='input', page_type='promo_test')
        assert loc is not None

        reg = selector_registry.list_registry(Path(str(reg_path)))
        backups = reg['promo_test'].get('backups', [])
        assert any(b.get('selector') == "input[name='from']" and b.get('success_count', 0) >= 1 for b in backups)

        await browser.close()

    del os.environ['RMA_SELECTOR_REGISTRY']
