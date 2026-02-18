import json
from pathlib import Path

from routemaster_agent.data.scene_ingest import scenes_to_fewshot, create_labeling_manifest


def test_scene_ingest_creates_files(tmp_path):
    # prepare a small fake dataset with one scene
    base = tmp_path / 'datasets' / 'raw_scenes'
    sdir = base / 'demo_test_001'
    sdir.mkdir(parents=True)
    scene_json = {
        'scene_id': 'demo_test_001',
        'meta': {'task': 'demo_record'},
        'steps': [
            {'step': 1, 'action': {'type': 'input', 'selector': '#q', 'value': 'X'}, 'meta': {'strategy': 'dom'}, 'screenshot': 'step_001.png', 'dom': '<html/>'}
        ]
    }
    (sdir / 'scene.json').write_text(json.dumps(scene_json))
    (sdir / 'step_001.png').write_bytes(b'PNG')

    fe = tmp_path / 'datasets' / 'few_shot_examples.jsonl'
    mf = tmp_path / 'datasets' / 'labeling_manifest.jsonl'

    n = scenes_to_fewshot(base, fe)
    m = create_labeling_manifest(base, mf)

    assert n == 1
    assert m == 1

    lines = fe.read_text(encoding='utf-8').strip().splitlines()
    assert len(lines) == 1
    ex = json.loads(lines[0])
    assert ex['scene_id'] == 'demo_test_001'

    lines2 = mf.read_text(encoding='utf-8').strip().splitlines()
    assert len(lines2) == 1
    man = json.loads(lines2[0])
    assert man['scene_id'] == 'demo_test_001'