import pytest
from playwright.async_api import async_playwright

from routemaster_agent.core.scroll_intelligence import ScrollIntelligence


@pytest.mark.asyncio
async def test_detect_load_more_buttons_and_auto_click(tmp_path):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        html = '''
        <html><body>
          <div id="items">1</div>
          <button id="load-more">Load more</button>
          <script>
            let count = 1;
            document.getElementById('load-more').addEventListener('click', function(){
              count += 1;
              const d = document.createElement('div'); d.className = 'item'; d.innerText = 'item'+count;
              document.getElementById('items').appendChild(d);
              if (count > 3) { document.getElementById('load-more').style.display = 'none'; }
            });
          </script>
        </body></html>
        '''
        await page.set_content(html)

        sc = ScrollIntelligence()
        candidates = await sc.detect_load_more_buttons(page)
        assert any('load-more' in c.get('selector') for c in candidates)

        clicks = await sc.auto_click_load_more(page, max_clicks=5, wait_ms=100)
        assert clicks >= 1

        # ensure items were appended
        items = await page.query_selector_all('.item')
        assert len(items) >= 1

        await browser.close()


@pytest.mark.asyncio
async def test_perform_infinite_scroll_detects_new_content():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        html = '''
        <html><body>
          <div id="list" style="height:200px; overflow:auto;">
            <div id="content" style="height:800px;">initial</div>
          </div>
          <script>
            const list = document.getElementById('list');
            list.addEventListener('scroll', function(){
              if (list.scrollTop > 200 && !document.getElementById('extra')){
                const e = document.createElement('div'); e.id='extra'; e.className='item'; e.innerText='more'; document.getElementById('content').appendChild(e);
              }
            });
          </script>
        </body></html>
        '''
        await page.set_content(html)

        sc = ScrollIntelligence()
        ok = await sc.perform_infinite_scroll(page, item_selector='.item', max_scrolls=6, scroll_step=300, idle_rounds=2)
        assert ok is True

        await browser.close()