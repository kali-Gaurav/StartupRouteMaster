"""
Reasoning Controller - Core AI loop for autonomous decision making.

Implements: OBSERVE -> THINK -> DECIDE -> ACT -> VERIFY -> LEARN

Uses Gemini for THINK stage, tools for ACT stage.
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import asyncio
import json

from .agent_state_manager import agent_state_manager, AgentState
from .gemini_client import GeminiClient
from routemaster_agent.scrapers.browser import BrowserManager
from routemaster_agent.intelligence.selector_registry import record_selector_result


class ReasoningController:
    def __init__(self):
        self.gemini = GeminiClient()
        self.browser_mgr = None
        self.tools = {}
        self.max_iterations = 10
        self.confidence_threshold = 0.7

    async def initialize(self):
        """Initialize browser and tools."""
        self.browser_mgr = BrowserManager()

    async def execute_task(self, task_definition: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a task using the reasoning loop.

        Args:
            task_definition: Task DSL dict (e.g., {'type': 'update_train_schedule', 'train_number': '12951'})

        Returns:
            Result dict with status, data, confidence, etc.
        """
        task_id = task_definition.get('id', f"task_{datetime.utcnow().timestamp()}")
        agent_state_manager.transition_to(AgentState.PLANNING, task_id=task_id)

        try:
            result = await self._reasoning_loop(task_definition)
            agent_state_manager.transition_to(AgentState.LEARNING, task_id=task_id)
            agent_state_manager.transition_to(AgentState.IDLE)
            return result
        except Exception as e:
            agent_state_manager.transition_to(AgentState.ERROR_RECOVERY, task_id=task_id, metadata={'error': str(e)})
            agent_state_manager.transition_to(AgentState.IDLE)
            return {'status': 'error', 'message': str(e), 'task_id': task_id}

    async def _reasoning_loop(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Main reasoning loop."""
        iteration = 0
        context = {'task': task, 'observations': [], 'actions_taken': [], 'confidence_scores': []}

        while iteration < self.max_iterations:
            iteration += 1

            # OBSERVE
            observation = await self._observe(context)
            context['observations'].append(observation)

            # THINK
            thought, confidence = await self._think(context)
            context['confidence_scores'].append(confidence)

            # DECIDE
            decision = await self._decide(thought, confidence, context)

            if decision['action'] == 'complete':
                return decision['result']
            elif decision['action'] == 'fallback':
                return await self._fallback_to_deterministic(task)

            # ACT
            action_result = await self._act(decision)
            context['actions_taken'].append(action_result)

            # VERIFY
            verification = await self._verify(action_result, context)
            if verification['success']:
                continue
            else:
                break

        return {'status': 'max_iterations', 'context': context}

    async def _observe(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Observe current state: page content, task progress, etc."""
        observation = {
            'timestamp': datetime.utcnow().isoformat(),
            'task_progress': len(context['actions_taken']),
            'current_page': None,
            'elements_found': []
        }

        if self.browser_mgr and hasattr(self.browser_mgr, 'current_page'):
            try:
                screenshot_path = f"data_lake/raw/screenshots/obs_{datetime.utcnow().timestamp()}.png"
                await self.browser_mgr.current_page.screenshot(path=screenshot_path)
                html = await self.browser_mgr.current_page.content()
                observation.update({
                    'screenshot_path': screenshot_path,
                    'html_content': html[:5000],
                    'url': self.browser_mgr.current_page.url
                })
            except Exception as e:
                observation['error'] = str(e)

        return observation

    async def _think(self, context: Dict[str, Any]) -> Tuple[str, float]:
        """Use Gemini to analyze observation and generate thought or structured action JSON.

        Supports both legacy text 'thought' responses and structured JSON with an 'action' or 'actions' array.
        """
        prompt = self._build_think_prompt(context)
        response = await self.gemini.generate(prompt)

        # Normalize response: allow dict|list|string
        thought = 'Unable to determine next action'
        confidence = 0.5

        try:
            if isinstance(response, dict):
                # prefer explicit thought and confidence
                if 'thought' in response:
                    thought = response['thought']
                elif 'action' in response or 'actions' in response or 'steps' in response:
                    # return JSON string so _parse_action_from_thought can decode
                    thought = json.dumps(response)

                confidence = float(response.get('confidence', response.get('layout_confidence', 0.5)))

            elif isinstance(response, list):
                # list of actions — stringify for parser
                thought = json.dumps({'actions': response})
                confidence = 0.9

            else:
                # string fallback
                text = str(response)
                thought = text[:4000]
        except Exception:
            thought = str(response)

        return thought, float(confidence)


    def _build_think_prompt(self, context: Dict[str, Any]) -> str:
        """Build Gemini prompt for THINK stage."""
        task = context['task']
        last_observation = context['observations'][-1] if context['observations'] else {}

        prompt = f"""
You are an autonomous railway data collection AI agent.

Current Task: {json.dumps(task)}

Last Observation: {json.dumps(last_observation)}

Actions Taken So Far: {json.dumps(context['actions_taken'])}

Your goal is to determine the next intelligent action to complete the task.

Think step-by-step:
1. What is the current state of the task?
2. What data do we still need?
3. What action should we take next?
4. How confident are you in this decision?

Return JSON with:
{{
  "thought": "Your reasoning and next action plan",
  "confidence": 0.0-1.0
}}
"""
        return prompt

    async def _decide(self, thought: str, confidence: float, context: Dict[str, Any]) -> Dict[str, Any]:
        """Decide on action based on thought and confidence."""
        if confidence < self.confidence_threshold:
            return {'action': 'fallback', 'reason': f'Low confidence: {confidence}'}

        action = self._parse_action_from_thought(thought)

        if action.get('type') == 'complete':
            return {'action': 'complete', 'result': action.get('result', {})}

        return {'action': 'continue', 'next_action': action}

    def _parse_action_from_thought(self, thought: str) -> Dict[str, Any]:
        """Parse action from Gemini thought.

        Accepts either free-text reasoning (legacy) or structured JSON (preferred). When
        JSON is provided it should contain either `action` or `actions` / `steps`.
        """
        # Try JSON first
        try:
            payload = json.loads(thought)
            # single action
            if isinstance(payload, dict) and payload.get('type'):
                return payload
            # wrapped action(s)
            if isinstance(payload, dict) and 'action' in payload:
                return payload['action']
            if isinstance(payload, dict) and 'actions' in payload and isinstance(payload['actions'], list):
                return payload['actions'][0]
            if isinstance(payload, dict) and 'steps' in payload and isinstance(payload['steps'], list):
                return payload['steps'][0]
        except Exception:
            pass

        # Fallback — legacy string parsing
        text = (thought or '').lower()
        if 'complete' in text:
            return {'type': 'complete', 'result': {'status': 'success'}}
        if 'click' in text:
            return {'type': 'click', 'target': 'button'}
        if 'input' in text or 'enter' in text:
            # try to extract a number-like token
            import re
            m = re.search(r"(\d{3,6})", thought)
            return {'type': 'input', 'value': m.group(1) if m else ''}

        return {'type': 'observe'}

    async def _act(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the decided action using tools."""
        action = decision.get('next_action', {})
        action_type = action.get('type')

        if action_type in self.tools:
            tool = self.tools[action_type]
            result = await tool.execute(action)
            return result
        else:
            return {'status': 'error', 'message': f'No tool for action type: {action_type}'}

    async def _verify(self, action_result: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Verify if action was successful."""
        success = action_result.get('status') == 'success'
        return {'success': success, 'details': action_result}

    async def _fallback_to_deterministic(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback to existing deterministic scrapers."""
        print(f"Falling back to deterministic mode for task: {task}")
        from routemaster_agent.scrapers.ntes_agent import NTESAgent
        from routemaster_agent.pipeline.processor import DataPipeline

        agent = NTESAgent()
        pipeline = DataPipeline()

        train_no = task.get('train_number', '12951')
        schedule = await agent.get_schedule(self.browser_mgr.current_page, train_no)
        return {'status': 'fallback_success', 'data': schedule}

    async def cleanup(self):
        """Cleanup resources."""
        if self.browser_mgr:
            await self.browser_mgr.close()
