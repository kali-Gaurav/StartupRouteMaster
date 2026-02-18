import os
import pytest
from pathlib import Path
from playwright.async_api import async_playwright

from routemaster_agent.core.vision_ai import VisionAI
from routemaster_agent.core.navigator_ai import NavigatorAI


@pytest.mark.asyncio
async def test_detect_scrollable_regions():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        html = '''
        <html><body>
          <div id="container" style="height:100px; overflow-y:auto; border:1px solid #000;">
            <ul>
              %s
            </ul>
          </div>
        </body></html>
        ''' % '\n'.join([f"<li>Item {i}</li>" for i in range(20)])

        await page.set_content(html)
        vis = VisionAI()
        regions = await vis.detect_scrollable_regions(page)
        assert isinstance(regions, list)
        assert any('container' in (r.get('selector') or '') or r.get('scrollable') for r in regions)

        await browser.close()


@pytest.mark.asyncio
async def test_detect_infinite_scroll():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        html = '''
        <html><body>
          <div id="results">1</div>
          <button id="load-more">Load more</button>
        </body></html>
        '''
        await page.set_content(html)
        vis = VisionAI()
        info = await vis.detect_infinite_scroll(page)
        assert info is not None
        assert info.get('type') == 'button_load_more'
        assert 'load-more' in (info.get('selector') or '')

        await browser.close()


@pytest.mark.asyncio
async def test_smart_scroll_finds_target():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        html = '''
        <html><body>
          <div id="container" style="height:100px; overflow:auto; border:1px solid #000;">
            <div style="height:1200px;">
              <div id="target" style="margin-top:1000px; display:none">TARGET</div>
            </div>
          </div>
          <script>
            document.getElementById('container').addEventListener('scroll', function(e) {
              if (this.scrollTop > 800) {
                document.getElementById('target').style.display = 'block';
              }
            });
          </script>
        </body></html>
        '''
        await page.set_content(html)

        nav = NavigatorAI()
        found = await nav.smart_scroll(page, container_selector='#container', wait_for_selector='#target', max_scrolls=6, scroll_step=200)
        assert found is True

        await browser.close()


@pytest.mark.asyncio
async def test_wait_for_dom_change_detects_change():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        html = '''
        <html><body>
          <div id="list"></div>
          <script>
            setTimeout(function(){ document.getElementById('list').innerHTML = '<div class="item">X</div>'; }, 200);
          </script>
        </body></html>
        '''
        await page.set_content(html)

        nav = NavigatorAI()
        changed = await nav.wait_for_dom_change(page, baseline_selector='#list div', timeout_ms=2000)
        assert changed is True

        await browser.close()


@pytest.mark.asyncio
async def test_wait_for_network_idle_returns_true_on_idle():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        await page.set_content('<html><body><div>static</div></body></html>')
        nav = NavigatorAI()
        ok = await nav.wait_for_network_idle(page, timeout_ms=1000)
        assert ok is True

        await browser.close()