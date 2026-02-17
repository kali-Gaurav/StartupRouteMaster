"""
Extraction AI — Intelligent Data Field Extraction

Extracts structured data from pages using:
- CSS selectors (fast)
- Semantic DOM search (robust)
- Visual OCR (fallback)
- Gemini reasoning (powerful)
- Multi-strategy confidence scoring
"""

import asyncio
import json
from typing import Optional, List, Dict, Any, Union
from playwright.async_api import Page
import logging

logger = logging.getLogger(__name__)


class ExtractionAI:
    """
    Smart field extraction with confidence scoring.
    Uses multiple strategies to extract data reliably.
    """

    def __init__(self, gemini_client=None, vision_ai=None):
        """
        Initialize ExtractionAI.

        Args:
            gemini_client: GeminiClient for advanced extraction
            vision_ai: VisionAI instance for visual analysis
        """
        self.gemini = gemini_client
        self.vision = vision_ai
        self.extraction_cache = {}  # Cache successful extractions
        self.field_strategies = {}  # Remember which strategy worked best for each field

    async def extract_with_confidence(
        self, page: Page, schema: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Extract fields from page with confidence scores.

        Args:
            page: Playwright page object
            schema: {'field_name': 'expected_type', ...}
                    Types: 'text', 'number', 'date', 'time', 'currency', 'email', etc

        Returns:
            {
                'field_name': {
                    'value': str | None,
                    'confidence': 0.0-1.0,
                    'extraction_strategy': 'css_selector' | 'semantic' | 'visual' | 'gemini',
                    'alternatives': [{'value': str, 'confidence': float}, ...],
                    'validation_passed': bool,
                    'error': str | None
                },
                ...
            }
        """
        logger.info(f"Extracting {len(schema)} fields with confidence scoring...")

        results = {}

        for field_name, expected_type in schema.items():
            logger.info(f"  Extracting field: '{field_name}' (type: {expected_type})")

            extraction_result = {
                "value": None,
                "confidence": 0.0,
                "extraction_strategy": "none",
                "alternatives": [],
                "validation_passed": False,
                "error": None,
            }

            try:
                # Try extraction strategies in order of speed
                strategies_results = []

                # Strategy 1: CSS Selector (fastest)
                css_result = await self._extract_via_css_selector(
                    page, field_name, expected_type
                )
                if css_result:
                    strategies_results.append(
                        ("css_selector", css_result["value"], css_result["confidence"])
                    )

                # Strategy 2: Semantic DOM search (medium speed)
                semantic_result = await self._extract_via_semantic_search(
                    page, field_name, expected_type
                )
                if semantic_result:
                    strategies_results.append(
                        ("semantic", semantic_result["value"], semantic_result["confidence"])
                    )

                # Strategy 3: Visual/OCR extraction (slower)
                if self.vision:
                    visual_result = await self._extract_via_visual_detection(
                        page, field_name, expected_type
                    )
                    if visual_result:
                        strategies_results.append(
                            ("visual", visual_result["value"], visual_result["confidence"])
                        )

                # Strategy 4: Gemini reasoning (most powerful)
                if self.gemini:
                    gemini_result = await self._extract_via_gemini(
                        page, field_name, expected_type
                    )
                    if gemini_result:
                        strategies_results.append(
                            ("gemini", gemini_result["value"], gemini_result["confidence"])
                        )

                # Select best result
                if strategies_results:
                    # Sort by confidence
                    strategies_results.sort(key=lambda x: x[2], reverse=True)

                    best_strategy, best_value, best_confidence = strategies_results[0]

                    extraction_result["value"] = best_value
                    extraction_result["confidence"] = best_confidence
                    extraction_result["extraction_strategy"] = best_strategy

                    # Store alternatives
                    extraction_result["alternatives"] = [
                        {"value": val, "confidence": conf, "strategy": strat}
                        for strat, val, conf in strategies_results[1:]
                    ]

                    # Validate
                    validation = await self._validate_extracted_value(
                        best_value, expected_type
                    )
                    extraction_result["validation_passed"] = validation["passed"]
                    if not validation["passed"]:
                        extraction_result["error"] = validation["error"]

                    logger.info(
                        f"    ✓ Extracted via {best_strategy}: {best_value} (confidence: {best_confidence:.2f})"
                    )
                else:
                    extraction_result["error"] = "No extraction strategies succeeded"
                    logger.warning(f"    ✗ Could not extract field: {field_name}")

            except Exception as e:
                extraction_result["error"] = str(e)
                logger.error(f"    ✗ Extraction error for {field_name}: {e}")

            results[field_name] = extraction_result

        logger.info(f"✓ Extracted {len(results)} fields")
        return results

    async def extract_structured_data(
        self, page: Page, structure_hint: str = ""
    ) -> Dict[str, Any]:
        """
        Extract JSON-structured data from page autonomously.

        The AI infers the schema and extracts all relevant data.

        Args:
            page: Playwright page object
            structure_hint: Hint about expected structure (e.g., "train schedule", "flight results")

        Returns:
            Extracted structured data
        """
        logger.info(f"Autonomously extracting structured data (hint: {structure_hint})...")

        try:
            if not self.gemini:
                logger.error("Gemini client required for structured extraction")
                return {}

            screenshot = await page.screenshot()
            html = await page.content()

            # Infer schema
            schema = await self.gemini.infer_data_schema(
                screenshot=screenshot,
                html=html,
                hint=structure_hint,
            )

            logger.info(f"Inferred schema: {list(schema.keys())}")

            # Extract using inferred schema
            extracted = await self.extract_with_confidence(page, schema)

            # Convert to structured format
            structured_data = {}
            for field_name, field_info in extracted.items():
                structured_data[field_name] = field_info.get("value")

            logger.info(f"✓ Extracted structured data: {len(structured_data)} fields")
            return structured_data

        except Exception as e:
            logger.error(f"Structured extraction failed: {e}")
            return {}

    async def extract_table_data(
        self, page: Page, table_selector: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract all rows from a table.

        Args:
            page: Playwright page object
            table_selector: Optional CSS selector for specific table

        Returns:
            List of row dictionaries
        """
        logger.info("Extracting table data...")

        try:
            # Find table using vision or selector
            table_element = None

            if table_selector:
                table_element = await page.query_selector(table_selector)
            else:
                tables = await page.query_selector_all("table")
                if tables:
                    table_element = tables[0]

            if not table_element and self.vision:
                table_info = await self.vision.detect_table_structure(page)
                if table_info:
                    # Visual extraction via Gemini
                    screenshot = await page.screenshot()
                    rows = await self.gemini.extract_table_rows_from_image(
                        screenshot,
                        column_names=table_info.get("headers", []),
                    )
                    logger.info(f"✓ Extracted {len(rows)} rows via visual detection")
                    return rows

            if not table_element:
                logger.warning("Could not find table on page")
                return []

            # Extract from HTML table
            rows = []
            headers = []

            # Get headers
            header_cells = await table_element.query_selector_all("thead th, thead td")
            if not header_cells:
                # Try first row as header
                first_row = await table_element.query_selector("tbody tr, tr")
                if first_row:
                    header_cells = await first_row.query_selector_all("td, th")

            for cell in header_cells:
                headers.append((await cell.inner_text()).strip())

            # Get rows
            body_rows = await table_element.query_selector_all(
                "tbody tr, tr:not(:has(th))"
            )

            for row_elem in body_rows:
                cells = await row_elem.query_selector_all("td")
                row_data = {}

                for idx, cell in enumerate(cells):
                    header = headers[idx] if idx < len(headers) else f"col_{idx}"
                    row_data[header] = (await cell.inner_text()).strip()

                if row_data:  # Only add non-empty rows
                    rows.append(row_data)

            logger.info(f"✓ Extracted {len(rows)} table rows with {len(headers)} columns")
            return rows

        except Exception as e:
            logger.error(f"Table extraction failed: {e}")
            return []

    async def extract_from_dynamic_content(
        self, page: Page, wait_selector: str, max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Extract from dynamically loaded content.

        Args:
            page: Playwright page object
            wait_selector: Selector to wait for dynamic content
            max_retries: Number of retries if extraction fails

        Returns:
            Extracted data
        """
        logger.info(f"Extracting from dynamic content (waiting for: {wait_selector})...")

        for attempt in range(max_retries):
            try:
                # Wait for content
                await page.wait_for_selector(wait_selector, timeout=15000)
                await asyncio.sleep(1)  # Give JS time to settle

                # Extract
                screenshot = await page.screenshot()
                html = await page.content()

                if self.gemini:
                    data = await self.gemini.extract_from_screenshot(screenshot, html)
                    logger.info(f"✓ Extracted dynamic content")
                    return data

                return {}

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Attempt {attempt + 1} failed, retrying... ({e})"
                    )
                    await asyncio.sleep(2)
                else:
                    logger.error(f"Failed to extract dynamic content after {max_retries} attempts")
                    return {}

    # Strategy implementations

    async def _extract_via_css_selector(
        self, page: Page, field_name: str, expected_type: str
    ) -> Optional[Dict[str, Any]]:
        """Extract using CSS selector (fast)."""
        try:
            # Try common selectors
            selectors = [
                f"[name='{field_name}']",
                f"[id='{field_name}']",
                f"[data-field='{field_name}']",
                f"[data-name='{field_name}']",
                f".{field_name}",
                f"#{field_name}",
            ]

            for selector in selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        # prefer element.value for inputs, otherwise inner_text
                        tag = (await (await element.get_property('tagName')).json_value()).lower() if await element.get_property('tagName') else ''
                        if tag in ('input', 'textarea', 'select'):
                            # try to read value attribute first
                            val = await element.get_attribute('value')
                            if not val:
                                # fallback to input_value (works for input elements)
                                try:
                                    val = await element.input_value()
                                except Exception:
                                    val = val or ''
                        else:
                            val = await element.inner_text()

                        if val:
                            return {"value": val.strip(), "confidence": 0.8}
                except Exception as e:
                    logger.debug(f"CSS selector lookup failed for {selector}: {e}")
                    pass

            return None

        except Exception as e:
            logger.debug(f"CSS selector extraction failed: {e}")
            return None

    async def _extract_via_semantic_search(
        self, page: Page, field_name: str, expected_type: str
    ) -> Optional[Dict[str, Any]]:
        """Extract via semantic DOM analysis (medium speed)."""
        try:
            # Search for text containing field name
            xpath = f"//*[contains(text(), '{field_name}')]"
            elements = await page.query_selector_all(xpath)

            for elem in elements:
                # Try to find adjacent input or value element
                parent = await elem.query_selector("..")
                if parent:
                    # Look for value in next siblings
                    next_elem = await parent.query_selector("+ *")
                    if next_elem:
                        value = await next_elem.inner_text()
                        if value:
                            return {"value": value, "confidence": 0.75}

                    # Look for value in children
                    value_elem = await parent.query_selector("span, strong, td")
                    if value_elem:
                        value = await value_elem.inner_text()
                        if value:
                            return {"value": value, "confidence": 0.7}

            return None

        except Exception as e:
            logger.debug(f"Semantic search extraction failed: {e}")
            return None

    async def _extract_via_visual_detection(
        self, page: Page, field_name: str, expected_type: str
    ) -> Optional[Dict[str, Any]]:
        """Extract via visual detection (slower)."""
        try:
            if not self.vision:
                return None

            screenshot = await page.screenshot()

            # Find field visually
            field_location = await self.vision.locate_data_field(
                page, field_name, context=f"expecting {expected_type}"
            )

            if field_location:
                # Extract text from location
                value = await self.vision.extract_text_from_region(
                    page, field_location.get("location")
                )
                if value:
                    return {
                        "value": value,
                        "confidence": field_location.get("confidence", 0.6),
                    }

            return None

        except Exception as e:
            logger.debug(f"Visual detection extraction failed: {e}")
            return None

    async def _extract_via_gemini(
        self, page: Page, field_name: str, expected_type: str
    ) -> Optional[Dict[str, Any]]:
        """Extract via Gemini reasoning (most powerful)."""
        try:
            if not self.gemini:
                return None

            screenshot = await page.screenshot()
            html = await page.content()

            result = await self.gemini.extract_field(
                screenshot=screenshot,
                html=html,
                field_name=field_name,
                expected_type=expected_type,
            )

            if result:
                return {
                    "value": result.get("value"),
                    "confidence": result.get("confidence", 0.7),
                }

            return None

        except Exception as e:
            logger.debug(f"Gemini extraction failed: {e}")
            return None

    async def _validate_extracted_value(
        self, value: Any, expected_type: str
    ) -> Dict[str, Any]:
        """Validate extracted value matches expected type."""
        try:
            if value is None:
                return {"passed": False, "error": "Value is None"}

            value_str = str(value).strip()

            if expected_type == "number":
                try:
                    float(value_str.replace(",", ""))
                    return {"passed": True, "error": None}
                except:
                    return {"passed": False, "error": "Not a valid number"}

            elif expected_type == "date":
                # Basic date validation (YYYY-MM-DD or DD-MM-YYYY or DD/MM/YYYY)
                import re
                if re.match(r"\d{1,4}[-/]\d{1,2}[-/]\d{1,4}", value_str):
                    return {"passed": True, "error": None}
                return {"passed": False, "error": "Not a valid date"}

            elif expected_type == "time":
                import re
                # validate HH:MM where HH is 0-23 and MM is 00-59
                if re.match(r"^([01]?\d|2[0-3]):[0-5]\d$", value_str):
                    return {"passed": True, "error": None}
                return {"passed": False, "error": "Not a valid time"}

            elif expected_type == "email":
                import re
                if re.match(r"[^@]+@[^@]+\.[^@]+", value_str):
                    return {"passed": True, "error": None}
                return {"passed": False, "error": "Not a valid email"}

            # For text types, just check not empty
            elif expected_type in ["text", "string"]:
                return {"passed": len(value_str) > 0, "error": None if len(value_str) > 0 else "Empty text"}

            else:
                # Unknown type - accept if not empty
                return {"passed": len(value_str) > 0, "error": None}

        except Exception as e:
            return {"passed": False, "error": str(e)}
