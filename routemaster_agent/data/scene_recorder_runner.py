"""Orchestration script to auto-record demo scenes using NavigatorAI + Playwright.

Usage (programmatic):
    from routemaster_agent.data.scene_recorder import SceneRecorder
    from routemaster_agent.data.scene_recorder_runner import record_demo_scenes

    recorder = SceneRecorder('datasets/raw_scenes')
    await record_demo_scenes(recorder, count=30)

The runner uses simple HTML templates (mock NTES/IRCTC-like pages) to produce
reproducible scenes suitable for Phase-2 dataset collection.
"""
from typing import Optional
import asyncio
from pathlib import Path
from datetime import datetime

from playwright.async_api import async_playwright
from routemaster_agent.data.scene_recorder import SceneRecorder
from routemaster_agent.core.navigator_ai import NavigatorAI


MOCK_TEMPLATES = [
    # template 1: NTES-style simple search + results
    lambda train_no: f'''<html><body>
        <label for="train_no">Train Number</label>
        <input id="train_no" name="train_no" placeholder="Train no" />
        <button id="get-schedule">Get Schedule</button>
        <div id="result-area"></div>
        <script>
          document.getElementById('get-schedule').addEventListener('click', function() {{
            const tbody = document.getElementById('result-area');
            tbody.innerHTML = '<div class="row">Train {train_no} - HOWRAH</div>';
          }});
        </script>
    </body></html>''',

    # template 2: results with load-more
    lambda train_no: f'''<html><body>
        <label for="from">From</label>
        <input id="from" name="from" placeholder="From station" />
        <label for="to">To</label>
        <input id="to" name="to" placeholder="To station" />
        <button id="search">Search Trains</button>
        <div id="results"><div class="item">Train A</div></div>
        <button id="load-more">Load more</button>
        <script>
          document.getElementById('search').addEventListener('click', function() {{ document.getElementById('results').innerHTML = '<div class=\'item\'>Train {train_no}</div>' }});
          document.getElementById('load-more').addEventListener('click', function() {{ const d=document.createElement('div'); d.className='item'; d.innerText='more'; document.getElementById('results').appendChild(d); }});
        </script>
    </body></html>''',
]


async def _run_single_scene(recorder: SceneRecorder, template_idx: int, scene_id: str, train_no: str):
    # create a per-scene recorder to avoid concurrent access to shared state
    local_recorder = SceneRecorder(base_dir=recorder.base_dir)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        html = MOCK_TEMPLATES[template_idx % len(MOCK_TEMPLATES)](train_no)
        await page.set_content(html)

        await local_recorder.start_scene(scene_id, {"task": "demo_record", "template": template_idx, "train_no": train_no, "created_at": datetime.utcnow().isoformat() + 'Z'})

        nav = NavigatorAI(scene_recorder=local_recorder)

        # simple flows for templates
        if template_idx % 2 == 0:
            input_loc = await nav.find_element_by_visual_label(page, 'Train Number', element_type='input')
            if input_loc:
                await nav.fill_input_and_trigger_event(page, input_loc, train_no, delay_ms=5)
            btn = await nav.find_button_by_intent(page, 'Get Schedule')
            if btn:
                await btn.click()
                await page.wait_for_selector('#result-area .row', timeout=2000)
        else:
            from_loc = await nav.find_element_by_visual_label(page, 'From', element_type='input')
            to_loc = await nav.find_element_by_visual_label(page, 'To', element_type='input')
            if from_loc:
                await nav.fill_input_and_trigger_event(page, from_loc, 'JP', delay_ms=5)
            if to_loc:
                await nav.fill_input_and_trigger_event(page, to_loc, 'KOTA', delay_ms=5)
            search_btn = await nav.find_button_by_intent(page, 'Search Trains')
            if search_btn:
                await search_btn.click()
                await page.wait_for_selector('#results .item', timeout=2000)
            # click load more once
            from routemaster_agent.core.scroll_intelligence import ScrollIntelligence
            sc = ScrollIntelligence()
            await sc.auto_click_load_more(page, max_clicks=1, wait_ms=200)

        local_recorder.finish_scene()
        await browser.close()


async def record_demo_scenes(recorder: SceneRecorder, count: int = 30, start_idx: int = 1, concurrency: int = 3):
    """Orchestrate multiple demo scene recordings (async).

    Runs up to `concurrency` recordings in parallel to avoid resource exhaustion.
    """
    # helper to run with a semaphore
    sem = asyncio.Semaphore(concurrency)

    async def _limited_run(idx: int):
        async with sem:
            scene_id = f"demo_scene_{idx:03d}"
            template_idx = idx % len(MOCK_TEMPLATES)
            train_no = str(10000 + idx)
            await _run_single_scene(recorder, template_idx, scene_id, train_no)

    tasks = [_limited_run(i) for i in range(start_idx, start_idx + count)]

    # run tasks in bounded parallel batches
    for i in range(0, len(tasks), concurrency):
        batch = tasks[i : i + concurrency]
        await asyncio.gather(*batch)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default='datasets/raw_scenes')
    parser.add_argument('--count', type=int, default=10)
    args = parser.parse_args()

    rec = SceneRecorder(base_dir=args.out)
    import asyncio
    asyncio.run(record_demo_scenes(rec, count=args.count))