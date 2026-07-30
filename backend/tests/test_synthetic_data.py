"""
Tests for Synthetic Data Generation Framework.

Tests all components:
- Data generators
- Validation framework
- Storage layer
- API endpoints
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any

from backend.services.synthetic_data.generators import (
    TrainScheduleGenerator,
    FareGenerator,
    AvailabilityGenerator,
    UserBehaviorGenerator,
    generate_train_schedules,
    generate_fares,
    generate_availability,
    generate_user_behavior,
)

from backend.services.synthetic_data.validation import (
    DistributionValidator,
    StatisticalValidator,
    RealismScorer,
    validate_synthetic_data,
)

from backend.services.synthetic_data.storage import (
    FeatureStore,
    RouteGraph,
)


class TestTrainScheduleGenerator:
    """Tests for TrainScheduleGenerator."""
    
    def test_generate_single_schedule(self):
        """Test generating a single train schedule."""
        generator = TrainScheduleGenerator()
        schedule = generator._generate_single_schedule()
        
        assert schedule.train_number is not None
        assert schedule.from_station != schedule.to_station
        assert schedule.departure_time is not None
        assert schedule.arrival_time is not None
        assert schedule.duration is not None
        assert len(schedule.days_of_week) > 0
        assert schedule.train_type in ['Express', 'Superfast', 'Rajdhani', 'Shatabdi']
        assert len(schedule.classes) > 0
        assert schedule.base_fare > 0
        assert schedule.distance > 0
    
    def test_generate_multiple_schedules(self):
        """Test generating multiple train schedules."""
        generator = TrainScheduleGenerator()
        schedules = generator.generate(100)
        
        assert len(schedules) == 100
        
        # Check all schedules are valid
        for schedule in schedules:
            assert schedule.train_number is not None
            assert schedule.from_station != schedule.to_station
    
    def test_train_type_distribution(self):
        """Test train type distribution matches expected."""
        generator = TrainScheduleGenerator()
        schedules = generator.generate(1000)
        
        # Count train types
        train_type_counts = {}
        for schedule in schedules:
            tt = schedule.train_type
            train_type_counts[tt] = train_type_counts.get(tt, 0) + 1
        
        # Check distribution is reasonable
        total = sum(train_type_counts.values())
        for tt, count in train_type_counts.items():
            percentage = count / total
            # Express should be ~60%, others should be reasonable
            if tt == 'Express':
                assert 0.4 <= percentage <= 0.8
            elif tt in ['Superfast', 'Rajdhani', 'Shatabdi']:
                assert percentage >= 0.01


class TestFareGenerator:
    """Tests for FareGenerator."""
    
    def test_generate_single_fare(self):
        """Test generating a single fare record."""
        schedule_generator = TrainScheduleGenerator()
        generator = FareGenerator(schedule_generator)
        fare = generator._generate_single_fare()
        
        assert fare.train_number is not None
        assert fare.from_station != fare.to_station
        assert fare.travel_class in ['SL', '3A', '2A', '1A', 'CC', 'EC']
        assert fare.base_fare > 0
        assert 0.8 <= fare.dynamic_factor <= 2.5
        # Allow small floating point differences
        assert abs(fare.final_fare - (fare.base_fare * fare.dynamic_factor)) < 0.01
        assert fare.booking_class in ['GN', 'TQ', 'PQ', 'FQ']
        assert 0 <= fare.availability <= 100
        # days_before_travel can be negative (past bookings)
        assert fare.days_before_travel >= -30
    
    def test_generate_multiple_fares(self):
        """Test generating multiple fare records."""
        schedule_generator = TrainScheduleGenerator()
        generator = FareGenerator(schedule_generator)
        fares = generator.generate(100)
        
        assert len(fares) == 100
        
        # Check all fares are valid
        for fare in fares:
            # Allow small floating point differences
            assert abs(fare.final_fare - (fare.base_fare * fare.dynamic_factor)) < 0.01


class TestAvailabilityGenerator:
    """Tests for AvailabilityGenerator."""
    
    def test_generate_single_availability(self):
        """Test generating a single availability record."""
        schedule_generator = TrainScheduleGenerator()
        generator = AvailabilityGenerator(schedule_generator)
        availability = generator._generate_single_availability()
        
        assert availability.train_number is not None
        assert availability.from_station != availability.to_station
        assert availability.travel_class in ['SL', '3A', '2A', '1A']
        assert 0 <= availability.availability <= 100
        assert 0 <= availability.waiting_list <= 50
        assert 0 <= availability.confirmation_probability <= 1.0
        assert 0.5 <= availability.festival_factor <= 1.5
        assert 0.5 <= availability.weather_factor <= 1.5
        assert 0.5 <= availability.event_factor <= 1.5
        assert 0.5 <= availability.seasonal_factor <= 1.5
        assert 0.5 <= availability.demand_score <= 2.0
    
    def test_high_demand_low_availability(self):
        """Test that high demand results in low availability."""
        schedule_generator = TrainScheduleGenerator()
        generator = AvailabilityGenerator(schedule_generator)
        
        # Simulate high demand scenario
        availability = generator._generate_single_availability()
        
        # Higher demand score should result in lower availability
        if availability.demand_score > 1.5:
            assert availability.availability < 30


class TestUserBehaviorGenerator:
    """Tests for UserBehaviorGenerator."""
    
    def test_generate_single_behavior(self):
        """Test generating a single user behavior record."""
        generator = UserBehaviorGenerator()
        behavior = generator._generate_single_behavior()
        
        assert behavior.user_id is not None
        assert behavior.session_id is not None
        assert behavior.from_station != behavior.to_station
        assert behavior.travel_class_preference in ['SL', '3A', '2A', '1A']
        assert behavior.time_preference in ['Morning', 'Afternoon', 'Evening']
        assert behavior.train_type_preference in ['Express', 'Superfast', 'Rajdhani']
        assert 0.3 <= behavior.price_sensitivity <= 0.9
        assert 0 <= behavior.transfer_tolerance <= 3
        assert behavior.search_results_count >= 5
        assert behavior.device_type in ['Mobile', 'Desktop', 'Tablet']
        assert behavior.platform in ['Android', 'iOS', 'Web']
    
    def test_booking_probability(self):
        """Test booking probability is reasonable."""
        generator = UserBehaviorGenerator()
        behaviors = generator.generate(100)
        
        # Calculate booking completion rate
        completed = sum(1 for b in behaviors if b.booking_completed)
        completion_rate = completed / len(behaviors)
        
        # Completion rate should be between 5% and 25%
        assert 0.05 <= completion_rate <= 0.25


class TestDistributionValidator:
    """Tests for DistributionValidator."""
    
    def test_validate_numerical_distributions(self):
        """Test numerical distribution validation."""
        # Create sample data
        real_data = pd.DataFrame({
            'base_fare': np.random.normal(1000, 200, 1000),
            'distance': np.random.normal(500, 100, 1000),
        })
        
        synthetic_data = pd.DataFrame({
            'base_fare': np.random.normal(1000, 200, 1000),
            'distance': np.random.normal(500, 100, 1000),
        })
        
        validator = DistributionValidator(real_data, synthetic_data)
        results = validator._validate_numerical_distributions()
        
        # Check all features are validated
        assert 'base_fare' in results
        assert 'distance' in results
        
        # Check test results
        for feature, result in results.items():
            assert 'test' in result
            assert 'p_value' in result
            assert 'kl_divergence' in result
    
    def test_validate_categorical_distributions(self):
        """Test categorical distribution validation."""
        # Create sample data
        real_data = pd.DataFrame({
            'train_type': np.random.choice(['Express', 'Superfast', 'Rajdhani'], 1000),
            'travel_class': np.random.choice(['SL', '3A', '2A', '1A'], 1000),
        })
        
        synthetic_data = pd.DataFrame({
            'train_type': np.random.choice(['Express', 'Superfast', 'Rajdhani'], 1000),
            'travel_class': np.random.choice(['SL', '3A', '2A', '1A'], 1000),
        })
        
        validator = DistributionValidator(real_data, synthetic_data)
        results = validator._validate_categorical_distributions()
        
        # Check all features are validated
        assert 'train_type' in results
        assert 'travel_class' in results
        
        # Check test results
        for feature, result in results.items():
            assert 'test' in result
            assert 'p_value' in result


class TestStatisticalValidator:
    """Tests for StatisticalValidator."""
    
    def test_validate_means(self):
        """Test mean validation."""
        # Create sample data
        real_data = pd.DataFrame({
            'base_fare': np.random.normal(1000, 200, 1000),
            'distance': np.random.normal(500, 100, 1000),
        })
        
        synthetic_data = pd.DataFrame({
            'base_fare': np.random.normal(1000, 200, 1000),
            'distance': np.random.normal(500, 100, 1000),
        })
        
        validator = StatisticalValidator(real_data, synthetic_data)
        results = validator._validate_means()
        
        # Check all features are validated
        assert 'base_fare' in results
        assert 'distance' in results
        
        # Check test results
        for feature, result in results.items():
            assert 'test' in result
            assert 'p_value' in result
    
    def test_validate_variances(self):
        """Test variance validation."""
        # Create sample data
        real_data = pd.DataFrame({
            'base_fare': np.random.normal(1000, 200, 1000),
            'distance': np.random.normal(500, 100, 1000),
        })
        
        synthetic_data = pd.DataFrame({
            'base_fare': np.random.normal(1000, 200, 1000),
            'distance': np.random.normal(500, 100, 1000),
        })
        
        validator = StatisticalValidator(real_data, synthetic_data)
        results = validator._validate_variances()
        
        # Check all features are validated
        assert 'base_fare' in results
        assert 'distance' in results
        
        # Check test results
        for feature, result in results.items():
            assert 'test' in result
            assert 'p_value' in result


class TestRealismScorer:
    """Tests for RealismScorer."""
    
    def test_score(self):
        """Test realism scoring."""
        # Create sample data
        real_data = pd.DataFrame({
            'base_fare': np.random.normal(1000, 200, 1000),
            'dynamic_factor': np.random.normal(1.0, 0.3, 1000),
            'final_fare': np.random.normal(1000, 200, 1000),
            'train_type': np.random.choice(['Express', 'Superfast'], 1000),
            'from_station': np.random.choice(['NDLS', 'BCT'], 1000),
            'to_station': np.random.choice(['BCT', 'NDLS'], 1000),
        })
        
        synthetic_data = pd.DataFrame({
            'base_fare': np.random.normal(1000, 200, 1000),
            'dynamic_factor': np.random.normal(1.0, 0.3, 1000),
            'final_fare': np.random.normal(1000, 200, 1000),
            'train_type': np.random.choice(['Express', 'Superfast'], 1000),
            'from_station': np.random.choice(['NDLS', 'BCT'], 1000),
            'to_station': np.random.choice(['BCT', 'NDLS'], 1000),
        })
        
        scorer = RealismScorer(real_data, synthetic_data)
        results = scorer.score()
        
        # Check overall score
        assert 'overall_score' in results
        assert 'distribution_score' in results
        assert 'statistical_score' in results
        assert 'domain_score' in results
        assert 'passed' in results
        
        # Check scores are between 0 and 1
        assert 0 <= results['overall_score'] <= 1
        assert 0 <= results['distribution_score'] <= 1
        assert 0 <= results['statistical_score'] <= 1
        assert 0 <= results['domain_score'] <= 1


class TestValidationIntegration:
    """Integration tests for validation framework."""
    
    def test_validate_synthetic_data(self):
        """Test full validation pipeline."""
        # Create sample data
        real_data = pd.DataFrame({
            'base_fare': np.random.normal(1000, 200, 1000),
            'dynamic_factor': np.random.normal(1.0, 0.3, 1000),
            'final_fare': np.random.normal(1000, 200, 1000),
            'train_type': np.random.choice(['Express', 'Superfast'], 1000),
            'from_station': np.random.choice(['NDLS', 'BCT'], 1000),
            'to_station': np.random.choice(['BCT', 'NDLS'], 1000),
        })
        
        synthetic_data = pd.DataFrame({
            'base_fare': np.random.normal(1000, 200, 1000),
            'dynamic_factor': np.random.normal(1.0, 0.3, 1000),
            'final_fare': np.random.normal(1000, 200, 1000),
            'train_type': np.random.choice(['Express', 'Superfast'], 1000),
            'from_station': np.random.choice(['NDLS', 'BCT'], 1000),
            'to_station': np.random.choice(['BCT', 'NDLS'], 1000),
        })
        
        results = validate_synthetic_data(real_data, synthetic_data)
        
        # Check results structure
        assert 'overall_score' in results
        assert 'distribution_score' in results
        assert 'statistical_score' in results
        assert 'domain_score' in results
        assert 'passed' in results
        assert 'distribution_tests' in results
        assert 'statistical_tests' in results
        assert 'domain_checks' in results


class TestGeneratorsIntegration:
    """Integration tests for data generators."""
    
    def test_generate_all_data(self):
        """Test generating all types of synthetic data."""
        # Generate train schedules
        schedules = generate_train_schedules(100)
        assert len(schedules) == 100
        
        # Generate fares
        fares = generate_fares(100)
        assert len(fares) == 100
        
        # Generate availability
        availability = generate_availability(100)
        assert len(availability) == 100
        
        # Generate user behavior
        behavior = generate_user_behavior(100)
        assert len(behavior) == 100
    
    def test_data_consistency(self):
        """Test data consistency across generators."""
        # Generate data
        schedules = generate_train_schedules(100)
        fares = generate_fares(100)
        availability = generate_availability(100)
        
        # Check that all generators produce valid data
        assert len(schedules) == 100
        assert len(fares) == 100
        assert len(availability) == 100
        
        # Check that train numbers are valid format
        for schedule in schedules:
            assert len(schedule.train_number) == 5
            assert schedule.train_number.isdigit()
        
        for fare in fares:
            assert len(fare.train_number) == 5
            assert fare.train_number.isdigit()
        
        for avail in availability:
            assert len(avail.train_number) == 5
            assert avail.train_number.isdigit()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])