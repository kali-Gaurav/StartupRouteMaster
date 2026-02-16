"""
Task: Update Train Schedule

DSL Definition for updating a train's schedule from NTES.
"""

from typing import Dict, Any, List

# Task metadata
TASK_METADATA = {
    'name': 'update_train_schedule',
    'description': 'Update train schedule data from NTES website',
    'version': '1.0',
    'author': 'RouteMaster Agent',
    'inputs': {
        'train_number': {'type': 'string', 'required': True, 'description': 'Train number to update'},
        'date': {'type': 'string', 'default': 'today', 'description': 'Date for schedule (today/tomorrow/YYYY-MM-DD)'},
        'force_refresh': {'type': 'boolean', 'default': False, 'description': 'Force update even if recently updated'}
    },
    'outputs': {
        'schedule_data': {'type': 'dict', 'description': 'Extracted schedule information'},
        'confidence_score': {'type': 'float', 'description': 'Extraction confidence 0-1'},
        'updated_stations': {'type': 'int', 'description': 'Number of stations updated'},
        'status': {'type': 'string', 'description': 'success/failed/partial'}
    },
    'estimated_duration': 120,
    'priority': 'high',
    'retry_policy': {
        'max_attempts': 3,
        'backoff_strategy': 'exponential',
        'backoff_base': 2
    },
    'dependencies': ['browser', 'ntes_website', 'database'],
    'tags': ['schedule', 'train', 'ntes', 'monthly']
}

# Success criteria
SUCCESS_CRITERIA = [
    'train_number_found',
    'schedule_table_extracted',
    'at_least_2_stations_extracted',
    'data_validation_passed',
    'database_updated'
]

# Failure modes and recovery
FAILURE_MODES = {
    'website_unavailable': {'recovery': 'retry_with_backoff', 'fallback': 'use_cached_data'},
    'train_not_found': {'recovery': 'verify_train_number', 'fallback': 'mark_as_invalid'},
    'extraction_failed': {'recovery': 'try_alternate_selectors', 'fallback': 'manual_review'},
    'validation_failed': {'recovery': 'clean_and_retry', 'fallback': 'partial_update'}
}


def validate_inputs(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Validate task inputs."""
    errors = []

    if not parameters.get('train_number'):
        errors.append('train_number is required')

    if not isinstance(parameters.get('train_number'), str):
        errors.append('train_number must be string')

    date = parameters.get('date', 'today')
    if date not in ['today', 'tomorrow'] and not _is_valid_date(date):
        errors.append('date must be today/tomorrow or YYYY-MM-DD')

    return {'valid': len(errors) == 0, 'errors': errors}


def _is_valid_date(date_str: str) -> bool:
    """Check if date string is valid YYYY-MM-DD."""
    try:
        from datetime import datetime
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def get_execution_plan(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Generate detailed execution plan."""
    train_number = parameters['train_number']

    return {
        'task_id': f"schedule_update_{train_number}",
        'phases': [
            {
                'name': 'navigation',
                'description': 'Navigate to NTES train schedule page',
                'estimated_time': 30,
                'tools_needed': ['browser_navigator']
            },
            {
                'name': 'input',
                'description': f'Enter train number {train_number}',
                'estimated_time': 15,
                'tools_needed': ['input_handler']
            },
            {
                'name': 'extraction',
                'description': 'Extract schedule table data',
                'estimated_time': 45,
                'tools_needed': ['table_extractor']
            },
            {
                'name': 'validation',
                'description': 'Validate extracted data',
                'estimated_time': 15,
                'tools_needed': ['data_validator']
            },
            {
                'name': 'storage',
                'description': 'Store data in database',
                'estimated_time': 15,
                'tools_needed': ['database_writer']
            }
        ],
        'total_estimated_time': 120,
        'resource_requirements': {
            'browser_instances': 1,
            'network_bandwidth': 'medium',
            'database_connections': 1
        }
    }


def get_fallback_strategies() -> List[Dict[str, Any]]:
    """Get fallback strategies for this task."""
    return [
        {
            'name': 'use_irctc_fallback',
            'description': 'Try IRCTC website instead of NTES',
            'conditions': ['ntes_unavailable'],
            'estimated_time': 180
        },
        {
            'name': 'use_cached_data',
            'description': 'Use recently cached schedule data',
            'conditions': ['extraction_failed', 'recent_data_available'],
            'estimated_time': 30
        },
        {
            'name': 'partial_update',
            'description': 'Update only successfully extracted stations',
            'conditions': ['partial_extraction_success'],
            'estimated_time': 60
        }
    ]
