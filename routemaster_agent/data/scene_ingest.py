"""Convert recorded scenes into few-shot training examples and produce a labeling manifest.

Outputs:
- datasets/few_shot_examples.jsonl  (one JSON per line)
- datasets/labeling_manifest.jsonl (one JSON per line) for annotators

Usage:
    python -m routemaster_agent.data.scene_ingest --in datasets/raw_scenes --out examples.jsonl
"""
from pathlib import Path
import json
from typing import List, Dict, Any


def step_to_action(step: Dict[str, Any]) -> Dict[str, Any]:
    a = step.get('action', {})
    t = a.get('type')
    if t == 'input':
        return {'type': 'input', 'selector': a.get('selector'), 'value': a.get('value'), 'target': a.get('selector')}
    if t == 'select':
        return {'type': 'select', 'selector': a.get('selector'), 'value': a.get('value')}
    if t == 'click':
        return {'type': 'click', 'selector': a.get('selector')}
    # fallback mapping
    return {'type': t or 'unknown', 'selector': a.get('selector')}


def scenes_to_fewshot(input_dir: str | Path = 'datasets/raw_scenes', out_file: str | Path = 'datasets/few_shot_examples.jsonl') -> int:
    base = Path(input_dir)
    out = Path(out_file)
    out.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with out.open('w', encoding='utf-8') as fh:
        for scene_dir in sorted([p for p in base.iterdir() if p.is_dir()]):
            scene_json = scene_dir / 'scene.json'
            if not scene_json.exists():
                continue
            data = json.loads(scene_json.read_text(encoding='utf-8'))
            meta = data.get('meta', {})
            steps = data.get('steps', [])
            actions = [step_to_action(s) for s in steps]

            # derive a compact textual description for the scene
            description = meta.get('task') or f"Recorded scene {data.get('scene_id')}"

            example = {
                'scene_id': data.get('scene_id'),
                'task': meta.get('task', 'demo_record'),
                'description': description,
                'actions': actions,
                'scene_dir': str(scene_dir),
                'screenshot': str(scene_dir / (steps[0]['screenshot'] if steps else ''))
            }
            fh.write(json.dumps(example, ensure_ascii=False) + '\n')
            count += 1
    return count


def create_labeling_manifest(input_dir: str | Path = 'datasets/raw_scenes', out_file: str | Path = 'datasets/labeling_manifest.jsonl') -> int:
    base = Path(input_dir)
    out = Path(out_file)
    out.parent.mkdir(parents=True, exist_ok=True)

    instr = (
        "Instructions: For each recorded scene, verify the recorded action steps are correct. "
        "If a step is incorrect or missing, update the 'actions' array with the correct action(s). "
        "Actions should use the canonical schema: type (click/input/select), selector (CSS), value (for inputs)."
    )

    count = 0
    with out.open('w', encoding='utf-8') as fh:
        for scene_dir in sorted([p for p in base.iterdir() if p.is_dir()]):
            scene_json = scene_dir / 'scene.json'
            if not scene_json.exists():
                continue
            data = json.loads(scene_json.read_text(encoding='utf-8'))
            steps = data.get('steps', [])
            entry = {
                'scene_id': data.get('scene_id'),
                'scene_dir': str(scene_dir),
                'screenshot': str(scene_dir / (steps[0]['screenshot'] if steps else '')),
                'steps': steps,
                'task': data.get('meta', {}).get('task', ''),
                'instructions': instr,
            }
            fh.write(json.dumps(entry, ensure_ascii=False) + '\n')
            count += 1
    return count


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--in', dest='input_dir', default='datasets/raw_scenes')
    parser.add_argument('--out_examples', dest='out_examples', default='datasets/few_shot_examples.jsonl')
    parser.add_argument('--out_manifest', dest='out_manifest', default='datasets/labeling_manifest.jsonl')
    args = parser.parse_args()

    n = scenes_to_fewshot(args.input_dir, args.out_examples)
    m = create_labeling_manifest(args.input_dir, args.out_manifest)
    print(f"Wrote {n} few-shot examples and {m} manifest entries")