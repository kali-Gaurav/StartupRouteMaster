"""
Validation Framework Usage Examples
Complete guide for integrating validators into your routing application
"""

# ============================================================================
# EXAMPLE 1: Using ValidationManager (RECOMMENDED APPROACH)
# ============================================================================

from backend.core.validator.validation_manager import (
    create_validation_manager_with_defaults,
    ValidationProfile,
    ValidationCategory
)
from datetime import datetime

def example_validation_manager_basic():
    """Simple ValidationManager usage with default configuration"""
    
    # Initialize manager with all default validators
    manager = create_validation_manager_with_defaults()
    
    # Example route data
    route_data = {
        'route_id': 'R001',
        'stops': [
            {'stop_id': 'S1', 'lat': 51.5074, 'lon': -0.1278},
            {'stop_id': 'S2', 'lat': 51.5174, 'lon': -0.1378},
            {'stop_id': 'S3', 'lat': 51.5274, 'lon': -0.1478},
        ],
        'transfers': [
            {'from_stop': 'S1', 'to_stop': 'S2', 'duration': 120},
            {'from_stop': 'S2', 'to_stop': 'S3', 'duration': 150},
        ],
        'duration': 900  # seconds
    }
    
    # Validate with QUICK profile (5ms, critical checks only)
    result = manager.validate_route(route_data, validation_profile=ValidationProfile.QUICK)
    
    if result.passed:
        print(f"✓ Route {route_data['route_id']} validation passed")
    else:
        print(f"✗ Route validation failed: {result.errors}")


def example_validation_manager_standard():
    """ValidationManager with STANDARD profile for production use"""
    
    manager = create_validation_manager_with_defaults()
    
    # Complex multi-modal route data
    multimodal_route = {
        'route_id': 'MM001',
        'segments': [
            {
                'mode': 'train',
                'from_stop': 'VICTORIA_STN',
                'to_stop': 'LONDON_BRIDGE_STN',
                'duration': 420,
                'modal_constraints': {'accessibility': True, 'bicycle_allowed': False}
            },
            {
                'mode': 'bus',
                'from_stop': 'LONDON_BRIDGE_BUS',
                'to_stop': 'DESTINATION',
                'duration': 300,
                'modal_constraints': {'accessibility': True, 'bicycle_allowed': True}
            }
        ],
        'total_transfers': 1,
        'fare': {
            'base': 8.50,
            'discount': 0.0,
            'discount_type': 'none'
        }
    }
    
    # Validate with STANDARD profile (20ms, recommended for production)
    result = manager.validate_route(
        multimodal_route, 
        validation_profile=ValidationProfile.STANDARD
    )
    
    print(f"Validation Result: {result.passed}")
    print(f"Checks Passed: {result.passed_count}/{result.total_checks}")


def example_validation_manager_full():
    """ValidationManager with FULL profile for comprehensive validation"""
    
    manager = create_validation_manager_with_defaults()
    
    comprehensive_data = {
        'routes': [
            {'route_id': 'R001', 'stops': [...]},
            {'route_id': 'R002', 'stops': [...]},
        ],
        'api_requests': [
            {
                'method': 'GET',
                'path': '/api/routes',
                'query_params': {'from': 'Victoria', 'to': 'Paddington'},
                'headers': {'Authorization': 'Bearer token123'}
            },
            {
                'method': 'POST',
                'path': '/api/booking',
                'body': {'route_id': 'R001', 'seats': 2}
            }
        ],
        'ai_ranking': {
            'user_profile': {
                'user_id': 'U123',
                'preferences': {'minimize_transfers': True, 'eco_friendly': True}
            },
            'model_metadata': {'version': '2.1', 'trained_date': '2024-01-15'},
            'rankings': [
                {'route_id': 'R001', 'score': 0.95},
                {'route_id': 'R002', 'score': 0.87}
            ]
        }
    }
    
    # Validate comprehensive data (100ms, all 170+ checks)
    report = manager.validate_complete(
        routes=comprehensive_data['routes'],
        api_requests=comprehensive_data['api_requests'],
        ranking_data=comprehensive_data['ai_ranking']
    )
    
    print(f"Total Checks: {report.total_checks}")
    print(f"Passed: {report.passed_count}")
    print(f"Failed: {report.failed_count}")
    print(f"Overall Status: {'✓ PASS' if report.all_passed else '✗ FAIL'}")
    
    # Print breakdown by category
    for category, result in report.category_results.items():
        status = '✓' if result.passed else '✗'
        print(f"  {status} {category}: {result.passed_count}/{result.total_checks}")


def example_custom_validation_profile():
    """Create custom validation profile with specific categories"""
    
    manager = create_validation_manager_with_defaults()
    
    route_data = {...}
    
    # Validate only specific categories
    from backend.core.validator.validation_manager import ValidationCategory
    
    result = manager.validate_route(
        route_data,
        validation_profile=ValidationProfile.CUSTOM,
        custom_categories={
            ValidationCategory.REAL_TIME_UPDATES,
            ValidationCategory.FARE_AVAILABILITY,
            ValidationCategory.API_SECURITY
        }
    )
    
    print(f"Custom Profile Results: {result.passed}")


def example_register_custom_validator():
    """Register additional custom validators with manager"""
    
    from backend.core.validator.validation_manager import BaseValidator, ValidationResult
    
    class CustomBusinessRuleValidator(BaseValidator):
        """Example custom validator for business rules"""
        
        def validate(self, data: dict) -> ValidationResult:
            checks_passed = 0
            total_checks = 3
            
            # Business rule 1: Maximum 5 transfers
            if len(data.get('transfers', [])) <= 5:
                checks_passed += 1
            
            # Business rule 2: Minimum route duration 15 minutes
            if data.get('duration', 0) >= 900:
                checks_passed += 1
            
            # Business rule 3: Fare must be between £1 and £20
            fare = data.get('fare', {}).get('base', 0)
            if 1 <= fare <= 20:
                checks_passed += 1
            
            return ValidationResult(
                passed=checks_passed == total_checks,
                passed_count=checks_passed,
                total_checks=total_checks
            )
    
    # Register custom validator
    manager = create_validation_manager_with_defaults()
    custom_validator = CustomBusinessRuleValidator()
    manager.validator_registry.register('business_rules', custom_validator)
    
    # Example route data for the custom validator
    route_data = {
        'route_id': 'CUSTOM_001',
        'stops': [
            {'stop_id': 'S1', 'lat': 51.5, 'lon': -0.1},
            {'stop_id': 'S2', 'lat': 51.51, 'lon': -0.11}
        ],
        'transfers': [],
        'duration': 900,
        'fare': {'base': 10.0}
    }

    # Use it in validation
    result = manager.validate_route(route_data)
    print(f"Validation passed: {result.passed}")


# ============================================================================
# EXAMPLE 2: Direct Integration with route_engine (ALTERNATIVE APPROACH)
# ============================================================================

from backend.core.route_engine import OptimizedRAPTOR
from sqlalchemy.orm import Session

def example_direct_integration_basic(db_session: Session):
    """Simple direct integration via route_engine"""
    
    raptor = OptimizedRAPTOR(db_session)
    
    # Setup validation config
    validation_config = {
        'from_stop': 'VICTORIA',
        'to_stop': 'PADDINGTON',
        'departure_time': datetime(2024, 1, 15, 9, 0),
        'max_transfers': 3
    }
    
    # Find routes
    routes = raptor.find_routes(
        from_stop='VICTORIA',
        to_stop='PADDINGTON',
        departure_time=datetime(2024, 1, 15, 9, 0)
    )
    
    # Validate routes using direct validators
    for route in routes:
        route_validation_config = {
            'route': route,
            'stops': route.get('stops', []),
            'transfers': route.get('transfers', [])
        }
        
        # Call validate_multimodal_route directly
        if raptor.validate_multimodal_route(route_validation_config):
            print(f"✓ Route {route['route_id']} passed multimodal validation")
        else:
            print(f"✗ Route {route['route_id']} failed multimodal validation")


def example_direct_integration_comprehensive(db_session: Session):
    """Comprehensive direct integration with multiple validators"""
    
    raptor = OptimizedRAPTOR(db_session)
    
    # Find initial routes
    routes = raptor.find_routes(
        from_stop='VICTORIA',
        to_stop='PADDINGTON',
        departure_time=datetime(2024, 1, 15, 9, 0),
        max_transfers=3
    )
    
    # Step 1: Validate Multimodal Routing
    multimodal_config = {
        'route': routes[0],
        'segments': routes[0].get('segments', []),
        'total_transfers': routes[0].get('total_transfers', 0)
    }
    
    if not raptor.validate_multimodal_route(multimodal_config):
        print("Failed multimodal validation")
        return
    
    print("✓ Passed multimodal validation")
    
    # Step 2: Validate Fare & Availability
    fare_config = {
        'fare': routes[0].get('fare', {}),
        'available_seats': routes[0].get('available_seats', 0),
        'vehicle_capacity': routes[0].get('capacity', 100)
    }
    
    if not raptor.validate_fare_and_availability(fare_config):
        print("Failed fare/availability validation")
        return
    
    print("✓ Passed fare/availability validation")
    
    # Step 3: Validate Data Integrity
    integrity_config = {
        'stops': routes[0].get('stops', []),
        'connections': routes[0].get('connections', [])
    }
    
    if not raptor.validate_data_integrity(integrity_config):
        print("Failed data integrity validation")
        return
    
    print("✓ Passed data integrity validation")
    
    # Step 4: Validate API & Security
    api_config = {
        'request_data': {
            'from': 'VICTORIA',
            'to': 'PADDINGTON',
            'departure': '2024-01-15T09:00:00Z'
        },
        'auth_token': 'valid_token_123'
    }
    
    if not raptor.validate_api_and_security(api_config):
        print("Failed API/security validation")
        return
    
    print("✓ Passed API/security validation")
    
    # Step 5: Validate AI Ranking (if ranking applied)
    ranking_config = {
        'ranking_result': routes[0],
        'user_profile': {
            'user_id': 'U123',
            'preferences': {'minimize_transfers': True}
        },
        'model_metadata': {'version': '2.1'}
    }
    
    if not raptor.validate_ai_ranking(ranking_config):
        print("Failed AI ranking validation")
        return
    
    print("✓ Passed AI ranking validation")
    
    print("\n✓✓✓ All validation stages passed ✓✓✓")


# ============================================================================
# EXAMPLE 3: Performance Comparison
# ============================================================================

import time

def performance_comparison():
    """Compare performance of different validation approaches"""
    
    manager = create_validation_manager_with_defaults()
    
    route_data = {
        'route_id': 'PERF_TEST',
        'stops': [{'stop_id': f'S{i}', 'lat': 51.5 + i*0.01, 'lon': -0.1 - i*0.01} 
                  for i in range(10)],
        'transfers': [{'from_stop': f'S{i}', 'to_stop': f'S{i+1}', 'duration': 120} 
                      for i in range(9)]
    }
    
    # QUICK Profile (critical checks only)
    start = time.time()
    result = manager.validate_route(route_data, ValidationProfile.QUICK)
    quick_time = (time.time() - start) * 1000
    print(f"QUICK Profile:    {quick_time:.2f}ms")
    
    # STANDARD Profile (recommended)
    start = time.time()
    result = manager.validate_route(route_data, ValidationProfile.STANDARD)
    standard_time = (time.time() - start) * 1000
    print(f"STANDARD Profile: {standard_time:.2f}ms")
    
    # FULL Profile (comprehensive)
    start = time.time()
    result = manager.validate_route(route_data, ValidationProfile.FULL)
    full_time = (time.time() - start) * 1000
    print(f"FULL Profile:     {full_time:.2f}ms")


# ============================================================================
# EXAMPLE 4: Error Handling & Reporting
# ============================================================================

def example_error_handling_and_reporting():
    """Proper error handling and detailed reporting"""
    
    manager = create_validation_manager_with_defaults()
    
    # Sample route data used for error-handling example
    route_data = {
        'route_id': 'ERR_HANDLING_001',
        'stops': [
            {'stop_id': 'S1', 'lat': 51.5, 'lon': -0.1},
            {'stop_id': 'S2', 'lat': 51.51, 'lon': -0.11}
        ],
        'transfers': [],
        'duration': 1200,
        'fare': {'base': 5.0}
    }

    try:
        # Validate with detailed error reporting
        result = manager.validate_route(route_data, ValidationProfile.STANDARD)
        
        if not result.passed:
            print("Validation Failed:")
            print(f"  Total Checks: {result.total_checks}")
            print(f"  Passed: {result.passed_count}")
            print(f"  Failed: {result.failed_count}")
            print("\nErrors:")
            for error in result.errors:
                print(f"  - {error}")
            
            # Failed validation - handle appropriately
            return False
        else:
            print("✓ All validations passed")
            return True
            
    except Exception as e:
        print(f"Validation error: {e}")
        # Log error and handle gracefully
        return False


# ============================================================================
# EXAMPLE 5: Real-World API Endpoint Usage
# ============================================================================

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class RouteRequest(BaseModel):
    from_stop: str
    to_stop: str
    departure_time: datetime
    max_transfers: int = 3

class RouteResponse(BaseModel):
    route_id: str
    duration: int
    fare: float
    transfers: int

@app.post("/api/routes/search", response_model=list[RouteResponse])
async def search_routes(request: RouteRequest, db_session: Session):
    """Search routes with integrated validation"""
    
    manager = create_validation_manager_with_defaults()
    
    # 1. Validate API Request (RT-111-130: API Security)
    api_config = {
        'method': 'POST',
        'path': '/api/routes/search',
        'query_params': request.dict(),
        'headers': {'Content-Type': 'application/json'}
    }
    
    api_result = manager.validate_api_request(api_config)
    if not api_result.passed:
        raise HTTPException(status_code=400, detail="Invalid request parameters")
    
    # 2. Find routes using RAPTOR
    raptor = OptimizedRAPTOR(db_session)
    routes = raptor.find_routes(
        from_stop=request.from_stop,
        to_stop=request.to_stop,
        departure_time=request.departure_time
    )
    
    # 3. Validate each route (RT-001-050: Multi-modal, Fare, Data Integrity)
    validated_routes = []
    
    for route in routes:
        route_validation_config = {
            'route': route,
            'segments': route.get('segments', []),
            'fare': route.get('fare', {}),
            'stops': route.get('stops', [])
        }
        
        # Use STANDARD profile for API responses
        result = manager.validate_route(
            route_validation_config,
            ValidationProfile.STANDARD
        )
        
        if result.passed:
            validated_routes.append(RouteResponse(
                route_id=route['route_id'],
                duration=route['duration'],
                fare=route['fare']['base'],
                transfers=route.get('total_transfers', 0)
            ))
    
    if not validated_routes:
        raise HTTPException(status_code=404, detail="No valid routes found")
    
    return validated_routes


# ============================================================================
# EXAMPLE 6: Batch Validation for Data Import/Export
# ============================================================================

def batch_validation_for_data_import(routes_list: list):
    """Validate multiple routes efficiently for data import"""
    
    manager = create_validation_manager_with_defaults()
    
    validation_report = {
        'total_routes': len(routes_list),
        'valid_routes': 0,
        'invalid_routes': [],
        'errors_by_type': {}
    }
    
    # Use FULL profile for data import to catch all issues
    for i, route in enumerate(routes_list):
        result = manager.validate_route(route, ValidationProfile.FULL)
        
        if result.passed:
            validation_report['valid_routes'] += 1
        else:
            validation_report['invalid_routes'].append({
                'index': i,
                'route_id': route.get('route_id'),
                'errors': result.errors
            })
            
            # Track error types
            for error in result.errors:
                error_type = error.split(':')[0]
                validation_report['errors_by_type'][error_type] = \
                    validation_report['errors_by_type'].get(error_type, 0) + 1
    
    # Print summary
    print(f"Batch Validation Report:")
    print(f"  Total Routes: {validation_report['total_routes']}")
    print(f"  Valid: {validation_report['valid_routes']}")
    print(f"  Invalid: {len(validation_report['invalid_routes'])}")
    print(f"  Success Rate: {validation_report['valid_routes']/len(routes_list)*100:.1f}%")
    
    if validation_report['errors_by_type']:
        print(f"\nError Breakdown:")
        for error_type, count in validation_report['errors_by_type'].items():
            print(f"  {error_type}: {count}")
    
    return validation_report


# ============================================================================
# MAIN: Run Examples
# ============================================================================

if __name__ == '__main__':
    print("=" * 70)
    print("VALIDATION FRAMEWORK USAGE EXAMPLES")
    print("=" * 70)
    
    # Run examples
    print("\n1. ValidationManager - Basic Usage")
    print("-" * 70)
    example_validation_manager_basic()
    
    print("\n2. ValidationManager - Performance Comparison")
    print("-" * 70)
    performance_comparison()
    
    print("\n✓ All examples completed successfully!")
