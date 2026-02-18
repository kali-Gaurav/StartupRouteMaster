"""Skill Library Generator — convert verified examples into reusable skills.

Transform verified automation examples into:
- Skill records with metadata
- Semantic embeddings (optional)
- Selector rankings
- Success/timing statistics

Usage:
    from skill_library_builder import SkillLibraryBuilder
    builder = SkillLibraryBuilder()
    skills = await builder.build_from_verified_examples('datasets/verified_examples.jsonl')
    builder.save_skills(skills, 'datasets/skill_registry.json')
"""
from typing import Dict, Any, List, Optional
import json
from pathlib import Path
from datetime import datetime
import hashlib
from collections import defaultdict


class SkillLibraryBuilder:
    """Convert verified scenes into reusable skills."""

    def __init__(self):
        self.skills = {}
        self._selector_stats = defaultdict(lambda: {'count': 0, 'success': 0, 'total_time_ms': 0})

    async def build_from_verified_examples(self, verified_file: str = 'datasets/verified_examples.jsonl') -> List[Dict[str, Any]]:
        """Convert verified examples into skill records.

        Returns:
            List of skill dicts
        """
        verified_file = Path(verified_file)
        skills = []

        if not verified_file.exists():
            return skills

        with open(verified_file, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                example = json.loads(line)
                if example.get('status') in ['approved', 'approved_with_edits']:
                    skill = await self._example_to_skill(example)
                    if skill:
                        skills.append(skill)

        return skills

    async def _example_to_skill(self, example: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Convert a single verified example into a skill record."""
        scene_id = example.get('scene_id')
        task = example.get('task', 'demo_task')
        steps = example.get('steps', [])

        if not steps:
            return None

        # Extract selector stats
        selectors_used = []
        action_sequence = []
        total_time_ms = 0
        success_count = 0

        for step in steps:
            action = step.get('action', {})
            meta = step.get('meta', {})

            action_type = action.get('type')
            selector = action.get('selector')
            value = action.get('value')
            strategy = meta.get('strategy')
            confidence = meta.get('selector_confidence', 0.5)
            time_ms = meta.get('time_to_success_ms', 0)
            success = meta.get('success', True)

            # Track selector statistics
            if selector:
                selectors_used.append({
                    'selector': selector,
                    'type': action_type,
                    'strategy': strategy,
                    'confidence': confidence,
                    'time_ms': time_ms,
                    'success': success,
                })
                self._selector_stats[selector]['count'] += 1
                self._selector_stats[selector]['success'] += (1 if success else 0)
                self._selector_stats[selector]['total_time_ms'] += time_ms

            # Build action record
            action_record = {
                'type': action_type,
                'selector': selector,
                'target': action.get('target',action_type) or selector,
            }
            if value:
                action_record['value'] = value
            action_sequence.append(action_record)

            total_time_ms += time_ms if time_ms else 0
            success_count += (1 if success else 0)

        # Generate skill name from task + scene
        skill_name = f"{task.replace(' ', '_').lower()}_{scene_id.split('_')[-1]}"

        # Compute skill properties
        success_rate = success_count / len(steps) if steps else 0.0
        avg_time_ms = int(total_time_ms / len(steps)) if steps else 0
        avg_selector_confidence = sum(s.get('confidence', 0) for s in selectors_used) / len(selectors_used) if selectors_used else 0.5

        skill = {
            'skill_id': hashlib.md5(skill_name.encode()).hexdigest()[:12],
            'skill_name': skill_name,
            'source_scene': scene_id,
            'scene_status': example.get('status'),
            'task': task,
            'context': self._infer_context(task),
            'action_sequence': action_sequence,
            'selectors_used': selectors_used,
            'metrics': {
                'success_rate': round(success_rate, 3),
                'avg_time_ms': avg_time_ms,
                'avg_selector_confidence': round(avg_selector_confidence, 3),
                'step_count': len(steps),
                'selector_count': len(selectors_used),
            },
            'created_at': datetime.utcnow().isoformat() + 'Z',
            'embeddings': None,  # populated by embedding service later
        }

        return skill

    @staticmethod
    def _infer_context(task: str) -> str:
        """Infer page/context type from task."""
        task_lower = task.lower()
        if 'train' in task_lower or 'schedule' in task_lower:
            return 'ntes_schedule'
        if 'search' in task_lower:
            return 'booking_search'
        if 'seat' in task_lower:
            return 'seat_selection'
        return 'generic_page'

    def save_skills(self, skills: List[Dict[str, Any]], output_file: str = 'datasets/skill_registry.json'):
        """Save skills to JSON file."""
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Group by context
        skills_by_context = defaultdict(list)
        for skill in skills:
            skills_by_context[skill.get('context', 'generic')].append(skill)

        registry = {
            'metadata': {
                'version': '1.0',
                'created_at': datetime.utcnow().isoformat() + 'Z',
                'skill_count': len(skills),
                'contexts': list(skills_by_context.keys()),
            },
            'skills': skills,
            'by_context': {
                ctx: [s['skill_name'] for s in skill_list]
                for ctx, skill_list in skills_by_context.items()
            },
            'selector_stats': dict(self._selector_stats),
        }

        output_file.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding='utf-8')
        return output_file

    def get_selector_rankings(self) -> List[Dict[str, Any]]:
        """Rank selectors by success rate and speed."""
        rankings = []
        for selector, stats in self._selector_stats.items():
            if stats['count'] == 0:
                continue
            success_rate = stats['success'] / stats['count']
            avg_time = stats['total_time_ms'] / stats['count']
            # Score: 50% success, 30% speed (inverse), 20% usage frequency
            score = (
                success_rate * 0.5 +
                (1.0 / (1.0 + avg_time / 1000.0)) * 0.3 +  # normalized speed
                (min(stats['count'] / 10.0, 1.0)) * 0.2  # usage frequency capped at 10
            )
            rankings.append({
                'selector': selector,
                'success_rate': round(success_rate, 3),
                'avg_time_ms': int(avg_time),
                'usage_count': stats['count'],
                'score': round(score, 3),
            })

        # Sort by score descending
        rankings.sort(key=lambda x: x['score'], reverse=True)
        return rankings


async def build_skill_library(verified_file: str = 'datasets/verified_examples.jsonl', output_file: str = 'datasets/skill_registry.json'):
    """Convenience function to build and save skill library in one call."""
    builder = SkillLibraryBuilder()
    skills = await builder.build_from_verified_examples(verified_file)
    output_path = builder.save_skills(skills, output_file)
    
    rankings = builder.get_selector_rankings()
    
    return {
        'skill_count': len(skills),
        'output_file': str(output_path),
        'top_selectors': rankings[:10],
    }


if __name__ == '__main__':
    import asyncio
    result = asyncio.run(build_skill_library())
    print(f"✅ Built skill library: {result['skill_count']} skills")
    print(f"📁 Saved to: {result['output_file']}")
    print(f"🏆 Top selectors by rank:")
    for i, sel in enumerate(result['top_selectors'], 1):
        print(f"  {i}. {sel['selector'][:40]} (score: {sel['score']}, success: {sel['success_rate']})")
