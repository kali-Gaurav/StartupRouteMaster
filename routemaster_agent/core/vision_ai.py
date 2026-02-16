"""
Vision AI — Screenshot Understanding & Visual Analysis

Analyzes page screenshots to:
- Detect page structure (tables, forms, lists)
- Identify clickable elements visually
- Understand field layouts
- Detect layout changes
- Extract text via OCR
"""

import asyncio
from typing import Optional, List, Dict, Any
from playwright.async_api import Page
import logging

logger = logging.getLogger(__name__)


class VisionAI:
    """
    Visual page analysis using Gemini vision API.
    Understands page layouts without relying on HTML structure.
    """

    def __init__(self, gemini_client=None):
        """
        Initialize VisionAI.

        Args:
            gemini_client: GeminiClient instance for vision analysis
        """
        self.gemini = gemini_client
        self.page_layouts_cache = {}  # Cache detected layouts

    async def analyze_page_structure(self, page: Page) -> Dict[str, Any]:
        """
        Detect all visual elements on page: tables, forms, buttons, text blocks.

        Args:
            page: Playwright page object

        Returns:
            {
                'tables': [{'location': {...}, 'size': {...}}, ...],
                'forms': [...],
                'buttons': [...],
                'text_regions': [...],
                'layout_type': 'form' | 'table' | 'list' | 'mixed',
                'confidence': 0.0-1.0
            }
        """
        logger.info("Analyzing page visual structure...")

        try:
            screenshot = await page.screenshot()

            if not self.gemini:
                logger.warning("Gemini client not available - using HTML analysis only")
                return await self._analyze_html_structure(page)

            # Use Gemini vision to analyze layout
            analysis = await self.gemini.analyze_page_layout(
                screenshot=screenshot,
                context=f"Page URL: {page.url}"
            )

            logger.info(
                f"✓ Detected page structure: {analysis.get('layout_type', 'unknown')}"
            )
            return analysis

        except Exception as e:
            logger.error(f"Page structure analysis failed: {e}")
            return await self._analyze_html_structure(page)

    async def detect_table_structure(
        self, page: Page, hint: str = "schedule"
    ) -> Optional[Dict[str, Any]]:
        """
        Detect and analyze table structure.

        Args:
            page: Playwright page object
            hint: Context hint (e.g., "train schedule", "flight results")

        Returns:
            {
                'headers': ['Station', 'Arrival', 'Departure', ...],
                'row_count': int,
                'column_count': int,
                'columns': [{'name': str, 'type': str, 'region': {...}}, ...],
                'rows': [{'region': {...}, 'cells': [...]}, ...],
                'confidence': 0.0-1.0,
                'is_paginated': bool,
                'next_page_button': {...} | null
            }
        """
        logger.info(f"Detecting table structure (hint: {hint})...")

        try:
            # First try HTML table detection
            html_tables = await page.query_selector_all("table")
            if html_tables:
                table_data = await self._analyze_html_table_structure(
                    page, html_tables[0]
                )
                if table_data:
                    logger.info(f"✓ Detected HTML table: {len(table_data['rows'])} rows")
                    return table_data

            # Use visual detection for non-HTML tables
            if self.gemini:
                screenshot = await page.screenshot()
                html_content = await page.content()

                table_structure = await self.gemini.extract_table_structure(
                    screenshot=screenshot,
                    html=html_content,
                    hint=hint
                )

                if table_structure and table_structure.get("row_count", 0) > 0:
                    logger.info(
                        f"✓ Detected visual table: {table_structure['row_count']} rows"
                    )
                    return table_structure

        except Exception as e:
            logger.error(f"Table structure detection failed: {e}")

        logger.warning("✗ No table structure detected")
        return None

    async def locate_data_field(
        self, page: Page, field_name: str, context: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        Locate where a specific data field is displayed on screen.

        Args:
            page: Playwright page object
            field_name: Name of field (e.g., "Train Name", "Platform")
            context: Additional context (e.g., "in schedule table")

        Returns:
            {
                'field_name': str,
                'location': {'x': int, 'y': int},
                'size': {'width': int, 'height': int},
                'element_type': 'text' | 'input' | 'span' | etc,
                'value': str | None,
                'confidence': 0.0-1.0
            }
        """
        logger.info(f"Locating field: '{field_name}'")

        try:
            # First try HTML attribute matching
            html_result = await self._find_field_in_html(page, field_name)
            if html_result:
                logger.info(f"✓ Found field in HTML: {field_name}")
                return html_result

            # Use visual detection
            if self.gemini:
                screenshot = await page.screenshot()

                field_location = await self.gemini.find_field_on_screen(
                    screenshot=screenshot,
                    field_name=field_name,
                    context=context or "webpage"
                )

                if field_location and field_location.get("confidence", 0) > 0.5:
                    logger.info(
                        f"✓ Found field visually: {field_name} (confidence: {field_location.get('confidence')})"
                    )
                    return field_location

        except Exception as e:
            logger.error(f"Field location failed: {e}")

        logger.warning(f"✗ Could not locate field: {field_name}")
        return None

    async def detect_form_fields(self, page: Page) -> List[Dict[str, Any]]:
        """
        Detect all form fields on page with visual analysis.

        Returns:
            [
                {
                    'label': str,
                    'type': 'text' | 'number' | 'date' | 'select' | etc,
                    'required': bool,
                    'placeholder': str | None,
                    'location': {...}
                },
                ...
            ]
        """
        logger.info("Detecting form fields...")

        try:
            fields = []

            # Get HTML form fields
            inputs = await page.query_selector_all("input, textarea, select")
            for inp in inputs:
                try:
                    field_data = {
                        "type": await inp.get_attribute("type") or "text",
                        "name": await inp.get_attribute("name"),
                        "placeholder": await inp.get_attribute("placeholder"),
                        "required": await inp.get_attribute("required") is not None,
                        "value": await inp.get_attribute("value"),
                    }

                    # Try to find associated label
                    label_text = ""
                    name = field_data.get("name")
                    if name:
                        label = await page.query_selector(f"label[for='{name}']")
                        if label:
                            label_text = await label.inner_text()

                    field_data["label"] = label_text
                    fields.append(field_data)

                except Exception as e:
                    logger.debug(f"Failed to analyze field: {e}")

            # Use visual detection for additional fields
            if self.gemini:
                screenshot = await page.screenshot()
                visual_fields = await self.gemini.detect_form_fields(
                    screenshot=screenshot
                )
                if visual_fields:
                    fields.extend(visual_fields)

            logger.info(f"✓ Detected {len(fields)} form fields")
            return fields

        except Exception as e:
            logger.error(f"Form field detection failed: {e}")
            return []

    async def detect_clickable_elements(self, page: Page) -> List[Dict[str, Any]]:
        """
        Detect all clickable UI elements (buttons, links, etc.).

        Returns:
            [
                {
                    'element_type': 'button' | 'link' | 'checkbox' | etc,
                    'text': str,
                    'aria_label': str | None,
                    'location': {'x': int, 'y': int},
                    'intent': str | None  # 'search', 'next', 'submit', etc
                },
                ...
            ]
        """
        logger.info("Detecting clickable elements...")

        try:
            elements = []

            # Get buttons
            buttons = await page.query_selector_all("button, [role=button]")
            for btn in buttons:
                try:
                    text = await btn.inner_text()
                    if text:  # Only include buttons with text
                        elements.append(
                            {
                                "element_type": "button",
                                "text": text,
                                "aria_label": await btn.get_attribute("aria-label"),
                            }
                        )
                except:
                    pass

            # Get links
            links = await page.query_selector_all("a")
            for link in links:
                try:
                    text = await link.inner_text()
                    if text:
                        elements.append(
                            {
                                "element_type": "link",
                                "text": text,
                                "href": await link.get_attribute("href"),
                            }
                        )
                except:
                    pass

            # Use visual detection
            if self.gemini:
                screenshot = await page.screenshot()
                visual_elements = await self.gemini.detect_buttons(
                    screenshot=screenshot
                )
                if visual_elements:
                    elements.extend(visual_elements)

            logger.info(f"✓ Detected {len(elements)} clickable elements")
            return elements

        except Exception as e:
            logger.error(f"Clickable element detection failed: {e}")
            return []

    async def detect_layout_changes(
        self, page: Page, previous_screenshot: Optional[bytes] = None
    ) -> Dict[str, Any]:
        """
        Detect if page layout has changed (useful for detecting site updates).

        Args:
            page: Playwright page object
            previous_screenshot: Previous screenshot for comparison

        Returns:
            {
                'changed': bool,
                'change_type': 'layout' | 'content' | 'styling' | None,
                'changes': [...],
                'confidence': 0.0-1.0,
                'recommendation': str
            }
        """
        logger.info("Checking for layout changes...")

        try:
            if not previous_screenshot:
                logger.info("No previous screenshot for comparison")
                return {"changed": False, "confidence": 0.0}

            current_screenshot = await page.screenshot()

            if not self.gemini:
                # Simple binary comparison
                changed = current_screenshot != previous_screenshot
                return {
                    "changed": changed,
                    "change_type": "unknown" if changed else None,
                    "confidence": 0.5,
                }

            # Use Gemini to analyze differences
            changes = await self.gemini.detect_layout_changes(
                current_screenshot=current_screenshot,
                previous_screenshot=previous_screenshot,
            )

            logger.info(
                f"Layout change detected: {changes.get('changed', False)} (confidence: {changes.get('confidence', 0)})"
            )
            return changes

        except Exception as e:
            logger.error(f"Layout change detection failed: {e}")
            return {"changed": False, "confidence": 0.0}

    async def extract_text_from_region(
        self, page: Page, region: Dict[str, int]
    ) -> Optional[str]:
        """
        Extract text from a specific region of page using OCR.

        Args:
            page: Playwright page object
            region: {'x': int, 'y': int, 'width': int, 'height': int}

        Returns:
            Extracted text or None
        """
        logger.info(f"Extracting text from region: {region}")

        try:
            if not self.gemini:
                logger.warning("Gemini not available for OCR")
                return None

            screenshot = await page.screenshot()

            # Crop screenshot to region
            cropped = await self.gemini.crop_image(screenshot, region)

            # Extract text using OCR
            text = await self.gemini.extract_text_via_ocr(cropped)

            logger.info(f"✓ Extracted text from region: {text[:50]}...")
            return text

        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            return None

    async def understand_page_intent(self, page: Page) -> Dict[str, Any]:
        """
        Analyze page and understand its purpose/intent.

        Returns:
            {
                'page_type': 'search_form' | 'results' | 'login' | 'booking' | etc,
                'primary_intent': str,
                'expected_fields': [str, ...],
                'expected_actions': [str, ...],
                'confidence': 0.0-1.0
            }
        """
        logger.info("Understanding page intent...")

        try:
            if not self.gemini:
                logger.warning("Gemini not available for intent analysis")
                return {"page_type": "unknown", "confidence": 0.0}

            screenshot = await page.screenshot()
            html = await page.content()

            intent = await self.gemini.analyze_page_intent(
                screenshot=screenshot, html=html, url=page.url
            )

            logger.info(f"✓ Page intent: {intent.get('page_type', 'unknown')}")
            return intent

        except Exception as e:
            logger.error(f"Intent analysis failed: {e}")
            return {"page_type": "unknown", "confidence": 0.0}

    # Helper methods

    async def _analyze_html_structure(self, page: Page) -> Dict[str, Any]:
        """Analyze page structure from HTML."""
        try:
            structure = {
                "tables": [],
                "forms": [],
                "buttons": [],
                "text_regions": [],
                "layout_type": "unknown",
                "confidence": 0.5,
            }

            # Detect tables
            tables = await page.query_selector_all("table")
            structure["tables"] = [
                {
                    "location": {"x": 0, "y": 0},
                    "rows": len(await t.query_selector_all("tr")),
                }
                for t in tables
            ]

            # Detect forms
            forms = await page.query_selector_all("form")
            structure["forms"] = [
                {"fields": len(await f.query_selector_all("input, textarea, select"))}
                for f in forms
            ]

            return structure

        except Exception as e:
            logger.debug(f"HTML structure analysis failed: {e}")
            return {"layout_type": "unknown", "confidence": 0.0}

    async def _analyze_html_table_structure(
        self, page: Page, table_element
    ) -> Optional[Dict[str, Any]]:
        """Analyze HTML table structure."""
        try:
            headers = []
            rows = []
            row_regions = []

            # Get headers
            header_cells = await table_element.query_selector_all("thead th, thead td")
            if not header_cells:
                header_cells = await table_element.query_selector_all("tbody tr:first-child td")

            for cell in header_cells:
                headers.append(await cell.inner_text())

            # Get rows
            body_rows = await table_element.query_selector_all(
                "tbody tr, tr:not(:first-child)"
            )
            for row in body_rows:
                cells = await row.query_selector_all("td")
                row_data = [await cell.inner_text() for cell in cells]
                if row_data:  # Only add non-empty rows
                    rows.append(row_data)

            return {
                "headers": headers,
                "rows": rows,
                "row_count": len(rows),
                "column_count": len(headers),
                "columns": [
                    {"name": h, "type": "text"} for h in headers
                ],
                "confidence": 0.95,
                "is_paginated": await self._check_table_pagination(page),
                "next_page_button": None,
            }

        except Exception as e:
            logger.debug(f"HTML table analysis failed: {e}")
            return None

    async def _check_table_pagination(self, page: Page) -> bool:
        """Check if table has pagination."""
        try:
            pagination = await page.query_selector(".pagination, .pager, [aria-label*=pagination]")
            return pagination is not None
        except:
            return False

    async def _find_field_in_html(self, page: Page, field_name: str) -> Optional[Dict[str, Any]]:
        """Find field in HTML structure."""
        try:
            # Look for elements with matching text content
            elements = await page.query_selector_all(
                f"text={field_name}, label:has-text('{field_name}')"
            )
            if elements:
                element = elements[0]
                return {
                    "field_name": field_name,
                    "element_type": "text",
                    "value": await element.inner_text(),
                    "confidence": 0.9,
                }

            return None
        except:
            return None
