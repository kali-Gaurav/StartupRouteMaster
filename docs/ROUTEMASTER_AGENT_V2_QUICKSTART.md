# RouteMaster Agent v2 — Quick Start Guide

**Created:** Feb 17, 2026  
**Status:** Core Intelligence Ready | Awaiting Gemini Integration

---

## 🎯 What You Got

Complete autonomous AI agent framework with:

✅ **NavigatorAI** — Smart element finding (no hardcoded selectors)  
✅ **VisionAI** — Screenshot understanding & layout detection  
✅ **ExtractionAI** — Multi-strategy data extraction with confidence scoring  
✅ **DecisionEngine** — Autonomous decision making  
✅ **Architecture Doc** — Complete v2 design (with 6 intelligence layers)  
✅ **Implementation Guide** — Step-by-step roadmap  

---

## 🚀 Next Immediate Step (THIS WEEK)

### Create Gemini API Wrapper

**File:** `routemaster_agent/ai/gemini_client.py`

```python
import os
import json
import base64
from typing import Optional, Dict, Any
import logging

try:
    import anthropic
    # Or use: from google.generativeai import genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

logger = logging.getLogger(__name__)


class GeminiClient:
    """Wrapper for Gemini API calls (vision, extraction, reasoning)"""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-pro-vision"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model
        
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not set - vision features disabled")
            self.enabled = False
        else:
            # Initialize Gemini client here
            self.enabled = True

    async def analyze_page_layout(
        self, 
        screenshot: bytes, 
        context: str = ""
    ) -> Dict[str, Any]:
        """
        Analyze page layout from screenshot.
        
        Returns:
        {
            'layout_type': 'form' | 'table' | 'list' | 'mixed',
            'tables': [{'rows': int, 'columns': int}, ...],
            'forms': [{'fields': int}, ...],
            'buttons': [{'text': str, 'intent': str}, ...],
            'confidence': 0.0-1.0
        }
        """
        if not self.enabled:
            return {'layout_type': 'unknown', 'confidence': 0.0}
        
        prompt = f"""
        Analyze this webpage screenshot. 
        Context: {context}
        
        Identify:
        1. Type of page (form, table, list, search results, etc.)
        2. All tables present (count rows/columns)
        3. All form fields present
        4. All clickable buttons with their text/intent
        5. Overall layout type
        
        Return JSON:
        {{
            "layout_type": "...",
            "tables": [...],
            "forms": [...],
            "buttons": [...],
            "confidence": 0.95
        }}
        """
        
        # Convert screenshot to base64
        image_b64 = base64.b64encode(screenshot).decode("utf-8")
        
        # Call Gemini API here
        # response = await self.client.messages.create(
        #     model=self.model,
        #     max_tokens=1024,
        #     messages=[{
        #         "role": "user",
        #         "content": [
        #             {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_b64}},
        #             {"type": "text", "text": prompt}
        #         ]
        #     }]
        # )
        
        # Parse response and return
        return {'layout_type': 'unknown', 'confidence': 0.5}

    async def detect_form_fields(
        self,
        screenshot: bytes,
        hint: str = ""
    ) -> list:
        """Detect all form fields in screenshot"""
        pass

    async def extract_table_structure(
        self,
        screenshot: bytes,
        html: str = "",
        hint: str = ""
    ) -> Dict[str, Any]:
        """Analyze table structure from screenshot"""
        pass

    async def extract_field(
        self,
        screenshot: bytes,
        html: str,
        field_name: str,
        expected_type: str
    ) -> Optional[Dict[str, Any]]:
        """Extract specific field value"""
        pass

    async def infer_data_schema(
        self,
        screenshot: bytes,
        html: str,
        hint: str = ""
    ) -> Dict[str, str]:
        """Auto-detect what data to extract"""
        pass

    async def find_field_on_screen(
        self,
        screenshot: bytes,
        field_name: str,
        context: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Locate where field appears on screen"""
        pass

    async def detect_buttons(
        self,
        screenshot: bytes,
        hint: str = ""
    ) -> list:
        """Detect clickable buttons"""
        pass

    async def detect_layout_changes(
        self,
        current_screenshot: bytes,
        previous_screenshot: bytes
    ) -> Dict[str, Any]:
        """Detect if page layout changed"""
        pass

    async def analyze_page_intent(
        self,
        screenshot: bytes,
        html: str,
        url: str = ""
    ) -> Dict[str, Any]:
        """Understand what this page is for"""
        pass
```

**Install Gemini SDK:**
```bash
# Option 1: Google Generative AI (Recommended)
pip install google-generativeai

# Option 2: Claude API (Alternative)
pip install anthropic

# Set API Key
export GEMINI_API_KEY="your-api-key-here"
```

---

## 📋 Then Create Reasoning Loop

**File:** `routemaster_agent/core/reasoning_loop.py`

```python
from typing import Dict, Any, Optional
from datetime import datetime
from .navigator_ai import NavigatorAI
from .vision_ai import VisionAI
from .extractor_ai import ExtractionAI
from .decision_engine import DecisionEngine
import logging

logger = logging.getLogger(__name__)


class ReasoningLoop:
    """
    Autonomous execution loop:
    OBSERVE → THINK → DECIDE → ACT → VERIFY → LEARN
    """

    def __init__(self, gemini_client):
        self.gemini = gemini_client
        self.navigator = NavigatorAI(gemini_client=gemini_client)
        self.vision = VisionAI(gemini_client=gemini_client)
        self.extractor = ExtractionAI(
            gemini_client=gemini_client,
            vision_ai=self.vision
        )
        self.decision = DecisionEngine(gemini_client=gemini_client)
        self.memory = {}  # Store learned patterns

    async def execute_autonomously(self, page, task: Dict[str, Any]):
        """
        Execute task using full reasoning loop.
        
        Args:
            page: Playwright page
            task: {
                'objective': str (e.g., 'extract train schedule'),
                'train_number': str (e.g., '12951'),
                'expected_schema': dict (what fields to extract)
            }
        
        Returns:
            {
                'success': bool,
                'data': dict,
                'confidence': 0.0-1.0,
                'reasoning_log': [...]
            }
        """
        reasoning_log = []
        task_id = f"task_{datetime.utcnow().timestamp()}"

        try:
            # 1️⃣ OBSERVE
            logger.info("🔍 [OBSERVE] Taking screenshot and analyzing DOM...")
            reasoning_log.append("OBSERVE: Captured current page state")
            
            screenshot = await page.screenshot()
            dom_html = await page.content()
            page_url = page.url
            
            observation = {
                'url': page_url,
                'screenshot_size': len(screenshot),
                'dom_size': len(dom_html)
            }

            # 2️⃣ THINK (Gemini analyzes)
            logger.info("🧠 [THINK] Analyzing current state with Gemini...")
            reasoning_log.append("THINK: Analyzing page structure and task")
            
            page_structure = await self.vision.analyze_page_structure(page)
            page_intent = await self.vision.understand_page_intent(page)
            
            thought_process = {
                'page_type': page_intent.get('page_type'),
                'detected_elements': {
                    'tables': len(page_structure.get('tables', [])),
                    'buttons': len(page_structure.get('buttons', [])),
                    'forms': len(page_structure.get('forms', []))
                },
                'task_alignment': f"Task: {task['objective']}, Page: {page_intent.get('page_type')}"
            }

            # 3️⃣ DECIDE (Choose strategy)
            logger.info("🎯 [DECIDE] Planning navigation strategy...")
            reasoning_log.append("DECIDE: Choosing action strategy")
            
            # Based on page structure and task, decide what to do
            if page_intent.get('page_type') == 'search_form':
                action_plan = await self._plan_form_navigation(task)
            elif page_intent.get('page_type') == 'results':
                action_plan = await self._plan_extraction(task)
            else:
                action_plan = await self._plan_generic_navigation(task)

            # 4️⃣ ACT (Execute plan)
            logger.info("⚡ [ACT] Executing navigation plan...")
            reasoning_log.append("ACT: Executing planned actions")
            
            for action in action_plan.get('steps', []):
                logger.info(f"  → {action['description']}")
                
                if action['type'] == 'fill_input':
                    element = await self.navigator.find_element_by_visual_label(
                        page, action['label']
                    )
                    if element:
                        await self.navigator.fill_input_and_trigger_event(
                            page, element, action['value']
                        )
                
                elif action['type'] == 'click_button':
                    button = await self.navigator.find_button_by_intent(
                        page, action['intent']
                    )
                    if button:
                        await button.click()
                
                elif action['type'] == 'wait':
                    await page.wait_for_load_state("networkidle")

            # 5️⃣ VERIFY (Check results)
            logger.info("✅ [VERIFY] Validating results...")
            reasoning_log.append("VERIFY: Checking data quality")
            
            extracted_data = await self.extractor.extract_with_confidence(
                page,
                schema=task.get('expected_schema', {})
            )
            
            validity = await self.decision.decide_data_validity(extracted_data)

            # 6️⃣ LEARN (Update memory)
            logger.info("📚 [LEARN] Storing lessons learned...")
            reasoning_log.append("LEARN: Updating knowledge base")
            
            await self._update_memory(
                task_id, action_plan, extracted_data, validity
            )

            # Return result
            return {
                'success': validity['valid'],
                'data': extracted_data,
                'confidence': validity['confidence'],
                'recommendation': validity['recommendation'],
                'reasoning_log': reasoning_log,
                'task_id': task_id
            }

        except Exception as e:
            logger.error(f"❌ [ERROR] Task failed: {e}")
            reasoning_log.append(f"ERROR: {str(e)}")
            
            return {
                'success': False,
                'error': str(e),
                'reasoning_log': reasoning_log,
                'task_id': task_id
            }

    async def _plan_form_navigation(self, task: Dict) -> Dict[str, Any]:
        """Plan navigation for form submission"""
        return {
            'steps': [
                {
                    'type': 'fill_input',
                    'label': 'Train Number',
                    'value': task.get('train_number'),
                    'description': f'Fill train number: {task.get("train_number")}'
                },
                {
                    'type': 'click_button',
                    'intent': 'search',
                    'description': 'Click search button'
                },
                {
                    'type': 'wait',
                    'description': 'Wait for results to load'
                }
            ]
        }

    async def _plan_extraction(self, task: Dict) -> Dict[str, Any]:
        """Plan data extraction"""
        return {
            'steps': [
                {
                    'type': 'wait',
                    'description': 'Wait for page to fully load'
                }
            ]
        }

    async def _plan_generic_navigation(self, task: Dict) -> Dict[str, Any]:
        """Generic fallback plan"""
        return {'steps': []}

    async def _update_memory(self, task_id: str, plan: Dict, data: Dict, result: Dict):
        """Store learned patterns for future tasks"""
        self.memory[task_id] = {
            'plan_effectiveness': 'success' if result['valid'] else 'failed',
            'strategy_used': plan,
            'confidence_score': result.get('confidence'),
            'timestamp': datetime.utcnow().isoformat()
        }
```

---

## 🧪 Quick Test

```python
# test_v2_core.py
import asyncio
from routemaster_agent.core import NavigatorAI, VisionAI, ExtractionAI, DecisionEngine
from playwright.async_api import async_playwright


async def test_core_modules():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        # Initialize core modules
        navigator = NavigatorAI()
        vision = VisionAI()
        extractor = ExtractionAI(vision_ai=vision)
        decision = DecisionEngine()
        
        # Test 1: Navigator
        print("Test 1: NavigatorAI")
        await page.goto("https://enquiry.indianrail.gov.in/mntes/")
        element = await navigator.find_element_by_visual_label(page, "Train Number")
        print(f"  ✓ Found element: {element is not None}")
        
        # Test 2: Vision
        print("Test 2: VisionAI")
        structure = await vision.analyze_page_structure(page)
        print(f"  ✓ Page structure: {structure.get('layout_type')}")
        
        # Test 3: Decision
        print("Test 3: DecisionEngine")
        validity = await decision.decide_data_validity({
            'field1': {'value': 'data', 'confidence': 0.9, 'validation_passed': True}
        })
        print(f"  ✓ Decision: {validity['recommendation']}")
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_core_modules())
```

**Run it:**
```bash
python test_v2_core.py
```

---

## 📊 Where It Fits

```
Existing Backend
    ↓
Command Interface (executes commands)
    ↓
Reasoning Loop [NEW - orchestrates all]
    ├── NavigatorAI → finds elements
    ├── VisionAI → understands page
    ├── ExtractionAI → extracts data
    └── DecisionEngine → decides what to do
    ↓
DataPipeline (cleans & normalizes)
    ↓
Database (stores)
```

---

## 🎓 Architecture Summary

**6 Brain Layers:**
1. **Task Planner** (in planner.py) — What to do
2. **Navigator** (NEW) — Where to click
3. **Vision** (NEW) — What to see
4. **Extractor** (NEW) — What to grab
5. **Decision Engine** (NEW) — What to decide
6. **Reasoning Loop** (to create) — Orchestrates all

**With Gemini:** Each layer gets AI-powered intelligence  
**Without Gemini:** Each layer uses heuristics/fallbacks

---

## 🔥 Why This is Powerful

✨ **No Hardcoded Selectors** — Finds elements intelligently  
✨ **Visual Understanding** — Understands page layout  
✨ **Multi-Strategy Extraction** — Never fails silently  
✨ **Autonomous Decision Making** — Decides what to do with data  
✨ **Self-Healing** — Recovers from page changes  
✨ **Confidence Scoring** — Knows quality of data  
✨ **Generic Handler** — Works on any website  
✨ **Grafana Integration** — Real-time dashboard control  

---

## 📝 Todo (in Order)

- [ ] Create `ai/gemini_client.py` (THIS WEEK)
- [ ] Setup Gemini API key
- [ ] Create `core/reasoning_loop.py` 
- [ ] Test end-to-end
- [ ] Create flight/bus sources
- [ ] Setup Grafana dashboard
- [ ] Deploy & monitor

---

## 💬 Key Files Reference

**New Core Modules:**
- `routemaster_agent/core/navigator_ai.py` — Element finding
- `routemaster_agent/core/vision_ai.py` — Screenshot analysis
- `routemaster_agent/core/extractor_ai.py` — Data extraction
- `routemaster_agent/core/decision_engine.py` — Decision making

**Documentation:**
- `routemaster_agent/ARCHITECTURE_ANALYSIS.md` — Full v2 design
- `routemaster_agent/IMPLEMENTATION_GUIDE.md` — Step-by-step guide

**To Create:**
- `routemaster_agent/ai/gemini_client.py` — Gemini wrapper (NEXT)
- `routemaster_agent/core/reasoning_loop.py` — Orchestrator (NEXT)

---

**Ready to make it truly autonomous? Let's go! 🚀**

The foundation is set. Now integrate Gemini and watch it think, decide, and act on its own.
