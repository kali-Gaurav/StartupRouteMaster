"""
Simple selector candidate generator.
Generates CSS and XPath candidate selectors from an HTML snapshot using heuristics.
This is intentionally lightweight — the heavy ranking/evaluation happens in selector_tester.
"""
from bs4 import BeautifulSoup
from typing import List


def generate_table_selectors(html: str) -> List[str]:
    """Return candidate CSS selectors likely to match schedule tables."""
    soup = BeautifulSoup(html, 'html.parser')
    candidates = []

    # common table classes
    for cls in ('table-striped', 'table', 'schedule-table', 'tbl'):
        candidates.append(f'table.{cls}')
        candidates.append(f'table[class*="{cls}"]')

    # find tables and generate row/column selectors
    for i, tbl in enumerate(soup.find_all('table')):
        # prefer tables with many rows
        row_count = len(tbl.select('tbody tr')) if tbl.select('tbody tr') else len(tbl.select('tr'))
        if row_count >= 1:
            # use nth-of-type selector for this table
            candidates.append(f'table:nth-of-type({i+1})')
            candidates.append(f'table:nth-of-type({i+1}) tbody tr')
            # add td column selectors for first 5 columns
            for col in range(1, 6):
                candidates.append(f'table:nth-of-type({i+1}) tbody tr td:nth-child({col})')

    # dedupe while preserving order
    seen = set()
    out = []
    for c in candidates:
        if c not in seen:
            out.append(c)
            seen.add(c)
    return out


def generate_xpath_variants(css_selector: str) -> List[str]:
    """Produce simple XPath variants from a CSS selector (best-effort).
    This is not a full CSS-to-XPath converter but helps provide alternatives.
    """
    # naive mapping for table/td selectors
    xpath = css_selector.replace('table', '//table').replace('tbody', '/tbody').replace('tr', '/tr').replace('td', '/td')
    return [xpath]
