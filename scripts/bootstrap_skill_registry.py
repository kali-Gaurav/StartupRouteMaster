"""Bootstrap Skill Registry Generator

Scans `datasets/raw_scenes/*/scene.json`, auto-approves high-confidence steps,
and emits `datasets/skill_registry_bootstrap.json` (and optionally prints a summary).

Usage:
    python scripts/bootstrap_skill_registry.py

Criteria (defaults):
    selector_confidence >= 0.65 OR (selector_confidence is null and strategy == 'dom')
    AND success == True
    AND time_to_success_ms <= 2000

Bootstrap skills are marked with "source": "bootstrap_auto" so they can be
distinguished from human-verified skills.
"""
from pathlib import Path
import json
import hashlib
from datetime import datetime
from collections import defaultdict


RAW_ROOT = Path('datasets/raw_scenes')
OUT_FILE = Path('datasets/skill_registry_bootstrap.json')


def infer_context_from_scene(scene_meta: dict) -> str:
    task = (scene_meta.get('task') or '').lower()
    if 'train' in task or 'schedule' in task:
        return 'ntes_schedule'
    if 'search' in task:
        return 'booking_search'
    return 'generic_page'


def build_skill_from_scene(scene_path: Path, conf_threshold=0.65, time_threshold_ms=2000):
    data = json.loads(scene_path.read_text(encoding='utf-8'))
    scene_id = data.get('scene_id') or scene_path.parent.name
    meta = data.get('meta', {})
    steps = data.get('steps', [])

    selected_steps = []
    selectors_used = []
    total_time = 0
    success_count = 0

    for s in steps:
        m = s.get('meta', {})
        success = m.get('success', False)
        conf = m.get('selector_confidence')
        strategy = m.get('strategy')
        t_ms = m.get('time_to_success_ms') or 0

        meets_conf = False
        if conf is not None:
            try:
                meets_conf = float(conf) >= conf_threshold
            except Exception:
                meets_conf = False
        else:
            meets_conf = (strategy == 'dom')

        if success and meets_conf and t_ms <= time_threshold_ms:
            action = s.get('action', {})
            selected_steps.append(action)
            selectors_used.append({
                'selector': action.get('selector'),
                'type': action.get('type'),
                'strategy': strategy,
                'confidence': conf if conf is not None else 0.5,
                'time_ms': t_ms,
                'success': True,
            })
            total_time += t_ms
            success_count += 1

    if not selected_steps:
        return None

    # Build skill record
    skill_name = f"bootstrap_{scene_id}"
    skill_id = hashlib.md5(skill_name.encode()).hexdigest()[:12]
    avg_time = int(total_time / len(selected_steps)) if selected_steps else 0
    success_rate = round(success_count / len(steps) if steps else 1.0, 3)

    skill = {
        'skill_id': skill_id,
        'skill_name': skill_name,
        'source_scene': scene_id,
        'source': 'bootstrap_auto',
        'task': meta.get('task', 'demo_task'),
        'context': infer_context_from_scene(meta),
        'action_sequence': [],
        'selectors_used': selectors_used,
        'metrics': {
            'success_rate': success_rate,
            'avg_time_ms': avg_time,
            'step_count': len(selected_steps),
        },
        'created_at': datetime.utcnow().isoformat() + 'Z'
    }

    # normalize action sequence
    for a in selected_steps:
        rec = {
            'type': a.get('type'),
            'selector': a.get('selector'),
        }
        if 'value' in a:
            rec['value'] = a.get('value')
        skill['action_sequence'].append(rec)

    return skill


def main():
    scenes = sorted(RAW_ROOT.glob('*/scene.json'))
    skills = []
    selector_stats = defaultdict(lambda: {'count': 0, 'success': 0, 'total_time_ms': 0})

    for s in scenes:
        skill = build_skill_from_scene(s)
        if skill:
            skills.append(skill)
            for sel in skill.get('selectors_used', []):
                k = sel.get('selector')
                if not k:
                    continue
                selector_stats[k]['count'] += 1
                selector_stats[k]['success'] += (1 if sel.get('success') else 0)
                selector_stats[k]['total_time_ms'] += sel.get('time_ms', 0)

    registry = {
        'metadata': {
            'version': 'bootstrap-1.0',
            'created_at': datetime.utcnow().isoformat() + 'Z',
            'skill_count': len(skills),
        },
        'skills': skills,
        'by_context': {},
        'selector_stats': dict(selector_stats),
    }

    # index by context
    by_ctx = {}
    for sk in skills:
        ctx = sk.get('context', 'generic')
        by_ctx.setdefault(ctx, []).append(sk.get('skill_name'))
    registry['by_context'] = by_ctx

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding='utf-8')

    print(f"Wrote {len(skills)} bootstrap skills to {OUT_FILE}")


if __name__ == '__main__':
    main()
