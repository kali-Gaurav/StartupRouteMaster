"""
Selector testing / evaluation harness.
Accepts HTML or a Playwright `page` snapshot and runs candidate selectors, returning a ranked scorecard.
"""
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import re


def _score_table_rows(rows: List[List[str]], expected_count: Optional[int] = None) -> float:
    """Simple scoring: completeness + basic validation.
    - more rows -> higher score
    - time-format and sequence continuity increase score
    """
    if not rows:
        return 0.0
    score = min(1.0, len(rows) / (expected_count or max(5, len(rows))))

    # bonus if times look valid (HH:MM) in first two rows
    time_re = re.compile(r"^\d{1,2}:\d{2}$")
    time_bonus = 0.0
    for r in rows[:3]:
        for c in r[:6]:
            if isinstance(c, str) and time_re.match(c.strip()):
                time_bonus += 0.05
                break
    score = min(1.0, score + time_bonus)
    return round(score, 3)


def _extract_rows_from_soup(soup: BeautifulSoup, selector: str) -> List[List[str]]:
    els = soup.select(selector)
    rows = []
    # If selector matches rows directly
    if els and els[0].name in ('tr', 'td'):
        for el in els:
            # gather text for all td children
            tds = [td.get_text(strip=True) for td in el.select('td')]
            if tds:
                rows.append(tds)
    else:
        # try to find table then rows
        tbl = soup.select_one(selector) if els else soup.select_one('table')
        if tbl:
            for tr in tbl.select('tbody tr') or tbl.select('tr'):
                tds = [td.get_text(strip=True) for td in tr.select('td')]
                if tds:
                    rows.append(tds)
    return rows


def evaluate_selectors(html: str, selectors: List[str], expected_min_rows: Optional[int] = None) -> List[Dict]:
    """Run each selector against HTML and return a ranked list of results.
    Returns: [{selector, rows_count, score, sample_rows}, ...]
    """
    soup = BeautifulSoup(html, 'html.parser')
    results = []
    for sel in selectors:
        try:
            rows = _extract_rows_from_soup(soup, sel)
            score = _score_table_rows(rows, expected_min_rows)
            results.append({
                'selector': sel,
                'rows_count': len(rows),
                'score': score,
                'sample_rows': rows[:3]
            })
        except Exception as e:
            results.append({
                'selector': sel,
                'rows_count': 0,
                'score': 0.0,
                'sample_rows': [],
                'error': str(e)
            })
    # sort by score desc, then rows_count
    results.sort(key=lambda r: (r.get('score', 0), r.get('rows_count', 0)), reverse=True)
    return results


if __name__ == '__main__':
    # quick smoke test
    sample = '<table class="table-striped"><tbody><tr><td>1</td><td>NDLS</td><td>06:00</td></tr></tbody></table>'
    sels = ['table.table-striped tbody tr', 'table tbody tr td:nth-child(2)']
    print(test_selectors(sample, sels, expected_min_rows=1))
