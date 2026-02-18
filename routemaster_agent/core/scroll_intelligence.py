"""Scroll intelligence helpers for RouteMaster Agent.

Provides detection and automation for infinite scroll, "load more" buttons,
and pagination controls. Designed to be Playwright-friendly and unit-testable.
"""
from typing import Optional, List, Dict, Any
import asyncio
import logging

logger = logging.getLogger(__name__)

LOAD_MORE_KEYWORDS = [
    "load more",
    "show more",
    "view more",
    "load",
    "more",
    "next",
]


class ScrollIntelligence:
    """High-level scroll helpers used by NavigatorAI and tests."""

    @staticmethod
    async def detect_load_more_buttons(page) -> List[Dict[str, Any]]:
        """Return list of candidate 'load more' button selectors found on page."""
        candidates = []
        try:
            # find buttons/links whose visible text contains any keyword
            elems = await page.query_selector_all("button, a, [role=button]")
            for el in elems:
                try:
                    txt = (await el.inner_text() or "").strip().lower()
                    if not txt:
                        continue
                    if any(k in txt for k in LOAD_MORE_KEYWORDS):
                        # compute a friendly selector for the element
                        sel = await page.evaluate("el => { return el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.className ? '.' + el.className.split(' ').join('.') : ''); }", el)
                        candidates.append({"selector": sel, "text": txt})
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"detect_load_more_buttons failed: {e}")
        return candidates

    @staticmethod
    async def auto_click_load_more(page, max_clicks: int = 5, wait_ms: int = 500) -> int:
        """Click discovered load-more buttons up to max_clicks times.

        Returns number of clicks performed.
        """
        clicks = 0
        try:
            for _ in range(max_clicks):
                candidates = await ScrollIntelligence.detect_load_more_buttons(page)
                if not candidates:
                    break
                # click the first candidate
                sel = candidates[0].get("selector")
                try:
                    # try to click by selector; fall back to text click
                    try:
                        await page.click(sel)
                    except Exception:
                        await page.click(f"text={candidates[0].get('text')}")
                    clicks += 1
                    # allow dynamic content to load
                    await asyncio.sleep(wait_ms / 1000.0)
                except Exception:
                    break
        except Exception as e:
            logger.debug(f"auto_click_load_more failed: {e}")
        return clicks

    @staticmethod
    async def perform_infinite_scroll(page, item_selector: Optional[str] = None, max_scrolls: int = 10, scroll_step: int = 600, idle_rounds: int = 2) -> bool:
        """Scroll the page (or container) until no new items appear.

        - If item_selector is provided, uses element count as progress signal.
        - Stops early when no new items are detected for `idle_rounds` iterations.
        - Returns True when additional content was observed, False otherwise.
        """
        try:
            baseline = 0
            if item_selector:
                nodes = await page.query_selector_all(item_selector)
                baseline = len(nodes)

            round_no_new = 0
            # try to find a scrollable container first (prefer container over window)
            scroll_container_selector = None
            try:
                # prefer an explicit scrollable container (common patterns)
                candidates = await page.query_selector_all("*[style*='overflow'], div.scrollable, #list")
                if candidates and len(candidates) > 0:
                    # pick the largest candidate by bounding box height
                    best = None
                    best_h = 0
                    for c in candidates:
                        try:
                            bbox = await c.bounding_box()
                            if bbox and bbox.get('height', 0) > best_h:
                                best_h = bbox.get('height', 0)
                                best = c
                        except Exception:
                            continue
                    if best:
                        # compute a selector string for eval_on_selector use
                        scroll_container_selector = await page.evaluate("el => { return el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.className ? '.' + el.className.split(' ').join('.') : '') }", best)
            except Exception:
                scroll_container_selector = None

            for i in range(max_scrolls):
                if scroll_container_selector:
                    try:
                        await page.eval_on_selector(scroll_container_selector, f"el => el.scrollBy(0, {scroll_step})")
                    except Exception:
                        await page.evaluate(f"window.scrollBy(0, {scroll_step})")
                else:
                    await page.evaluate(f"window.scrollBy(0, {scroll_step})")

                await asyncio.sleep(0.3)

                # try network idle briefly
                try:
                    await page.wait_for_load_state('networkidle', timeout=1000)
                except Exception:
                    pass

                new_count = baseline
                if item_selector:
                    nodes = await page.query_selector_all(item_selector)
                    new_count = len(nodes)
                else:
                    # fallback using document height change
                    height_before = await page.evaluate("() => document.body.scrollHeight")
                    await asyncio.sleep(0.1)
                    height_after = await page.evaluate("() => document.body.scrollHeight")
                    if height_after > height_before:
                        # assume new content loaded
                        return True

                if new_count > baseline:
                    baseline = new_count
                    round_no_new = 0
                else:
                    round_no_new += 1

                if round_no_new >= idle_rounds:
                    break

            return baseline > 0
        except Exception as e:
            logger.debug(f"perform_infinite_scroll failed: {e}")
            return False

    @staticmethod
    async def auto_paginate(page, max_pages: int = 5) -> int:
        """Click pagination 'next' controls until end or max_pages reached.

        Returns number of pages visited (including the starting page).
        """
        visited = 0
        try:
            for _ in range(max_pages):
                visited += 1
                # try standard selectors
                next_btn = await page.query_selector("a[rel='next'], button:has-text('Next'), button:has-text('>'), .pagination .next")
                if not next_btn:
                    break
                # if disabled, stop
                disabled = await next_btn.get_attribute('disabled')
                if disabled:
                    break
                await next_btn.click()
                try:
                    await page.wait_for_load_state('networkidle', timeout=5000)
                except Exception:
                    await asyncio.sleep(0.5)
            return visited
        except Exception as e:
            logger.debug(f"auto_paginate failed: {e}")
            return visited

    @staticmethod
    async def detect_end_of_list(page, item_selector: str, attempts: int = 3, wait_ms: int = 500) -> bool:
        """Return True if end-of-list is reached (no new items after attempts)."""
        try:
            prev = len(await page.query_selector_all(item_selector))
            for _ in range(attempts):
                await asyncio.sleep(wait_ms / 1000.0)
                curr = len(await page.query_selector_all(item_selector))
                if curr > prev:
                    prev = curr
                    continue
                # no change this round
                return False
            return True
        except Exception as e:
            logger.debug(f"detect_end_of_list failed: {e}")
            return False
