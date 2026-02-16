"""
Reasoning Loop - Autonomous execution orchestrator

Implements full reasoning cycle: OBSERVE -> THINK -> DECIDE -> ACT -> VERIFY -> STORE -> LEARN

This is the orchestrator for autonomous agent execution.
"""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

from .navigator_ai import NavigatorAI
from .vision_ai import VisionAI
from .extractor_ai import ExtractionAI
from .decision_engine import DecisionEngine

logger = logging.getLogger(__name__)


class ReasoningLoop:
    """
    Autonomous execution orchestrator.
    
    Full reasoning cycle:
    1. OBSERVE - Capture current page state
    2. THINK - Analyze with Gemini AI
    3. DECIDE - Choose navigation strategy
    4. ACT - Execute navigation actions
    5. VERIFY - Validate extracted data
    6. STORE - Make storage decision
    7. LEARN - Update learned patterns
    """

    def __init__(self, gemini_client=None):
        """
        Initialize reasoning loop.

        Args:
            gemini_client: GeminiClient for AI reasoning (optional)
        """
        self.gemini = gemini_client
        self.navigator = NavigatorAI(gemini_client=gemini_client)
        self.vision = VisionAI(gemini_client=gemini_client)
        self.extractor = ExtractionAI(gemini_client=gemini_client, vision_ai=self.vision)
        self.decision = DecisionEngine(gemini_client=gemini_client)
        
        self.memory = {
            "successful_paths": {},
            "failed_recoveries": {},
            "page_layouts": {},
            "field_locations": {},
            "extraction_strategies": {},
        }
        self.execution_history = []

    async def execute_autonomously(
        self, page, task: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute task using full reasoning cycle.

        Args:
            page: Playwright page object
            task: Task definition dict

        Returns:
            Result dict with success status, data, confidence, reasoning log
        """
        task_id = f"task_{datetime.utcnow().timestamp()}"
        reasoning_log = []
        start_time = datetime.utcnow()

        logger.info(f"[START] Task: {task.get('objective')}")

        try:
            # 1. OBSERVE
            logger.info("[OBSERVE] Capturing page state...")
            observation = await self._observe(page)
            reasoning_log.append("OBSERVE: Captured page state")

            # 2. THINK
            logger.info("[THINK] Analyzing with AI...")
            analysis = await self._think(page, task, observation)
            reasoning_log.append(f"THINK: Page type={analysis.get('page_type')}")

            # 3. DECIDE
            logger.info("[DECIDE] Planning strategy...")
            plan = await self._decide(task, analysis)
            reasoning_log.append(f"DECIDE: {len(plan.get('steps', []))} actions")

            # 4. ACT
            logger.info("[ACT] Executing navigation...")
            act_result = await self._act(page, plan, task)
            if not act_result["success"]:
                reasoning_log.append(f"ACT failed: {act_result['error']}")
                recovery = await self._attempt_recovery(page, act_result, task)
                if recovery["success"]:
                    reasoning_log.append(f"RECOVERED: {recovery['strategy']}")
                    act_result = recovery
                else:
                    return {
                        "success": False,
                        "error": f"Action failed: {act_result['error']}",
                        "reasoning_log": reasoning_log,
                        "task_id": task_id,
                    }

            # 5. VERIFY
            logger.info("[VERIFY] Extracting data...")
            extracted = await self._verify(page, task)
            reasoning_log.append(f"VERIFY: Extracted {len(extracted)} fields")

            # 6. STORE
            logger.info("[STORE] Validating...")
            validity = await self.decision.decide_data_validity(
                extracted, data_type=task.get("data_type", "")
            )
            reasoning_log.append(f"STORE: {validity['recommendation']}")

            # 7. LEARN
            logger.info("[LEARN] Updating memory...")
            await self._learn(task_id, plan, extracted, validity)
            reasoning_log.append("LEARN: Memory updated")

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            result = {
                "success": validity["valid"],
                "data": extracted,
                "confidence": validity["confidence"],
                "recommendation": validity["recommendation"],
                "reasoning_log": reasoning_log,
                "task_id": task_id,
                "execution_time_seconds": execution_time,
            }

            logger.info(f"[COMPLETE] Task completed in {execution_time:.2f}s")
            self.execution_history.append(
                {"task_id": task_id, "success": result["success"], "time": execution_time}
            )

            return result

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            logger.error(f"[ERROR] Task failed: {e}")
            reasoning_log.append(f"ERROR: {str(e)}")

            return {
                "success": False,
                "error": str(e),
                "reasoning_log": reasoning_log,
                "task_id": task_id,
                "execution_time_seconds": execution_time,
            }

    async def _observe(self, page) -> Dict[str, Any]:
        """Capture current page state."""
        try:
            screenshot = await page.screenshot()
            structure = await self.vision.analyze_page_structure(page)
            return {
                "url": page.url,
                "page_type": structure.get("layout_type", "unknown"),
                "screenshot_size": len(screenshot),
            }
        except Exception as e:
            logger.error(f"Observation failed: {e}")
            return {"url": page.url, "error": str(e)}

    async def _think(self, page, task: Dict, observation: Dict) -> Dict[str, Any]:
        """Analyze with Gemini or heuristics."""
        try:
            page_intent = observation.get("page_type", "unknown")
            return {
                "page_type": page_intent,
                "task_objective": task.get("objective", ""),
                "recommended_strategy": self._recommend_strategy(
                    task.get("objective", ""), page_intent
                ),
            }
        except Exception as e:
            logger.error(f"Think failed: {e}")
            return {"error": str(e)}

    async def _decide(self, task: Dict, analysis: Dict) -> Dict[str, Any]:
        """Choose execution strategy."""
        try:
            steps = await self._generate_action_steps(
                analysis.get("recommended_strategy", "generic"), task
            )
            return {"strategy": analysis.get("recommended_strategy"), "steps": steps}
        except Exception as e:
            logger.error(f"Decide failed: {e}")
            return {"steps": [], "error": str(e)}

    async def _act(self, page, plan: Dict, task: Dict) -> Dict[str, Any]:
        """Execute navigation plan."""
        try:
            steps = plan.get("steps", [])
            for step in steps:
                await self._execute_step(page, step)
            return {"success": True}
        except Exception as e:
            logger.error(f"Act failed: {e}")
            return {"success": False, "error": str(e)}

    async def _verify(self, page, task: Dict) -> Dict[str, Any]:
        """Extract and validate data."""
        try:
            schema = task.get("expected_schema", {})
            if not schema:
                return {}
            extracted = await self.extractor.extract_with_confidence(page, schema)
            return extracted
        except Exception as e:
            logger.error(f"Verify failed: {e}")
            return {}

    async def _learn(self, task_id: str, plan: Dict, extracted: Dict, validity: Dict) -> None:
        """Update memory with learned patterns."""
        try:
            if validity.get("valid"):
                strategy = plan.get("strategy", "unknown")
                if strategy not in self.memory["successful_paths"]:
                    self.memory["successful_paths"][strategy] = []
                self.memory["successful_paths"][strategy].append(task_id)
        except Exception as e:
            logger.error(f"Learn failed: {e}")

    async def _attempt_recovery(self, page, error_info: Dict, task: Dict) -> Dict[str, Any]:
        """Recover from failures intelligently."""
        try:
            retry_strategy = await self.decision.decide_retry_strategy(
                {"type": "action_failure", "message": error_info.get("error", "unknown")},
                attempt_number=1,
            )
            if retry_strategy.get("strategy") == "RESET_BROWSER":
                await page.reload()
                await asyncio.sleep(2)
                return {"success": True, "strategy": "RESET_BROWSER"}
            return {"success": False, "error": "Recovery failed"}
        except Exception as e:
            logger.error(f"Recovery failed: {e}")
            return {"success": False, "error": str(e)}

    async def _execute_step(self, page, step: Dict) -> None:
        """Execute single action step."""
        step_type = step.get("type")
        if step_type == "fill_input":
            element = await self.navigator.find_element_by_visual_label(
                page, step.get("label", "")
            )
            if element:
                await self.navigator.fill_input_and_trigger_event(
                    page, element, step.get("value", "")
                )
        elif step_type == "click_button":
            button = await self.navigator.find_button_by_intent(
                page, step.get("intent", "")
            )
            if button:
                await button.click()
        elif step_type == "wait":
            await page.wait_for_load_state("networkidle", timeout=10000)

    async def _generate_action_steps(self, strategy: str, task: Dict) -> List[Dict]:
        """Generate action steps based on strategy."""
        steps = []
        if strategy == "form_search":
            steps.append({
                "type": "fill_input",
                "label": "Train Number",
                "value": task.get("train_number", ""),
                "description": f"Fill train number",
            })
            steps.append({
                "type": "click_button",
                "intent": "search",
                "description": "Click search button",
            })
            steps.append({"type": "wait", "description": "Wait for results"})
        return steps

    def _recommend_strategy(self, task_objective: str, page_type: str) -> str:
        """Recommend strategy based on task and page."""
        if "schedule" in task_objective.lower() and page_type == "search_form":
            return "form_search"
        return "generic"
