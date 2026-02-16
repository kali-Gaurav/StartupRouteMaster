"""
Gemini Client — API wrapper for vision, extraction, and reasoning

Integrates Google Gemini API for:
- Page layout analysis
- Form field detection
- Table structure extraction
- Field extraction with reasoning
- Page intent understanding
- Layout change detection
"""

import os
import json
import base64
import asyncio
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False
    logger.warning("google-generativeai not installed. Install with: pip install google-generativeai")


class GeminiClient:
    """
    Wrapper for Google Gemini API calls.
    Handles vision analysis, extraction, and reasoning.
    
    Supports multiple API keys for load balancing and fallback.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-pro-vision"):
        """
        Initialize Gemini client.

        Args:
            api_key: Gemini API key (uses GEMINI_API_KEY env var or multiple keys if not provided)
            model: Model to use (default: gemini-pro-vision for vision tasks)
        """
        self.api_keys = self._load_api_keys(api_key)
        self.model = model
        self.enabled = False
        self.current_key_index = 0

        if not self.api_keys:
            logger.warning("No Gemini API keys found - Gemini features disabled")
            logger.info("Set GEMINI_API_KEY or GEMINI_API_KEY1-5 environment variables")
            return

        if not HAS_GEMINI:
            logger.warning("google-generativeai not installed - Gemini features disabled")
            return

        try:
            self._configure_with_current_key()
            self.enabled = True
            logger.info(f"✓ Gemini client initialized (model: {model}, {len(self.api_keys)} key(s) available)")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {e}")
            self.enabled = False

    def _load_api_keys(self, provided_key: Optional[str]) -> List[str]:
        """
        Load API keys from environment variables.
        
        Priority:
        1. Provided api_key parameter
        2. Multiple keys: GEMINI_API_KEY1-5
        3. Single key: GEMINI_API_KEY
        """
        keys = []
        
        # If explicitly provided, use that
        if provided_key:
            return [provided_key]
        
        # Try to load multiple keys (GEMINI_API_KEY1-5)
        for i in range(1, 6):
            key = os.getenv(f"GEMINI_API_KEY{i}")
            if key:
                keys.append(key)
        
        # If no multiple keys, try single key
        if not keys:
            single_key = os.getenv("GEMINI_API_KEY")
            if single_key:
                keys.append(single_key)
        
        return keys

    def _configure_with_current_key(self):
        """Configure Gemini with the current API key."""
        if not self.api_keys:
            raise ValueError("No API keys available")
        
        current_key = self.api_keys[self.current_key_index % len(self.api_keys)]
        genai.configure(api_key=current_key)

    async def _call_with_fallback(self, api_call_fn):
        """
        Execute API call with automatic fallback to next key on rate limit.
        
        Args:
            api_call_fn: Async function that makes the API call
            
        Returns:
            API response or None if all keys are exhausted
        """
        max_retries = min(3, len(self.api_keys))
        
        for attempt in range(max_retries):
            try:
                self._configure_with_current_key()
                result = await api_call_fn()
                return result
            except Exception as e:
                error_msg = str(e).lower()
                
                # Check if it's a rate limit or quota error
                if any(x in error_msg for x in ['rate limit', 'quota', 'too many requests', '429', '403']):
                    logger.warning(
                        f"Rate limited on key {self.current_key_index + 1}/{len(self.api_keys)}. "
                        f"Switching to next key... ({attempt + 1}/{max_retries})"
                    )
                    self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1)  # Brief wait before retry
                        continue
                
                # For other errors, log and return None
                logger.error(f"Gemini API call failed: {e}")
                return None
        
        logger.error(f"All {len(self.api_keys)} API key(s) exhausted or failed")
        return None

    async def analyze_page_layout(
        self, screenshot: bytes, context: str = ""
    ) -> Dict[str, Any]:
        """
        Analyze page layout from screenshot.

        Args:
            screenshot: Screenshot bytes
            context: Additional context (e.g., "NTES website")

        Returns:
            {
                'layout_type': 'form' | 'table' | 'list' | 'mixed' | 'unknown',
                'tables': [{'rows': int, 'columns': int, 'detected': True}, ...],
                'forms': [{'fields': int}, ...],
                'buttons': [{'text': str, 'intent': str}, ...],
                'text_regions': [...],
                'confidence': 0.0-1.0
            }
        """
        if not self.enabled:
            return {"layout_type": "unknown", "confidence": 0.0}

        prompt = f"""
Analyze this webpage screenshot carefully.
Context: {context}

Identify and describe:
1. Overall page layout type (form, table, search results, list, mixed, etc.)
2. All tables present (count rows and columns approximately)
3. All form fields (inputs, selects, textareas)
4. All clickable buttons with their text
5. Text blocks and headings
6. Overall confidence in your analysis

Return ONLY valid JSON (no markdown, no code blocks):
{{
    "layout_type": "form|table|list|mixed|unknown",
    "tables": [
        {{"rows": int, "columns": int, "purpose": "str"}}
    ],
    "forms": [
        {{"fields": int, "purpose": "str"}}
    ],
    "buttons": [
        {{"text": "str", "intent": "str"}}
    ],
    "text_regions": [
        {{"type": "heading|paragraph|label", "content": "str"}}
    ],
    "layout_confidence": 0.0-1.0,
    "page_purpose": "brief description"
}}
        """

        # Convert screenshot to base64
        image_b64 = base64.b64encode(screenshot).decode("utf-8")

        async def api_call():
            model = genai.GenerativeModel(self.model)
            response = await asyncio.to_thread(
                model.generate_content,
                [
                    {"mime_type": "image/png", "data": image_b64},
                    prompt
                ]
            )
            return response

        response = await self._call_with_fallback(api_call)
        
        # Parse response
        if response and response.text:
            try:
                result = json.loads(response.text)
                logger.info(f"✓ Page layout analyzed: {result.get('layout_type')}")
                return result
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from Gemini: {response.text[:100]}")
                return {"layout_type": "unknown", "confidence": 0.0}

        return {"layout_type": "unknown", "confidence": 0.0}

    async def detect_form_fields(
        self, screenshot: bytes, hint: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Detect all form fields in screenshot.

        Args:
            screenshot: Screenshot bytes
            hint: Hint about what to look for

        Returns:
            [
                {
                    'label': str,
                    'type': 'text' | 'number' | 'date' | 'select' | 'checkbox' | 'radio',
                    'required': bool,
                    'placeholder': str,
                    'confidence': 0.0-1.0
                },
                ...
            ]
        """
        if not self.enabled:
            return []

        prompt = f"""
Analyze this form screenshot.
Hint: {hint}

Identify all form fields visible:
1. Input fields (text, number, email, date, etc.)
2. Select/dropdown fields
3. Checkboxes and radio buttons
4. Text areas
5. For each field: label text, type, required indicator, placeholder

Return ONLY valid JSON:
[
    {{
        "label": "field label text",
        "type": "text|number|date|email|select|checkbox|radio|textarea",
        "required": true|false,
        "placeholder": "placeholder text or null",
        "confidence": 0.0-1.0,
        "position": "top|middle|bottom"
    }}
]
        """

        image_b64 = base64.b64encode(screenshot).decode("utf-8")

        async def api_call():
            model = genai.GenerativeModel(self.model)
            response = await asyncio.to_thread(
                model.generate_content,
                [
                    {"mime_type": "image/png", "data": image_b64},
                    prompt
                ]
            )
            return response

        response = await self._call_with_fallback(api_call)

        if response and response.text:
            try:
                fields = json.loads(response.text)
                logger.info(f"✓ Detected {len(fields)} form fields")
                return fields if isinstance(fields, list) else []
            except json.JSONDecodeError:
                logger.warning("Invalid JSON from form field detection")
                return []

        return []

    async def extract_table_structure(
        self, screenshot: bytes, html: str = "", hint: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        Extract table structure and content from screenshot.

        Args:
            screenshot: Screenshot bytes
            html: HTML content (optional, for reference)
            hint: Hint about table content (e.g., "train schedule")

        Returns:
            {
                'headers': [str, ...],
                'row_count': int,
                'column_count': int,
                'columns': [{'name': str, 'type': str}, ...],
                'sample_rows': [[str, ...], ...],
                'confidence': 0.0-1.0,
                'is_paginated': bool
            }
        """
        if not self.enabled:
            return None

        prompt = f"""
Analyze this table screenshot.
Hint: {hint}

Extract table structure:
1. Column headers (names)
2. Approximate row count
3. Column data types (text, number, date, currency, etc.)
4. Sample rows (first 3 rows as examples)
5. Whether table appears paginated

Return ONLY valid JSON:
{{
    "headers": ["col1", "col2", ...],
    "row_count": estimated_count,
    "column_count": int,
    "columns": [
        {{"name": "str", "type": "text|number|date|currency|time"}},
        ...
    ],
    "sample_rows": [
        ["val1", "val2", ...],
        ["val1", "val2", ...],
        ["val1", "val2", ...]
    ],
    "table_confidence": 0.0-1.0,
    "is_paginated": true|false,
    "pagination_hint": "next button found|no pagination"
}}
        """

        image_b64 = base64.b64encode(screenshot).decode("utf-8")

        async def api_call():
            model = genai.GenerativeModel(self.model)
            response = await asyncio.to_thread(
                model.generate_content,
                [
                    {"mime_type": "image/png", "data": image_b64},
                    prompt
                ]
            )
            return response

        response = await self._call_with_fallback(api_call)

        if response and response.text:
            try:
                result = json.loads(response.text)
                logger.info(f"✓ Table structure extracted: {result.get('row_count')} rows")
                return result
            except json.JSONDecodeError:
                logger.warning("Invalid JSON from table extraction")
                return None

        return None

    async def extract_field(
        self,
        screenshot: bytes,
        html: str,
        field_name: str,
        expected_type: str = "text",
    ) -> Optional[Dict[str, Any]]:
        """
        Extract specific field value from screenshot.

        Args:
            screenshot: Screenshot bytes
            html: HTML content
            field_name: Name of field to extract (e.g., "Train Name")
            expected_type: Expected data type

        Returns:
            {
                'value': extracted_value,
                'confidence': 0.0-1.0,
                'field_name': str,
                'extraction_method': str
            }
        """
        if not self.enabled:
            return None

        prompt = f"""
Looking at this screenshot, find and extract the value for: {field_name}
Expected type: {expected_type}

Search for this field:
1. By label text matching "{field_name}"
2. By field description
3. By context and location

Extract the field value carefully.

Return ONLY valid JSON:
{{
    "value": "extracted value or null",
    "confidence": 0.0-1.0,
    "found": true|false,
    "location": "top|middle|bottom",
    "method": "label_match|context|position"
}}
        """

        image_b64 = base64.b64encode(screenshot).decode("utf-8")

        async def api_call():
            model = genai.GenerativeModel(self.model)
            response = await asyncio.to_thread(
                model.generate_content,
                [
                    {"mime_type": "image/png", "data": image_b64},
                    prompt
                ]
            )
            return response

        response = await self._call_with_fallback(api_call)

        if response and response.text:
            try:
                result = json.loads(response.text)
                if result.get("found"):
                    logger.info(f"✓ Field extracted: {field_name}")
                    return result
            except json.JSONDecodeError:
                logger.warning("Invalid JSON from field extraction")
                return None

        return None

    async def infer_data_schema(
        self, screenshot: bytes, html: str = "", hint: str = ""
    ) -> Dict[str, str]:
        """
        Infer what data should be extracted from page.

        Args:
            screenshot: Screenshot bytes
            html: HTML content (optional)
            hint: Context hint (e.g., "train schedule")

        Returns:
            {'field_name': 'expected_type', ...}
            Types: text, number, date, time, currency, email, etc.
        """
        if not self.enabled:
            return {}

        prompt = f"""
Analyze this page and determine what data fields are available.
Context: {hint}

For each visible field/column:
1. Identify the field name/header
2. Determine the expected data type

Return ONLY valid JSON mapping (no other text):
{{
    "field_name_1": "text|number|date|time|currency|email",
    "field_name_2": "text|number|date|time|currency",
    ...
}}

Example for train schedule:
{{
    "station_code": "text",
    "station_name": "text",
    "arrival_time": "time",
    "departure_time": "time",
    "distance_km": "number"
}}
        """

        image_b64 = base64.b64encode(screenshot).decode("utf-8")

        async def api_call():
            model = genai.GenerativeModel(self.model)
            response = await asyncio.to_thread(
                model.generate_content,
                [
                    {"mime_type": "image/png", "data": image_b64},
                    prompt
                ]
            )
            return response

        response = await self._call_with_fallback(api_call)

        if response and response.text:
            try:
                schema = json.loads(response.text)
                logger.info(f"✓ Schema inferred: {len(schema)} fields")
                return schema if isinstance(schema, dict) else {}
            except json.JSONDecodeError:
                logger.warning("Invalid JSON from schema inference")
                return {}

        return {}

    async def find_field_on_screen(
        self, screenshot: bytes, field_name: str, context: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        Locate where a field appears on screen.

        Args:
            screenshot: Screenshot bytes
            field_name: Name of field to find
            context: Additional context

        Returns:
            {
                'field_name': str,
                'found': bool,
                'location': {'x': int, 'y': int, 'width': int, 'height': int},
                'confidence': 0.0-1.0,
                'approximate_region': 'top-left|top|top-right|middle|bottom'
            }
        """
        if not self.enabled:
            return None

        prompt = f"""
Find the field "{field_name}" on this screenshot.
Context: {context}

Estimate the pixel location (approximate):
1. X coordinate (0-1000)
2. Y coordinate (0-800)
3. Width and height
4. Confidence that this is the right field

Return ONLY valid JSON:
{{
    "found": true|false,
    "field_name": "{field_name}",
    "location": {{"x": int, "y": int, "width": int, "height": int}},
    "confidence": 0.0-1.0,
    "approximate_region": "top-left|top|top-right|middle-left|middle|middle-right|bottom-left|bottom|bottom-right"
}}
        """

        image_b64 = base64.b64encode(screenshot).decode("utf-8")

        async def api_call():
            model = genai.GenerativeModel(self.model)
            response = await asyncio.to_thread(
                model.generate_content,
                [
                    {"mime_type": "image/png", "data": image_b64},
                    prompt
                ]
            )
            return response

        response = await self._call_with_fallback(api_call)

        if response and response.text:
            try:
                result = json.loads(response.text)
                if result.get("found"):
                    logger.info(f"✓ Field located: {field_name}")
                    return result
            except json.JSONDecodeError:
                logger.warning("Invalid JSON from field location")
                return None

        return None

    async def analyze_page_intent(
        self, screenshot: bytes, html: str = "", url: str = ""
    ) -> Dict[str, Any]:
        """
        Understand what this page is for.

        Args:
            screenshot: Screenshot bytes
            html: HTML content
            url: Page URL

        Returns:
            {
                'page_type': str (search_form|results|login|booking|etc),
                'primary_intent': str,
                'expected_fields': [str, ...],
                'expected_actions': [str, ...],
                'confidence': 0.0-1.0
            }
        """
        if not self.enabled:
            return {"page_type": "unknown", "confidence": 0.0}

        prompt = f"""
Analyze this webpage and understand its purpose.
URL: {url}

Determine:
1. Page type (search form, results page, login, booking, etc.)
2. Primary intent (what is user supposed to do?)
3. Expected form fields
4. Expected actions/buttons

Return ONLY valid JSON:
{{
    "page_type": "search_form|results|login|booking|schedule|unknown",
    "primary_intent": "description of main purpose",
    "expected_fields": ["field1", "field2"],
    "expected_actions": ["action1", "action2"],
    "page_confidence": 0.0-1.0
}}
        """

        image_b64 = base64.b64encode(screenshot).decode("utf-8")

        async def api_call():
            model = genai.GenerativeModel(self.model)
            response = await asyncio.to_thread(
                model.generate_content,
                [
                    {"mime_type": "image/png", "data": image_b64},
                    prompt
                ]
            )
            return response

        response = await self._call_with_fallback(api_call)

        if response and response.text:
            try:
                result = json.loads(response.text)
                logger.info(f"✓ Page intent analyzed: {result.get('page_type')}")
                return result
            except json.JSONDecodeError:
                logger.warning("Invalid JSON from intent analysis")
                return {"page_type": "unknown", "confidence": 0.0}

        return {"page_type": "unknown", "confidence": 0.0}

    async def detect_layout_changes(
        self, current_screenshot: bytes, previous_screenshot: bytes
    ) -> Dict[str, Any]:
        """
        Detect if page layout has changed.

        Args:
            current_screenshot: Current screenshot
            previous_screenshot: Previous screenshot

        Returns:
            {
                'changed': bool,
                'change_type': 'layout|content|styling|major|none',
                'confidence': 0.0-1.0,
                'changes_detected': [str, ...],
                'recommendation': str
            }
        """
        if not self.enabled:
            return {"changed": False, "confidence": 0.0}

        prompt = """
Compare these two screenshots. Has the page layout changed?

Analyze:
1. Page structure (columns, sections)
2. Element positions
3. Form field locations
4. Button positions
5. Overall design

Return ONLY valid JSON:
{
    "changed": true|false,
    "change_type": "major_layout|minor_layout|content_only|styling|none",
    "confidence": 0.0-1.0,
    "changes_detected": [
        "description of change 1",
        "description of change 2"
    ],
    "recommendation": "selectors_may_break|safe_to_reuse_selectors"
}
        """

        current_b64 = base64.b64encode(current_screenshot).decode("utf-8")
        previous_b64 = base64.b64encode(previous_screenshot).decode("utf-8")

        async def api_call():
            model = genai.GenerativeModel(self.model)
            response = await asyncio.to_thread(
                model.generate_content,
                [
                    "Previous screenshot:",
                    {"mime_type": "image/png", "data": previous_b64},
                    "Current screenshot:",
                    {"mime_type": "image/png", "data": current_b64},
                    prompt
                ]
            )
            return response

        response = await self._call_with_fallback(api_call)

        if response and response.text:
            try:
                result = json.loads(response.text)
                logger.info(f"Layout change detection: {result.get('change_type')}")
                return result
            except json.JSONDecodeError:
                logger.warning("Invalid JSON from layout change detection")
                return {"changed": False, "confidence": 0.0}

        return {"changed": False, "confidence": 0.0}

    async def detect_buttons(self, screenshot: bytes, hint: str = "") -> List[Dict[str, Any]]:
        """
        Detect all clickable buttons on page.

        Args:
            screenshot: Screenshot bytes
            hint: Hint about what buttons to look for

        Returns:
            [
                {
                    'text': button text,
                    'intent': semantic meaning (search, next, submit, etc),
                    'confidence': 0.0-1.0,
                    'region': 'top|middle|bottom'
                },
                ...
            ]
        """
        if not self.enabled:
            return []

        prompt = f"""
Identify all clickable buttons on this page.
Hint: {hint}

For each button:
1. Button text or label
2. Semantic intent (search, next, submit, save, cancel, etc)
3. Approximate position

Return ONLY valid JSON array:
[
    {{
        "text": "button text",
        "intent": "search|next|previous|submit|save|cancel|apply|close",
        "confidence": 0.0-1.0,
        "region": "top|middle|bottom"
    }},
    ...
]
        """

        image_b64 = base64.b64encode(screenshot).decode("utf-8")

        async def api_call():
            model = genai.GenerativeModel(self.model)
            response = await asyncio.to_thread(
                model.generate_content,
                [
                    {"mime_type": "image/png", "data": image_b64},
                    prompt
                ]
            )
            return response

        response = await self._call_with_fallback(api_call)

        if response and response.text:
            try:
                buttons = json.loads(response.text)
                logger.info(f"✓ Detected {len(buttons)} buttons")
                return buttons if isinstance(buttons, list) else []
            except json.JSONDecodeError:
                logger.warning("Invalid JSON from button detection")
                return []

        return []
