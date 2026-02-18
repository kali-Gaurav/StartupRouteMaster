import pytest
import json
import asyncio
from pathlib import Path
from routemaster_agent.skills.skill_library_builder import SkillLibraryBuilder, build_skill_library
from routemaster_agent.skills.skill_retrieval import SkillRetriever, SkillExecutor


@pytest.mark.asyncio
async def test_skill_library_builder(tmp_path):
    """Test converting verified examples to skills."""
    # Create fake verified examples
    verified_file = tmp_path / 'verified.jsonl'
    with open(verified_file, 'w', encoding='utf-8') as f:
        example = {
            'scene_id': 'demo_scene_001',
            'status': 'approved',
            'task': 'train_search',
            'steps': [
                {
                    'step': 1,
                    'action': {'type': 'input', 'selector': '#train_no', 'value': '12345'},
                    'meta': {'strategy': 'css', 'selector_confidence': 0.95, 'time_to_success_ms': 100, 'success': True}
                },
                {
                    'step': 2,
                    'action': {'type': 'click', 'selector': '#search'},
                    'meta': {'strategy': 'css', 'selector_confidence': 0.92, 'time_to_success_ms': 50, 'success': True}
                }
            ]
        }
        f.write(json.dumps(example) + '\n')

    # Build skills
    builder = SkillLibraryBuilder()
    skills = await builder.build_from_verified_examples(str(verified_file))

    assert len(skills) == 1
    skill = skills[0]
    assert skill['task'] == 'train_search'
    assert skill['action_sequence'][0]['type'] == 'input'
    assert skill['metrics']['step_count'] == 2
    assert skill['metrics']['avg_selector_confidence'] > 0.9


def test_skill_registry_save(tmp_path):
    """Test saving skill registry."""
    builder = SkillLibraryBuilder()
    skills = [
        {
            'skill_id': 'skill_001',
            'skill_name': 'train_search_1',
            'context': 'ntes_schedule',
            'action_sequence': [{'type': 'input', 'selector': '#q', 'value': 'test'}],
            'metrics': {'success_rate': 0.9, 'avg_time_ms': 100},
        }
    ]
    
    output_file = tmp_path / 'skills.json'
    builder.save_skills(skills, str(output_file))

    assert output_file.exists()
    registry = json.loads(output_file.read_text(encoding='utf-8'))
    assert registry['metadata']['skill_count'] == 1
    assert 'ntes_schedule' in registry['by_context']


@pytest.mark.asyncio
async def test_skill_retriever(tmp_path):
    """Test skill retrieval by context."""
    # Create registry
    registry = {
        'metadata': {'version': '1.0'},
        'skills': [
            {
                'skill_id': 'skill_001',
                'skill_name': 'ntes_search',
                'context': 'ntes_schedule',
                'metrics': {'success_rate': 0.95, 'avg_time_ms': 150},
            },
            {
                'skill_id': 'skill_002',
                'skill_name': 'generic_input',
                'context': 'generic_page',
                'metrics': {'success_rate': 0.8, 'avg_time_ms': 200},
            }
        ],
        'by_context': {
            'ntes_schedule': ['skill_001'],
            'generic_page': ['skill_002']
        }
    }
    registry_file = tmp_path / 'registry.json'
    registry_file.write_text(json.dumps(registry))

    # Test retrieval
    retriever = SkillRetriever(str(registry_file))
    
    # Exact match
    skills = await retriever.retrieve_skills('ntes_schedule')
    assert len(skills) > 0
    assert skills[0]['skill_name'] == 'ntes_search'
    
    # Generic fallback
    skills = await retriever.retrieve_skills('unknown_context')
    assert len(skills) > 0


@pytest.mark.asyncio
async def test_build_skill_library_integration(tmp_path):
    """Test full pipeline: verified examples → skill library."""
    # Create verified examples
    verified_file = tmp_path / 'verified.jsonl'
    with open(verified_file, 'w', encoding='utf-8') as f:
        for i in range(3):
            example = {
                'scene_id': f'demo_{i}',
                'status': 'approved',
                'task': 'search_trains',
                'steps': [
                    {'step': 1, 'action': {'type': 'input', 'selector': f'#input_{i}', 'value': 'test'},
                     'meta': {'strategy': 'css', 'selector_confidence': 0.9, 'time_to_success_ms': 100, 'success': True}}
                ]
            }
            f.write(json.dumps(example) + '\n')

    # Build library
    output_file = tmp_path / 'skills.json'
    builder = SkillLibraryBuilder()
    skills = await builder.build_from_verified_examples(str(verified_file))
    builder.save_skills(skills, str(output_file))

    assert output_file.exists()
    assert len(skills) == 3
    
    # Verify registry structure
    registry = json.loads(output_file.read_text(encoding='utf-8'))
    assert registry['metadata']['skill_count'] == 3
    assert len(registry['skills']) == 3
