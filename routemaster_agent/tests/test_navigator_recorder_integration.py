import os
import pytest
from pathlib import Path
from playwright.async_api import async_playwright

from routemaster_agent.data.scene_recorder import SceneRecorder
from routemaster_agent.core.navigator_ai import NavigatorAI


@pytest.mark.asyncio
async def test_navigator_records_steps_with_scene_recorder(tmp_path):
    recorder = SceneRecorder(base_dir=tmp_path)
    scene_dir = await recorder.start_scene('test_scene_01', {'task': 'search_trains'})

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        html = '''
        <html><body>
          <label for="train_no">Train Number</label>
          <input id="train_no" name="train_no" placeholder="Train no" />
          <button id="get-schedule">Get Schedule</button>
        </body></html>
        '''
        await page.set_content(html)

        nav = NavigatorAI(scene_recorder=recorder)
        inp = await nav.find_element_by_visual_label(page, 'Train Number', element_type='input')
        assert inp is not None
        await nav.fill_input_and_trigger_event(page, inp, '12345', delay_ms=1)

        btn = await nav.find_button_by_intent(page, 'Get Schedule')
        assert btn is not None
        await btn.click()

        # finish scene and verify files
        out = recorder.finish_scene()
        sc_json = Path(out) / 'scene.json'
        assert sc_json.exists()
        data = sc_json.read_text(encoding='utf-8')
        assert 'steps' in data

        # verify recorded steps include the new metadata schema
        import json
        obj = json.loads(data)
        assert isinstance(obj.get('steps'), list) and len(obj['steps']) >= 1
        for step in obj['steps']:
            assert 'meta' in step
            assert set(['strategy','selector_confidence','time_to_success_ms','success']).issubset(set(step['meta'].keys()))

        await browser.close()