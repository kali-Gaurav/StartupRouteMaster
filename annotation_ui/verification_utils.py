"""Verification pipeline utilities and analytics."""
import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime


def verification_stats(verified_file: str = "datasets/verified_examples.jsonl") -> Dict[str, Any]:
    """Analyze verification status across all scenes."""
    verified_file = Path(verified_file)
    
    stats = {
        'total_verified': 0,
        'approved': 0,
        'approved_with_edits': 0,
        'rejected': 0,
        'status_breakdown': {},
        'timestamp': datetime.utcnow().isoformat() + 'Z',
    }
    
    if verified_file.exists():
        with open(verified_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    obj = json.loads(line)
                    status = obj.get('status', 'unknown')
                    stats['total_verified'] += 1
                    stats[status] = stats.get(status, 0) + 1
                    stats['status_breakdown'][status] = stats['status_breakdown'].get(status, 0) + 1
    
    return stats


def batch_approve_scenes(scene_ids: List[str], input_manifest: str = "datasets/labeling_manifest.jsonl", output_file: str = "datasets/verified_examples.jsonl"):
    """Batch approve multiple scenes (for testing or auto-approval of high-confidence scenes)."""
    input_manifest = Path(input_manifest)
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Load manifest
    manifest_by_id = {}
    if input_manifest.exists():
        with open(input_manifest, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    obj = json.loads(line)
                    manifest_by_id[obj['scene_id']] = obj
    
    # Append verifications
    with open(output_file, 'a', encoding='utf-8') as f:
        for scene_id in scene_ids:
            if scene_id in manifest_by_id:
                scene = manifest_by_id[scene_id]
                data = {
                    'scene_id': scene_id,
                    'status': 'approved',
                    'steps': scene.get('steps', []),
                    'task': scene.get('task'),
                    'screenshot': scene.get('screenshot'),
                    'timestamp': datetime.utcnow().isoformat() + 'Z'
                }
                f.write(json.dumps(data, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'stats':
        stats = verification_stats()
        print(json.dumps(stats, indent=2))
    else:
        print("Usage: python verification_utils.py stats")
