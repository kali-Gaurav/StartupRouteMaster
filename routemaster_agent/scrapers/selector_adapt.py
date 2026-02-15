from typing import List, Dict, Any
from playwright.async_api import Page


async def extract_table_heuristic(page: Page) -> List[Dict[str, Any]]:
    """Try to find any sensible table on the page and extract rows heuristically.

    Returns a list of row dicts with best-effort mapping to common columns.
    """
    tables = await page.query_selector_all('table')
    best_rows = []

    for tbl in tables:
        try:
            # attempt to get header texts
            headers = []
            thead = await tbl.query_selector('thead')
            if thead:
                ths = await thead.query_selector_all('th')
                for th in ths:
                    try:
                        headers.append((await th.inner_text()).strip().lower())
                    except Exception:
                        headers.append('')
            # fallback to first row as header if thead missing
            if not headers:
                first_row = await tbl.query_selector('tr')
                if first_row:
                    cols = await first_row.query_selector_all('td,th')
                    if cols and len(cols) > 1:
                        headers = []
                        for c in cols:
                            try:
                                headers.append((await c.inner_text()).strip().lower())
                            except Exception:
                                headers.append('')

            rows = []
            trs = await tbl.query_selector_all('tbody tr')
            if not trs:
                trs = await tbl.query_selector_all('tr')

            for tr in trs:
                try:
                    tds = await tr.query_selector_all('td')
                    if not tds:
                        continue
                    texts = []
                    for td in tds:
                        try:
                            texts.append((await td.inner_text()).strip())
                        except Exception:
                            texts.append('')

                    # Heuristic mapping based on number of columns
                    row = {}
                    if len(texts) >= 8:
                        # common schedule layout
                        row = {
                            'sequence': texts[0],
                            'station_code': texts[1],
                            'station_name': texts[2],
                            'day': texts[3] if len(texts) > 3 else None,
                            'arrival': texts[4] if len(texts) > 4 else None,
                            'departure': texts[5] if len(texts) > 5 else None,
                            'halt': texts[6] if len(texts) > 6 else None,
                            'distance': texts[7] if len(texts) > 7 else None,
                        }
                    else:
                        # best-effort: map first columns
                        keys = ['sequence', 'station_code', 'station_name', 'arrival', 'departure', 'halt', 'distance']
                        for i, txt in enumerate(texts):
                            if i < len(keys):
                                row[keys[i]] = txt

                    rows.append(row)
                except Exception:
                    continue

            # choose the table with most rows
            if len(rows) > len(best_rows):
                best_rows = rows
        except Exception:
            continue

    return best_rows
