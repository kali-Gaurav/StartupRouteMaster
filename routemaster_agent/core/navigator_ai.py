"""
Navigator AI — Intelligent Element Finding & Navigation

Autonomously finds and interacts with UI elements using:
- Visual label detection (Gemini + OCR)
- Semantic DOM analysis
- Context-aware element selection
- Fallback strategies
"""

import asyncio
from typing import Optional, List, Dict, Any, Tuple
from playwright.async_api import Page, Locator
from datetime import datetime
import logging
import time

# record selector successes/failures into selector registry
from routemaster_agent.intelligence.selector_registry import record_selector_result, get_primary_selector, get_entry

logger = logging.getLogger(__name__)


class NavigatorAI:
    """
    Smart element finding and navigation without hardcoded selectors.
    Uses Gemini vision + semantic analysis for robust automation.
    """

    def __init__(self, gemini_client=None, scene_recorder=None):
        """
        Initialize NavigatorAI.

        Args:
            gemini_client: GeminiClient instance for vision analysis
            scene_recorder: optional SceneRecorder instance to persist interaction traces
        """
        self.gemini = gemini_client
        self.navigation_memory = {}  # Cache successful paths
        self.failed_attempts = {}  # Track failures for learning
        self.scene_recorder = scene_recorder
        self._scene_step = 0
        # lazy import for scroll intelligence helper
        self._scroller = None

    async def find_element_by_visual_label(
        self, page: Page, label: str, element_type: str = "input", page_type: Optional[str] = None
    ) -> Optional[Locator]:
        """
        Find an element by its visible label text using visual analysis.

        Args:
            page: Playwright page object
            label: The label text to find (e.g., "Train Number", "From Station")
            element_type: Type of element (input, button, etc.)
            page_type: Optional registry key (e.g. 'ntes_schedule') to record selector success/failure

        Returns:
            Locator object or None if not found
        """
        logger.info(f"Finding element with label: '{label}'")

        # If page_type provided, try registry primary + backups first (fast path)
        if page_type:
            try:
                entry = get_entry(page_type)
                candidates = []
                primary = entry.get('primary', {}).get('selector') if entry else None
                if primary:
                    candidates.append(primary)
                for b in (entry.get('backups') or []):
                    sel = b.get('selector')
                    if sel and sel not in candidates:
                        candidates.append(sel)

                for sel in candidates:
                    try:
                        el = await page.query_selector(sel)
                        if el:
                            # record and return locator
                            try:
                                record_selector_result(page_type, sel, True)
                            except Exception:
                                pass
                            logger.info(f"✓ Found element via registry selector (selector={sel})")
                            return page.locator(sel)
                        else:
                            try:
                                record_selector_result(page_type, sel, False)
                            except Exception:
                                pass
                    except Exception:
                        # invalid selector format / evaluation error — skip
                        continue
            except Exception:
                pass

        # Strategy 1: Direct DOM search for associated labels
        try:
            # Look for label elements
            labels = await page.query_selector_all("label")
            for lbl in labels:
                text = await lbl.inner_text()
                if label.lower() in text.lower():
                    # Get associated input via 'for' attribute
                    lbl_for = await lbl.get_attribute("for")
                    if lbl_for:
                        element = await page.query_selector(f"#{lbl_for}")
                        if element:
                            selector = f"#{lbl_for}"
                            logger.info(f"✓ Found element via label[@for] association (selector={selector})")
                            if page_type:
                                try:
                                    record_selector_result(page_type, selector, True)
                                except Exception:
                                    pass
                            return page.locator(selector)

                    # Try next sibling input (label sibling)
                    input_elem = await lbl.query_selector(f"{element_type}")
                    if input_elem:
                        selector = f"label:has-text('{label}') >> {element_type}"
                        logger.info(f"✓ Found element as label sibling (selector={selector})")
                        if page_type:
                            try:
                                record_selector_result(page_type, selector, True)
                            except Exception:
                                pass
                        return page.locator(selector)
        except Exception as e:
            logger.debug(f"Label search failed: {e}")

        # Strategy 2: Visual analysis using Gemini
        if self.gemini:
            try:
                screenshot = await page.screenshot()
                detected_elements = await self.gemini.detect_form_fields(
                    screenshot, hint=label
                )

                if detected_elements:
                    for element_data in detected_elements:
                        if element_data.get("match_score", 0) > 0.7:
                            # Click at detected location to focus element
                            coords = element_data.get("coordinates")
                            if coords:
                                eid = element_data.get('element_id')
                                selector = f"[data-testid='{eid}']" if eid else None
                                if selector:
                                    try:
                                        await page.click(selector, position=coords, timeout=3000)
                                    except Exception:
                                        # fallback to click at coords
                                        await page.mouse.click(coords.get('x', 0), coords.get('y', 0))
                                logger.info(
                                    f"✓ Found element via visual detection (confidence: {element_data.get('match_score')})"
                                )
                                if page_type and selector:
                                    try:
                                        record_selector_result(page_type, selector, True)
                                    except Exception:
                                        pass
                                return page.locator(selector if selector else f"[data-testid='{eid}']")
            except Exception as e:
                logger.debug(f"Visual detection failed: {e}")

        # Strategy 3: Semantic DOM search
        try:
            all_inputs = await page.query_selector_all(element_type)
            for inp in all_inputs:
                # Check placeholder
                placeholder = await inp.get_attribute("placeholder")
                if placeholder and label.lower() in placeholder.lower():
                    selector = f"{element_type}[placeholder*='{placeholder}']"
                    logger.info(f"✓ Found element via placeholder match (selector={selector})")
                    if page_type:
                        try:
                            record_selector_result(page_type, selector, True)
                        except Exception:
                            pass
                    return page.locator(selector)

                # Check aria-label
                aria_label = await inp.get_attribute("aria-label")
                if aria_label and label.lower() in aria_label.lower():
                    selector = f"{element_type}[aria-label*='{aria_label}']"
                    logger.info(f"✓ Found element via aria-label match (selector={selector})")
                    if page_type:
                        try:
                            record_selector_result(page_type, selector, True)
                        except Exception:
                            pass
                    return page.locator(selector)

                # Check name attribute
                name = await inp.get_attribute("name")
                if name and label.lower() in name.lower():
                    selector = f"{element_type}[name='{name}']"
                    logger.info(f"✓ Found element via name match (selector={selector})")
                    if page_type:
                        try:
                            record_selector_result(page_type, selector, True)
                        except Exception:
                            pass
                    return page.locator(selector)
        except Exception as e:
            logger.debug(f"Semantic search failed: {e}")

        if page_type:
            try:
                primary = get_primary_selector(page_type)
                if primary:
                    record_selector_result(page_type, primary, False)
            except Exception:
                pass
        logger.warning(f"✗ Could not find element with label: '{label}'")
        return None

    async def find_button_by_intent(
        self, page: Page, intent: str, page_type: Optional[str] = None
    ) -> Optional[Locator]:
        """
        Find a button by its semantic meaning/intent.

        Args:
            page: Playwright page object
            intent: Button intent (e.g., "search", "next", "submit", "apply")
            page_type: Optional registry key to record selector success/failure

        Returns:
            Locator object or None
        """
        logger.info(f"Finding button with intent: '{intent}'")

        # If page_type provided, try registry selectors first
        if page_type:
            try:
                entry = get_entry(page_type)
                candidates = []
                primary = entry.get('primary', {}).get('selector') if entry else None
                if primary:
                    candidates.append(primary)
                for b in (entry.get('backups') or []):
                    sel = b.get('selector')
                    if sel and sel not in candidates:
                        candidates.append(sel)

                for sel in candidates:
                    try:
                        el = await page.query_selector(sel)
                        if el:
                            try:
                                record_selector_result(page_type, sel, True)
                            except Exception:
                                pass
                            logger.info(f"✓ Found button via registry selector (selector={sel})")
                            return page.locator(sel)
                        else:
                            try:
                                record_selector_result(page_type, sel, False)
                            except Exception:
                                pass
                    except Exception:
                        continue
            except Exception:
                pass

        # Strategy 1: Text match
        button_texts = [intent, intent.capitalize(), intent.upper()]
        for text in button_texts:
            button = await page.query_selector(
                f"button:has-text('{text}'), input[type=button][value='{text}']"
            )
            if button:
                selector = f"button:has-text('{text}')"
                logger.info(f"✓ Found button via text match: '{text}' (selector={selector})")
                if page_type:
                    try:
                        record_selector_result(page_type, selector, True)
                    except Exception:
                        pass
                return page.locator(selector)

        # Strategy 2: Visual analysis with Gemini
        if self.gemini:
            try:
                screenshot = await page.screenshot()
                buttons_analysis = await self.gemini.detect_buttons(
                    screenshot, hint=intent
                )

                if buttons_analysis:
                    for btn_data in buttons_analysis:
                        if btn_data.get("intent") == intent:
                            # Use detected button coordinates
                            await page.click(
                                position=btn_data.get("center_coordinates")
                            )
                            logger.info(f"✓ Found button via visual intent detection")
                            return await self._get_clicked_element(page)
            except Exception as e:
                logger.debug(f"Button visual detection failed: {e}")

        # Strategy 3: ARIA labels
        try:
            buttons = await page.query_selector_all("button, [role=button]")
            for btn in buttons:
                aria_label = await btn.get_attribute("aria-label")
                if aria_label and intent.lower() in aria_label.lower():
                    selector = f"button[aria-label*='{aria_label}']"
                    logger.info(f"✓ Found button via aria-label: {aria_label} (selector={selector})")
                    if page_type:
                        try:
                            record_selector_result(page_type, selector, True)
                        except Exception:
                            pass
                    return page.locator(selector)

                text = await btn.inner_text()
                if intent.lower() in text.lower():
                    selector = f"button:has-text('{text}')"
                    logger.info(f"✓ Found button via text content: {text} (selector={selector})")
                    if page_type:
                        try:
                            record_selector_result(page_type, selector, True)
                        except Exception:
                            pass
                    return page.locator(selector)
        except Exception as e:
            logger.debug(f"ARIA search failed: {e}")

        if page_type:
            try:
                primary = get_primary_selector(page_type)
                if primary:
                    record_selector_result(page_type, primary, False)
            except Exception:
                pass
        logger.warning(f"✗ Could not find button with intent: '{intent}'")
        return None

    async def find_table_on_page(self, page: Page) -> Optional[Dict[str, Any]]:
        """
        Detect and analyze table structure on page.

        Returns:
            {
                'headers': [...],
                'rows': [...],
                'row_count': int,
                'columns_count': int,
                'element': Locator
            }
        """
        logger.info("Scanning page for tables...")

        try:
            # Check for HTML tables first
            tables = await page.query_selector_all("table")
            if tables:
                for table in tables:
                    table_data = await self._analyze_html_table(page, table)
                    if table_data and table_data.get("row_count", 0) > 0:
                        logger.info(
                            f"✓ Found HTML table with {table_data['row_count']} rows"
                        )
                        return table_data

            # Fallback: Use Gemini for visual table detection
            if self.gemini:
                screenshot = await page.screenshot()
                table_analysis = await self.gemini.detect_tables(screenshot)

                if table_analysis:
                    logger.info(f"✓ Found table via visual detection")
                    return table_analysis

        except Exception as e:
            logger.error(f"Table detection failed: {e}")

        logger.warning("✗ No table found on page")
        return None

    async def fill_input_and_trigger_event(
        self, page: Page, element: Locator, value: str, delay_ms: int = 100, page_type: Optional[str] = None
    ) -> bool:
        """
        Fill input field with human-like typing and trigger change events.

        Args:
            page: Playwright page object
            element: Locator of input element
            value: Value to fill
            delay_ms: Delay between keystrokes (simulates human typing)
            page_type: Optional registry key to record selector success/failure

        Returns:
            True if successful
        """
        selector = None
        el_handle = None
        is_locator = hasattr(element, "element_handle")
        try:
            start_time = time.monotonic()
            # obtain an ElementHandle for robust operations
            if is_locator:
                try:
                    el_handle = await element.element_handle()
                except Exception:
                    el_handle = None
            else:
                # element may already be an ElementHandle
                el_handle = element

            # compute friendly selector for metrics/registry when possible
            if el_handle:
                try:
                    info = await page.evaluate(
                        '(el) => ({ tag: el.tagName.toLowerCase(), id: el.id || "", name: el.name || "" })',
                        el_handle,
                    )
                    selector = info.get('tag', '')
                    if info.get('id'):
                        selector += f"#{info['id']}"
                    if info.get('name'):
                        selector += f"[name='{info['name']}']"
                except Exception:
                    selector = None

            # Focus element (use evaluate on handle for ElementHandle)
            if is_locator and hasattr(element, 'focus'):
                await element.focus()
            elif el_handle:
                await page.evaluate("el => el.focus()", el_handle)
            await asyncio.sleep(0.1)

            # Clear existing value
            if is_locator and hasattr(element, 'fill'):
                await element.fill("")
            elif el_handle:
                await page.evaluate("el => { if ('value' in el) el.value = ''; else el.innerText = ''; }", el_handle)
            await asyncio.sleep(0.1)

            # Type with delays (human-like)
            if is_locator and hasattr(element, 'type'):
                await element.type(value, delay=delay_ms)
            elif el_handle:
                # fallback: set value directly and dispatch input event
                await page.evaluate("(el, v) => { if ('value' in el) { el.value = v; el.dispatchEvent(new Event('input')); } else { el.innerText = v; } }", el_handle, value)
            await asyncio.sleep(0.2)

            # Trigger change/input events that JS handlers might expect
            if is_locator and hasattr(element, 'evaluate'):
                try:
                    await element.evaluate("el => el.dispatchEvent(new Event('change'))")
                    await element.evaluate("el => el.dispatchEvent(new Event('input'))")
                except Exception:
                    pass
            elif el_handle:
                try:
                    await page.evaluate("el => { el.dispatchEvent(new Event('change')); el.dispatchEvent(new Event('input')); }", el_handle)
                except Exception:
                    pass

                logger.info(f"✓ Filled input with value: '{value}' (selector={selector})")
            if page_type and selector:
                try:
                    record_selector_result(page_type, selector, True)
                except Exception:
                    pass

            # record scene step if recorder available (include timing + selector metadata)
            try:
                if self.scene_recorder:
                    elapsed_ms = int((time.monotonic() - start_time) * 1000) if 'start_time' in locals() else None
                    meta = {
                        "strategy": "dom" if selector else None,
                        "selector_confidence": None,
                        "time_to_success_ms": elapsed_ms,
                        "success": True,
                    }
                    self._scene_step += 1
                    await self.scene_recorder.record_step(page, {"type": "input", "selector": selector, "value": value}, self._scene_step, metadata=meta)
            except Exception:
                pass

            return True

        except Exception as e:
            logger.error(f"Input fill failed: {e}")
            if page_type:
                try:
                    # if we failed and have a primary registered, record a failure for it
                    primary = get_primary_selector(page_type)
                    if primary:
                        record_selector_result(page_type, primary, False)
                    elif selector:
                        record_selector_result(page_type, selector, False)
                except Exception:
                    pass
            return False

    async def wait_for_element_interactive(
        self, page: Page, selector: str, timeout_ms: int = 10000
    ) -> bool:
        """
        Wait for element to appear and be interactive.

        Args:
            page: Playwright page object
            selector: CSS selector or Playwright selector
            timeout_ms: Maximum wait time

        Returns:
            True if element became interactive
        """
        try:
            await page.wait_for_selector(selector, timeout=timeout_ms)
            element = page.locator(selector)
            await element.wait_for(state="visible", timeout=timeout_ms)

            # Wait for element to be enabled
            for _ in range(10):
                if await element.is_enabled():
                    return True
                await asyncio.sleep(0.5)

            return True
        except Exception as e:
            logger.warning(f"Element wait timeout: {e}")
            return False

    async def wait_for_dom_change(self, page: Page, baseline_selector: str = None, timeout_ms: int = 5000) -> bool:
        """Wait for DOM changes.

        - If baseline_selector provided, waits until the number of matching elements changes.
        - Otherwise waits until page.content() length changes.
        """
        try:
            if baseline_selector:
                initial = await page.query_selector_all(baseline_selector)
                initial_count = len(initial)
                end_time = __import__('time').time() + (timeout_ms / 1000.0)
                while __import__('time').time() < end_time:
                    current = await page.query_selector_all(baseline_selector)
                    if len(current) != initial_count:
                        return True
                    await asyncio.sleep(0.25)
                return False

            # fallback: monitor page content length
            initial = await page.content()
            end_time = __import__('time').time() + (timeout_ms / 1000.0)
            while __import__('time').time() < end_time:
                current = await page.content()
                if len(current) != len(initial):
                    return True
                await asyncio.sleep(0.25)
            return False
        except Exception as e:
            logger.debug(f"wait_for_dom_change failed: {e}")
            return False

    async def wait_for_network_idle(self, page: Page, timeout_ms: int = 5000) -> bool:
        """Wait for network to become idle (wrapper around Playwright's networkidle)."""
        try:
            await page.wait_for_load_state('networkidle', timeout=timeout_ms)
            return True
        except Exception as e:
            logger.debug(f"wait_for_network_idle: {e}")
            return False
    async def handle_dropdown_selection(
        self, page: Page, dropdown_selector: str, option_text: str, page_type: Optional[str] = None
    ) -> bool:
        """
        Handle dropdown/select element selection.

        Args:
            page: Playwright page object
            dropdown_selector: CSS selector for dropdown
            option_text: Text of option to select
            page_type: Optional registry key to record selector success/failure

        Returns:
            True if successfully selected
        """
        try:
            dropdown = page.locator(dropdown_selector)
            tag = None
            try:
                tag = (await dropdown.evaluate("el => el.tagName.toLowerCase()"))
            except Exception:
                tag = None

            # Native <select> handling
            if tag == 'select':
                try:
                    await dropdown.select_option(label=option_text)
                    logger.info(f"✓ Selected native select option: '{option_text}' (selector={dropdown_selector})")
                    if page_type:
                        try:
                            record_selector_result(page_type, dropdown_selector, True)
                        except Exception:
                            pass
                    return True
                except Exception as e:
                    logger.error(f"Native select failed: {e}")
                    if page_type:
                        try:
                            record_selector_result(page_type, dropdown_selector, False)
                        except Exception:
                            pass
                    return False

            # Otherwise treat as custom dropdown
            try:
                await dropdown.click()
                await asyncio.sleep(0.3)

                # Wait for options to appear
                await page.wait_for_selector(
                    f"{dropdown_selector} + [role=listbox] [role=option], {dropdown_selector} ~ ul li, .dropdown-menu li",
                    timeout=5000,
                )

                # Click matching option
                start_time = time.monotonic()
                await page.click(f"text={option_text}")
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                logger.info(f"✓ Selected dropdown option: '{option_text}' (selector={dropdown_selector})")
                if page_type:
                    try:
                        record_selector_result(page_type, dropdown_selector, True)
                    except Exception:
                        pass

                # record scene step (with metadata)
                try:
                    if self.scene_recorder:
                        meta = {"strategy": "dom", "selector_confidence": None, "time_to_success_ms": elapsed_ms, "success": True}
                        self._scene_step += 1
                        await self.scene_recorder.record_step(page, {"type": "select", "selector": dropdown_selector, "value": option_text}, self._scene_step, metadata=meta)
                except Exception:
                    pass

                return True
            except Exception as e:
                logger.error(f"Dropdown selection failed: {e}")
                if page_type:
                    try:
                        record_selector_result(page_type, dropdown_selector, False)
                    except Exception:
                        pass
                return False

        except Exception as e:
            logger.error(f"Dropdown selection failed: {e}")
            if page_type:
                try:
                    record_selector_result(page_type, dropdown_selector, False)
                except Exception:
                    pass
            return False

    async def navigate_pagination(
        self, page: Page, max_pages: int = 5, page_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Autonomously navigate multi-page results.

        Args:
            page: Playwright page object
            max_pages: Maximum pages to fetch
            page_type: Optional registry key to record selector success/failure

        Returns:
            List of extracted data from each page
        """
        results = []
        pages_visited = 0

        while pages_visited < max_pages:
            try:
                # Extract from current page
                data = await self._extract_current_page(page)
                results.append(data)
                pages_visited += 1

                logger.info(f"Extracted page {pages_visited}")

                # Find and click next button
                next_button = await self.find_button_by_intent(page, "next", page_type=page_type)
                if not next_button:
                    logger.info("No more pages - reached end")
                    # record primary failure if page_type provided
                    if page_type:
                        try:
                            primary = get_primary_selector(page_type)
                            if primary:
                                record_selector_result(page_type, primary, False)
                        except Exception:
                            pass
                    break

                # Check if button is disabled
                disabled = await next_button.get_attribute("disabled")
                if disabled:
                    logger.info("Next button disabled - reached end")
                    break

                # try to derive selector for metrics
                try:
                    sel = await page.evaluate("el => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.className ? '.' + el.className.split(' ').join('.') : '')", await next_button.element_handle())
                except Exception:
                    sel = None

                start_click = time.monotonic()
                await next_button.click()
                await page.wait_for_load_state("networkidle", timeout=10000)
                elapsed_click_ms = int((time.monotonic() - start_click) * 1000)

                if page_type and sel:
                    try:
                        record_selector_result(page_type, sel, True)
                    except Exception:
                        pass

                # record pagination step (with metadata)
                try:
                    if self.scene_recorder:
                        meta = {"strategy": "dom" if sel else None, "selector_confidence": None, "time_to_success_ms": elapsed_click_ms, "success": True}
                        self._scene_step += 1
                        await self.scene_recorder.record_step(page, {"type": "click", "selector": sel or 'next_button', "action": 'paginate'}, self._scene_step, metadata=meta)
                except Exception:
                    pass

            except Exception as e:
                logger.error(f"Pagination error: {e}")
                if page_type:
                    try:
                        primary = get_primary_selector(page_type)
                        if primary:
                            record_selector_result(page_type, primary, False)
                    except Exception:
                        pass
                break

        logger.info(f"✓ Visited {pages_visited} pages")
        return results

    async def handle_dynamic_content_loading(
        self, page: Page, wait_for_selector: str = None, timeout_ms: int = 15000
    ) -> bool:
        """
        Wait for dynamic content to load (AJAX, infinite scroll, etc.).

        Args:
            page: Playwright page object
            wait_for_selector: Wait for specific element to appear
            timeout_ms: Maximum wait time

        Returns:
            True if content loaded
        """
        try:
            # Wait for network idle
            await page.wait_for_load_state("networkidle", timeout=timeout_ms)

            # If specific selector provided, wait for it
            if wait_for_selector:
                await page.wait_for_selector(wait_for_selector, timeout=timeout_ms)

            logger.info("✓ Dynamic content loaded")
            return True

        except Exception as e:
            logger.warning(f"Content load timeout: {e}")
            return False

    async def scroll_to_element(self, page: Page, element: Locator) -> bool:
        """
        Scroll element into view.

        Args:
            page: Playwright page object
            element: Locator to scroll to

        Returns:
            True if successful
        """
        try:
            await element.scroll_into_view_if_needed()
            logger.info("✓ Scrolled element into view")
            return True
        except Exception as e:
            logger.error(f"Scroll failed: {e}")
            return False

    async def smart_scroll(
        self,
        page: Page,
        container_selector: str = None,
        wait_for_selector: str = None,
        max_scrolls: int = 5,
        scroll_step: int = 400,
        timeout_ms: int = 10000,
    ) -> bool:
        """Scroll intelligently on the page or inside a container.

        - If `container_selector` provided, scroll that element; otherwise scroll window.
        - If `wait_for_selector` provided, wait for it to appear after each scroll.
        - Returns True when new content appears or `wait_for_selector` is found.
        """
        # defer import to avoid circulars in tests
        if self._scroller is None:
            from routemaster_agent.core.scroll_intelligence import ScrollIntelligence
            self._scroller = ScrollIntelligence()

        try:
            # prefer scroller.perform_infinite_scroll when item selector provided
            if wait_for_selector:
                return await self._scroller.perform_infinite_scroll(page, item_selector=wait_for_selector, max_scrolls=max_scrolls, scroll_step=scroll_step)

            # use the simpler behavior otherwise
            for i in range(max_scrolls):
                if container_selector:
                    await page.eval_on_selector(container_selector, f"el => el.scrollBy(0, {scroll_step})")
                else:
                    await page.evaluate(f"window.scrollBy(0, {scroll_step})")

                # allow dynamic content to load
                try:
                    await page.wait_for_load_state('networkidle', timeout=int(timeout_ms / max_scrolls))
                except Exception:
                    pass

                # small pause between scrolls
                await asyncio.sleep(0.25)

            logger.info("✓ smart_scroll: completed scrolling attempts")
            return True

        except Exception as e:
            logger.error(f"smart_scroll failed: {e}")
            return False
    async def get_page_structure(self, page: Page) -> Dict[str, Any]:
        """
        Analyze current page structure and layout.

        Returns:
            {
                'title': str,
                'url': str,
                'form_fields': [...],
                'buttons': [...],
                'tables': [...],
                'text_blocks': [...]
            }
        """
        try:
            structure = {
                "title": await page.title(),
                "url": page.url,
                "form_fields": [],
                "buttons": [],
                "tables": [],
                "headings": [],
            }

            # Get form fields
            inputs = await page.query_selector_all("input, textarea, select")
            for inp in inputs:
                try:
                    label_elem = await inp.query_selector("..")
                    label_text = await label_elem.inner_text() if label_elem else ""
                    structure["form_fields"].append(
                        {
                            "type": await inp.get_attribute("type"),
                            "name": await inp.get_attribute("name"),
                            "placeholder": await inp.get_attribute("placeholder"),
                            "label": label_text,
                        }
                    )
                except:
                    pass

            # Get buttons
            buttons = await page.query_selector_all("button")
            for btn in buttons:
                try:
                    structure["buttons"].append(
                        {
                            "text": await btn.inner_text(),
                            "aria_label": await btn.get_attribute("aria-label"),
                        }
                    )
                except:
                    pass

            # Get headings
            headings = await page.query_selector_all("h1, h2, h3")
            for heading in headings:
                try:
                    structure["headings"].append(await heading.inner_text())
                except:
                    pass

            logger.info(f"✓ Analyzed page structure")
            return structure

        except Exception as e:
            logger.error(f"Structure analysis failed: {e}")
            return {}

    # Helper methods

    async def _analyze_html_table(
        self, page: Page, table_element
    ) -> Optional[Dict[str, Any]]:
        """Analyze HTML table structure."""
        try:
            headers = []
            rows = []

            # Get headers
            header_cells = await table_element.query_selector_all("thead th, thead td")
            for cell in header_cells:
                headers.append(await cell.inner_text())

            # Get rows
            body_rows = await table_element.query_selector_all("tbody tr")
            for row in body_rows:
                cells = await row.query_selector_all("td")
                row_data = []
                for cell in cells:
                    row_data.append(await cell.inner_text())
                rows.append(row_data)

            return {
                "headers": headers,
                "rows": rows,
                "row_count": len(rows),
                "columns_count": len(headers),
                "element": table_element,
            }

        except Exception as e:
            logger.debug(f"Table analysis failed: {e}")
            return None

    async def _extract_current_page(self, page: Page) -> Dict[str, Any]:
        """Extract data from current page (to be overridden by subclasses)."""
        return {"url": page.url, "timestamp": datetime.utcnow().isoformat()}

    async def _get_clicked_element(self, page: Page) -> Optional[Locator]:
        """Get reference to last clicked element."""
        try:
            return page.locator(":focus")
        except:
            return None
