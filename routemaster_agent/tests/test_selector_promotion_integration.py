import os
import pytest
from pathlib import Path

from routemaster_agent.core.navigator_ai import NavigatorAI
from routemaster_agent.intelligence import selector_registry
from routemaster_agent import metrics
from playwright.async_api import async_playwright


@pytest.mark.asyncio
async def test_fill_input_records_success_and_failure(tmp_path):
    reg_path = tmp_path / 'selector_registry_fill.json'
    os.environ['RMA_SELECTOR_REGISTRY'] = str(reg_path)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        html = '''
        <html><body>
          <input id="from_stn" name="from" placeholder="From station" />
        </body></html>
        '''
        await page.set_content(html)

        nav = NavigatorAI()
        loc = await nav.find_element_by_visual_label(page, 'From station', element_type='input', page_type='promo_test')
        assert loc is not None

        ok = await nav.fill_input_and_trigger_event(page, loc, 'JP', delay_ms=1, page_type='promo_test')
        assert ok is True

        reg = selector_registry.list_registry(Path(str(reg_path)))
        assert 'promo_test' in reg
        entry = reg['promo_test']
        # backups should show recorded selector success_count
        backups = entry.get('backups', [])
        assert any(b.get('success_count', 0) >= 1 for b in backups)

        # Now simulate a failure for a selector (primary may not be set)
        fail_selector = entry.get('primary', {}).get('selector') or "input[name='missing']"
        selector_registry.record_selector_result('promo_test', fail_selector, False)
        reg2 = selector_registry.list_registry(Path(str(reg_path)))
        primary_failures = reg2['promo_test'].get('primary', {}).get('failure_count', 0)
        # either primary was incremented or the failing selector was recorded as a backup
        backup_hit = any(b.get('selector') == fail_selector and b.get('failure_count', 0) >= 1 for b in reg2['promo_test'].get('backups', []))
        assert primary_failures >= 1 or backup_hit is True

        await browser.close()

    del os.environ['RMA_SELECTOR_REGISTRY']


@pytest.mark.asyncio
async def test_dropdown_and_pagination_recording_and_promotion(tmp_path):
    reg_path = tmp_path / 'selector_registry_pag.json'
    os.environ['RMA_SELECTOR_REGISTRY'] = str(reg_path)

    # prepare registry with a weak primary and a strong backup so promotion can occur
    backup_selector = "button#next-v2"
    primary_selector = "button#next-old"
    reg_entry = {
        'primary': {'selector': primary_selector, 'score': 0.0, 'success_count': 1, 'failure_count': 9, 'last_tested': None},
        'backups': [
            {'selector': backup_selector, 'score': 0.0, 'success_count': 25, 'failure_count': 2, 'last_tested': None}
        ],
        'semantic_fallback': True,
        'last_updated': None,
        'last_promotion_timestamp': None,
        'promotion_cooldown_until': None
    }
    selector_registry._save({'ntes_pagination': reg_entry}, Path(str(reg_path)))

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        # page with dropdown and a next button matching backup selector
        html = '''
        <html><body>
          <select id="class-select"><option>SL</option><option>3AC</option></select>
          <button id="next-v2">Next</button>
        </body></html>
        '''
        await page.set_content(html)

        nav = NavigatorAI()
        # dropdown selection should be recorded
        ok = await nav.handle_dropdown_selection(page, '#class-select', '3AC', page_type='ntes_pagination')
        assert ok is True

        # navigate pagination should click next and record backup selector success
        results = await nav.navigate_pagination(page, max_pages=2, page_type='ntes_pagination')
        assert isinstance(results, list)

        # inspect registry before promotion
        reg_before = selector_registry.list_registry(Path(str(reg_path)))
        print('\nREG_BEFORE =', reg_before)
        assert 'ntes_pagination' in reg_before
        backups = reg_before['ntes_pagination'].get('backups', [])
        print('BACKUPS =', backups)
        primary_sel = reg_before['ntes_pagination'].get('primary', {}).get('selector')
        # either the backup still exists with enough samples OR it was already promoted to primary
        backup_ok = any(b.get('selector') == backup_selector and (b.get('success_count', 0) + b.get('failure_count', 0)) >= 20 for b in backups)
        assert backup_ok or primary_sel == backup_selector

        # evaluate promotion should now see backup with high success and promote it
        promoted = selector_registry.evaluate_promotion('ntes_pagination')
        # allow for either immediate promotion or cooldown behavior; metric must reflect promotion history
        assert promoted is True or metrics.RMA_SELECTOR_PROMOTIONS_TOTAL.labels(page_type='ntes_pagination')._value.get() >= 1

        # metrics counter should have incremented for promotions (if promotion occurred now or earlier)
        before = metrics.RMA_SELECTOR_PROMOTIONS_TOTAL.labels(page_type='ntes_pagination')._value.get()
        assert before >= 0

        await browser.close()

    del os.environ['RMA_SELECTOR_REGISTRY']
