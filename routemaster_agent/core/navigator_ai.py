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

logger = logging.getLogger(__name__)


class NavigatorAI:
    """
    Smart element finding and navigation without hardcoded selectors.
    Uses Gemini vision + semantic analysis for robust automation.
    """

    def __init__(self, gemini_client=None):
        """
        Initialize NavigatorAI.

        Args:
            gemini_client: GeminiClient instance for vision analysis
        """
        self.gemini = gemini_client
        self.navigation_memory = {}  # Cache successful paths
        self.failed_attempts = {}  # Track failures for learning

    async def find_element_by_visual_label(
        self, page: Page, label: str, element_type: str = "input"
    ) -> Optional[Locator]:
        """
        Find an element by its visible label text using visual analysis.

        Args:
            page: Playwright page object
            label: The label text to find (e.g., "Train Number", "From Station")
            element_type: Type of element (input, button, etc.)

        Returns:
            Locator object or None if not found
        """
        logger.info(f"Finding element with label: '{label}'")

        # Strategy 1: Direct DOM search for associated labels
        try:
            # Look for label elements
            labels = await page.query_selector_all("label")
            for lbl in labels:
                text = await lbl.inner_text()
                if label.lower() in text.lower():
                    # Get associated input
                    lbl_for = await lbl.get_attribute("for")
                    if lbl_for:
                        element = await page.query_selector(f"#{lbl_for}")
                        if element:
                            logger.info(f"✓ Found element via label[@for] association")
                            return page.locator(f"#{lbl_for}")

                    # Try next sibling
                    input_elem = await lbl.query_selector(f"{element_type}")
                    if input_elem:
                        logger.info(f"✓ Found element as label sibling")
                        return page.locator(
                            f"label:has-text('{label}') >> {element_type}"
                        )
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
                                await page.click(
                                    f"[data-testid='{element_data.get('element_id')}']",
                                    position=coords,
                                    timeout=3000,
                                )
                                logger.info(
                                    f"✓ Found element via visual detection (confidence: {element_data.get('match_score')})"
                                )
                                return page.locator(
                                    f"[data-testid='{element_data.get('element_id')}']"
                                )
            except Exception as e:
                logger.debug(f"Visual detection failed: {e}")

        # Strategy 3: Semantic DOM search
        try:
            all_inputs = await page.query_selector_all(element_type)
            for inp in all_inputs:
                # Check placeholder
                placeholder = await inp.get_attribute("placeholder")
                if placeholder and label.lower() in placeholder.lower():
                    logger.info(f"✓ Found element via placeholder match")
                    return page.locator(inp)

                # Check aria-label
                aria_label = await inp.get_attribute("aria-label")
                if aria_label and label.lower() in aria_label.lower():
                    logger.info(f"✓ Found element via aria-label match")
                    return page.locator(inp)

                # Check name attribute
                name = await inp.get_attribute("name")
                if name and label.lower() in name.lower():
                    logger.info(f"✓ Found element via name match")
                    return page.locator(inp)
        except Exception as e:
            logger.debug(f"Semantic search failed: {e}")

        logger.warning(f"✗ Could not find element with label: '{label}'")
        return None

    async def find_button_by_intent(
        self, page: Page, intent: str
    ) -> Optional[Locator]:
        """
        Find a button by its semantic meaning/intent.

        Args:
            page: Playwright page object
            intent: Button intent (e.g., "search", "next", "submit", "apply")

        Returns:
            Locator object or None
        """
        logger.info(f"Finding button with intent: '{intent}'")

        # Strategy 1: Text match
        button_texts = [intent, intent.capitalize(), intent.upper()]
        for text in button_texts:
            button = await page.query_selector(
                f"button:has-text('{text}'), input[type=button][value='{text}']"
            )
            if button:
                logger.info(f"✓ Found button via text match: '{text}'")
                return page.locator(f"button:has-text('{text}')")

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
                    logger.info(f"✓ Found button via aria-label: {aria_label}")
                    return page.locator(btn)

                text = await btn.inner_text()
                if intent.lower() in text.lower():
                    logger.info(f"✓ Found button via text content: {text}")
                    return page.locator(btn)
        except Exception as e:
            logger.debug(f"ARIA search failed: {e}")

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
        self, page: Page, element: Locator, value: str, delay_ms: int = 100
    ) -> bool:
        """
        Fill input field with human-like typing and trigger change events.

        Args:
            page: Playwright page object
            element: Locator of input element
            value: Value to fill
            delay_ms: Delay between keystrokes (simulates human typing)

        Returns:
            True if successful
        """
        try:
            # Focus element
            await element.focus()
            await asyncio.sleep(0.1)

            # Clear existing value
            await element.fill("")
            await asyncio.sleep(0.1)

            # Type with delays (human-like)
            await element.type(value, delay=delay_ms)
            await asyncio.sleep(0.2)

            # Trigger change events that JS handlers might expect
            await element.evaluate("el => el.dispatchEvent(new Event('change'))")
            await element.evaluate("el => el.dispatchEvent(new Event('input'))")

            logger.info(f"✓ Filled input with value: '{value}'")
            return True

        except Exception as e:
            logger.error(f"Input fill failed: {e}")
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

    async def handle_dropdown_selection(
        self, page: Page, dropdown_selector: str, option_text: str
    ) -> bool:
        """
        Handle dropdown/select element selection.

        Args:
            page: Playwright page object
            dropdown_selector: CSS selector for dropdown
            option_text: Text of option to select

        Returns:
            True if successfully selected
        """
        try:
            dropdown = page.locator(dropdown_selector)
            await dropdown.click()
            await asyncio.sleep(0.3)

            # Wait for options to appear
            await page.wait_for_selector(
                f"{dropdown_selector} + [role=listbox] [role=option], {dropdown_selector} ~ ul li, .dropdown-menu li",
                timeout=5000,
            )

            # Click matching option
            await page.click(f"text={option_text}")
            logger.info(f"✓ Selected dropdown option: '{option_text}'")
            return True

        except Exception as e:
            logger.error(f"Dropdown selection failed: {e}")
            return False

    async def navigate_pagination(
        self, page: Page, max_pages: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Autonomously navigate multi-page results.

        Args:
            page: Playwright page object
            max_pages: Maximum pages to fetch

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
                next_button = await self.find_button_by_intent(page, "next")
                if not next_button:
                    logger.info("No more pages - reached end")
                    break

                # Check if button is disabled
                disabled = await next_button.get_attribute("disabled")
                if disabled:
                    logger.info("Next button disabled - reached end")
                    break

                await next_button.click()
                await page.wait_for_load_state("networkidle", timeout=10000)

            except Exception as e:
                logger.error(f"Pagination error: {e}")
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
