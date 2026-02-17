"""
Skill Trainer — bootstrap agent skills using Gemini few-shot prompts.

This module provides a lightweight training harness that:
- Defines a JSON `action` schema the agent understands (click/input/scroll/select/extract/complete)
- Builds few-shot prompts (scene + desired steps) for Gemini to propose action sequences
- Validates/normalizes Gemini output into the agent `action` format that NavigatorAI/ExtractionAI can execute

The goal is to bootstrap supervised examples for the agent (behavioral cloning / prompt-first approach)
so the `ReasoningController` can later rely on structured actions produced by Gemini.

This is intentionally simple and testable (no network calls here — uses GeminiClient abstraction).
"""
from typing import List, Dict, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)


# canonical action schema used across the agent
# Example:
# {"type": "input", "target": "Train Number", "selector": "#trainNo", "value": "12345", "confidence": 0.98}

DEFAULT_FEW_SHOT_EXAMPLES = [
    {
        "scene": "NTES - Train Schedule search page with Train No input and Get Schedule button",
        "task": "Extract train schedule for train number 12345",
        "actions": [
            {"type": "input", "target": "Train Number", "selector": "input[name=txtTrainNo]", "value": "12345"},
            {"type": "click", "target": "Get Schedule", "selector": "button:has-text('Get Schedule')"},
            {"type": "wait", "wait_for": "table.schedule-results"},
            {"type": "extract_table", "selector": "table.schedule-results", "output_format": "rows"},
            {"type": "complete", "result": "schedule_extracted"}
        ]
    },
    {
        "scene": "IRCTC - Booking widget with origin/destination/date and Search button",
        "task": "Find trains and seat availability from Jaipur to Kota on 18-Feb-2026",
        "actions": [
            {"type": "input", "target": "From", "selector": "input[id='fromStation']", "value": "Jaipur (JP)"},
            {"type": "input", "target": "To", "selector": "input[id='toStation']", "value": "Kota (KOTA)"},
            {"type": "input", "target": "Date", "selector": "input[name='date']", "value": "18-02-2026"},
            {"type": "click", "target": "Search Trains", "selector": "button:has-text('Search Trains')"},
            {"type": "wait", "wait_for": "div.train-list"},
            {"type": "extract_list", "selector": "div.train-list .train-card"},
            {"type": "complete", "result": "trains_listed"}
        ]
    },
]


class SkillTrainer:
    """Bootstrap skill examples using Gemini few-shot prompting."""

    def __init__(self, gemini_client):
        self.gemini = gemini_client

    def _build_prompt(self, scene: Dict[str, Any], task: Dict[str, Any], examples: Optional[List[Dict[str, Any]]] = None) -> str:
        """Create a few-shot prompt asking Gemini to produce a JSON action sequence for the scene+task."""
        examples = examples or DEFAULT_FEW_SHOT_EXAMPLES

        prompt_parts = [
            "You are an assistant that converts a webpage screenshot/DOM 'scene' and a task into a sequence of exact actions that an automation agent can execute.",
            "Return ONLY valid JSON: an array of actions. Each action must be one of: click, input, select, scroll, wait, extract_table, extract_list, complete, fallback.",
            "Action format example: {type: 'click', selector: 'button:has-text(\'Search\')', target: 'Search'}",
            "\nFEW-SHOT EXAMPLES:\n"
        ]

        for ex in examples:
            prompt_parts.append(json.dumps({
                'scene': ex['scene'],
                'task': ex['task'],
                'actions': ex['actions']
            }, indent=2))

        prompt_parts.append("\nNOW: Produce actions for the following scene and task:")
        prompt_parts.append(json.dumps({'scene': scene, 'task': task}, indent=2))

        prompt_parts.append("\nReturn only a JSON array of action objects. Do not include any other text.")

        return "\n\n".join(prompt_parts)

    async def propose_actions(self, scene: Dict[str, Any], task: Dict[str, Any], examples: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """Ask Gemini to propose an action sequence for a scene+task and normalize the output.

        Returns a list of normalized action dicts (may be empty on failure).
        """
        if not self.gemini or not getattr(self.gemini, 'enabled', False):
            logger.warning("Gemini not available — SkillTrainer cannot propose actions")
            return []

        prompt = self._build_prompt(scene, task, examples)
        response = await self.gemini.generate(prompt)

        # `generate` returns parsed JSON when possible; accept dict/list or text
        actions = []
        if isinstance(response, list):
            actions = response
        elif isinstance(response, dict):
            # try common keys
            if 'actions' in response and isinstance(response['actions'], list):
                actions = response['actions']
            else:
                # fallback — maybe the model returned {'text': '...'}
                text = response.get('text', '')
                try:
                    actions = json.loads(text)
                except Exception:
                    actions = []
        else:
            # string fallback
            try:
                actions = json.loads(str(response))
            except Exception:
                actions = []

        # Basic normalization + validation
        normalized = []
        for act in actions:
            if not isinstance(act, dict) or 'type' not in act:
                continue
            norm = {
                'type': act.get('type'),
                'selector': act.get('selector'),
                'target': act.get('target') or act.get('field') or act.get('label'),
                'value': act.get('value'),
                'wait_for': act.get('wait_for'),
                'confidence': float(act.get('confidence', 0.8))
            }
            normalized.append({k: v for k, v in norm.items() if v is not None})

        return normalized


# lightweight helper to convert a sequence of actions into a short human-readable plan
def actions_to_plan(actions: List[Dict[str, Any]]) -> str:
    lines = []
    for a in actions:
        t = a.get('type')
        sel = a.get('selector') or a.get('target') or ''
        val = a.get('value', '')
        lines.append(f"{t} -> {sel} {('= ' + val) if val else ''}")
    return "\n".join(lines)
