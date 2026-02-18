"""ReasoningController — Skill-first decision loop with Gemini fallback.

Primary flow:
 - infer page context via VisionAI
 - retrieve skills via SkillRetriever
 - if top skill confidence > threshold: execute via SkillExecutor
 - else: call Gemini fallback (gemini.propose_actions)

Also updates skill metrics (simple EMA) after execution to form feedback loop.
"""
from typing import Optional, Dict, Any
import logging
import json
from pathlib import Path
import asyncio
import tempfile
import os

logger = logging.getLogger(__name__)


class ReasoningController:
    def __init__(
        self,
        skill_retriever=None,
        skill_executor=None,
        gemini_client=None,
        vision_ai=None,
        skill_registry_path: str = "datasets/skill_registry.json",
    ):
        self.skill_retriever = skill_retriever
        self.skill_executor = skill_executor
        self.gemini = gemini_client
        self.vision = vision_ai
        self.skill_registry_path = Path(skill_registry_path)
        # lock to guard EMA updates and registry file writes
        self._skill_lock = asyncio.Lock()

    async def infer_context(self, page) -> Optional[str]:
        if not self.vision:
            return None
        try:
            info = await self.vision.analyze_page_structure(page)
            # prefer an explicit 'context' key produced by vision
            if isinstance(info, dict):
                if 'context' in info:
                    return info['context']
                # fallback heuristics
                title = info.get('title', '')
                if 'train' in (title or '').lower() or 'schedule' in (title or '').lower():
                    return 'ntes_schedule'
                if 'search' in (title or '').lower():
                    return 'booking_search'
            return None
        except Exception as e:
            logger.debug(f"Context inference failed: {e}")
            return None

    async def reason_and_act(self, page, task: str, threshold: float = 0.65) -> Dict[str, Any]:
        # OBSERVE
        context = await self.infer_context(page)
        logger.info(f"Inferred context: {context} for task={task}")

        # RETRIEVE
        if self.skill_retriever:
            skills = await self.skill_retriever.retrieve_skills(context or 'generic_page', task=task, max_results=5)
        else:
            skills = []

        if skills:
            top = skills[0]
            score = top.get('_retrieval_score') or top.get('metrics', {}).get('success_rate', 0.0)
            logger.info(f"Top skill: {top.get('skill_name')} score={score}")
            if score >= threshold and self.skill_executor:
                # EXECUTE
                try:
                    result = await self.skill_executor.execute_skill(top, page=page)
                except Exception as e:
                    logger.warning(f"Skill execution raised exception: {e}")
                    # update EMA as failure
                    await self._update_skill_score(top.get('skill_id') or top.get('skill_name'), success=False)
                    if self.gemini:
                        try:
                            actions = await self.gemini.propose_actions(page, {'task': task})
                        except Exception:
                            actions = []
                        logger.info("Skill execution errored; falling back to Gemini reasoning")
                        return {'success': False, 'fallback': True, 'actions': actions, 'from_skill': top.get('skill_name')}
                    return {'success': False, 'fallback': False, 'from_skill': top.get('skill_name'), 'reason': 'skill_exception'}

                # FEEDBACK
                await self._update_skill_score(top.get('skill_id') or top.get('skill_name'), success=result.get('success', False))
                # If skill succeeded, return; otherwise fall back to Gemini if available
                if result.get('success'):
                    result['from_skill'] = top.get('skill_name')
                    return result
                else:
                    # attempt Gemini fallback on failure
                    if self.gemini:
                        try:
                            actions = await self.gemini.propose_actions(page, {'task': task})
                        except Exception:
                            actions = []
                        logger.info("Skill execution failed; falling back to Gemini reasoning")
                        return {'success': False, 'fallback': True, 'actions': actions, 'from_skill': top.get('skill_name')}
                    return {'success': False, 'fallback': False, 'from_skill': top.get('skill_name'), 'reason': 'skill_failed'}

        # FALLBACK: Gemini reasoning
        if self.gemini:
            try:
                actions = await self.gemini.propose_actions(page, {'task': task})
            except Exception:
                actions = []
            logger.info("Falling back to Gemini reasoning")
            return {'success': False, 'fallback': True, 'actions': actions}

        return {'success': False, 'fallback': False, 'reason': 'No skills or Gemini available'}

    async def _update_skill_score(self, skill_id: str, success: bool, alpha: float = 0.1):
        """Simple EMA update of skill success_rate stored in skill_registry.json.

        If `skill_id` matches skill_name when skill_id not present.
        """
        if not self.skill_registry_path.exists():
            logger.debug("Skill registry not found; skipping score update")
            return
        try:
            # perform update under lock to avoid concurrent writes
            async with self._skill_lock:
                text = self.skill_registry_path.read_text(encoding='utf-8')
                data = json.loads(text)
                changed = False
                for skill in data.get('skills', []):
                    if skill.get('skill_id') == skill_id or skill.get('skill_name') == skill_id:
                        old = skill.get('metrics', {}).get('success_rate', 0.5)
                        new = old * (1 - alpha) + (1.0 if success else 0.0) * alpha
                        skill.setdefault('metrics', {})['success_rate'] = round(new, 4)
                        changed = True
                        logger.info(f"Updated skill {skill.get('skill_name')} success_rate: {old} -> {new}")
                        break

                if changed:
                    # atomic write: write to temp file then replace
                    tmp_dir = str(self.skill_registry_path.parent)
                    fd, tmp_path = tempfile.mkstemp(dir=tmp_dir, prefix=self.skill_registry_path.name, text=True)
                    try:
                        with os.fdopen(fd, 'w', encoding='utf-8') as tf:
                            json.dump(data, tf, indent=2, ensure_ascii=False)
                            tf.flush()
                            os.fsync(tf.fileno())
                        os.replace(tmp_path, str(self.skill_registry_path))
                    finally:
                        if os.path.exists(tmp_path):
                            try:
                                os.remove(tmp_path)
                            except Exception:
                                pass
        except Exception as e:
            logger.warning(f"Failed to update skill registry: {e}")


__all__ = ['ReasoningController']
