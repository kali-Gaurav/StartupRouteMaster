import pytest
import asyncio
import json

from routemaster_agent.ai.skill_trainer import SkillTrainer, actions_to_plan


class DummyGemini:
    def __init__(self):
        self.enabled = True

    async def generate(self, prompt):
        # return a valid JSON array of actions as if Gemini responded correctly
        return [
            {"type": "input", "selector": "input[name=txtTrainNo]", "value": "12345"},
            {"type": "click", "selector": "button:has-text('Get Schedule')"},
            {"type": "wait", "wait_for": "table.schedule-results"},
            {"type": "extract_table", "selector": "table.schedule-results"},
            {"type": "complete", "result": "schedule_extracted"}
        ]


@pytest.mark.asyncio
async def test_propose_actions_from_dummy_gemini():
    gem = DummyGemini()
    trainer = SkillTrainer(gem)

    scene = {"page": "NTES schedule"}
    task = {"objective": "get_schedule", "train_number": "12345"}

    actions = await trainer.propose_actions(scene, task)
    assert isinstance(actions, list)
    assert len(actions) >= 1
    assert actions[0]['type'] == 'input'

    plan_text = actions_to_plan(actions)
    assert 'input' in plan_text and 'click' in plan_text


def test_actions_to_plan_formatting():
    actions = [
        {"type": "input", "selector": "#a", "value": "x"},
        {"type": "click", "selector": "#go"}
    ]
    p = actions_to_plan(actions)
    assert 'input' in p and 'click' in p
