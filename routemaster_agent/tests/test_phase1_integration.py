import pytest
from playwright.async_api import async_playwright

from routemaster_agent.core.navigator_ai import NavigatorAI
from routemaster_agent.core.vision_ai import VisionAI
from routemaster_agent.core.extractor_ai import ExtractionAI


@pytest.mark.asyncio
async def test_phase1_full_loop_train_search():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        html = '''
        <html><body>
          <label for="train_no">Train Number</label>
          <input id="train_no" name="train_no" placeholder="Train no" />
          <button id="get-schedule">Get Schedule</button>

          <div id="result-area">
            <table id="schedule-table" style="display:none; width:100%;">
              <thead><tr><th>Station</th><th>Arrival</th><th>Departure</th><th>Distance</th></tr></thead>
              <tbody id="schedule-body"></tbody>
            </table>
          </div>

          <script>
            document.getElementById('get-schedule').addEventListener('click', function() {
              const tbody = document.getElementById('schedule-body');
              tbody.innerHTML = '<tr><td>HOWRAH JN</td><td>16:05</td><td>16:05</td><td>0</td></tr>'
                              + '<tr><td>BARDHAMAN</td><td>16:57</td><td>16:59</td><td>70</td></tr>';
              document.getElementById('schedule-table').style.display = 'table';
            });
          </script>
        </body></html>
        '''

        await page.set_content(html)

        # OBSERVE
        vision = VisionAI()
        structure = await vision.analyze_page_structure(page)
        assert isinstance(structure, dict)

        # THINK / DECIDE: find input + button
        nav = NavigatorAI()
        input_locator = await nav.find_element_by_visual_label(page, 'Train Number', element_type='input', page_type='ntes_schedule')
        assert input_locator is not None

        # ACT: fill and click
        ok = await nav.fill_input_and_trigger_event(page, input_locator, '12345', delay_ms=5)
        assert ok is True

        btn = await nav.find_button_by_intent(page, 'Get Schedule', page_type='ntes_schedule')
        assert btn is not None
        await btn.click()

        # VERIFY: wait for table and extract
        await page.wait_for_selector('#schedule-table[style*="display: table"], #schedule-table:not([style*="display:none"])', timeout_ms=3000)
        extractor = ExtractionAI(vision_ai=vision)
        rows = await extractor.extract_table_data(page, table_selector='#schedule-table')

        assert len(rows) >= 1, f"Expected at least 1 row, got {len(rows)}"
        if rows:
            assert 'Station' in rows[0], f"Expected 'Station' column, got {list(rows[0].keys())}"
            assert rows[0]['Station'] == 'HOWRAH JN', f"Expected HOWRAH JN, got {rows[0].get('Station')}"
        if len(rows) >= 2:
            assert rows[1]['Distance'] == '70', f"Expected 70, got {rows[1].get('Distance')}"

        await browser.close()