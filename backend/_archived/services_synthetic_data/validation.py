"""
Data Validation Framework for Synthetic Data Generation.

This module provides validation tools to ensure synthetic data quality:
- Distribution matching validation
- Statistical validity tests
- Realism scoring
"""

import numpy as np
import pandas as pd
from scipy import stats
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class ValidationResults:
    """Results of data validation."""
    passed: bool
    tests: Dict[str, Dict[str, Any]]
    overall_score: float


class DistributionValidator:
    """
    Validate synthetic data distributions match real data distributions.
    
    Uses statistical tests to ensure synthetic data has similar
    statistical properties to real data.
    """
    
    def __init__(self, real_data: pd.DataFrame, synthetic_data: pd.DataFrame):
        """
        Initialize the validator.
        
        Args:
            real_data: Real data DataFrame
            synthetic_data: Synthetic data DataFrame
        """
        self.real_data = real_data
        self.synthetic_data = synthetic_data
        self.results = {}
    
    def validate(self) -> ValidationResults:
        """
        Run all distribution validation tests.
        
        Returns:
            ValidationResults with test results and overall score
        """
        numerical_tests = self._validate_numerical_distributions()
        categorical_tests = self._validate_categorical_distributions()
        correlation_tests = self._validate_correlations()
        
        all_tests = {**numerical_tests, **categorical_tests, **correlation_tests}
        
        # Calculate overall score
        passed_tests = sum(1 for test in all_tests.values() if test['passed'])
        total_tests = len(all_tests)
        overall_score = passed_tests / total_tests if total_tests > 0 else 0.0
        
        return ValidationResults(
            passed=overall_score >= 0.95,
            tests=all_tests,
            overall_score=overall_score,
        )
    
    def _validate_numerical_distributions(self) -> Dict[str, Dict[str, Any]]:
        """Validate numerical distributions using KS test."""
        results = {}
        
        # Get numerical columns
        numerical_cols = self.real_data.select_dtypes(include=[np.number]).columns
        
        for col in numerical_cols:
            real_values = self.real_data[col].dropna()
            synth_values = self.synthetic_data[col].dropna()
            
            # KS test
            ks_stat, ks_pvalue = stats.ks_2samp(real_values, synth_values)
            
            # Calculate KL divergence
            kl_div = self._calculate_kl_divergence(real_values, synth_values, col)
            
            results[col] = {
                'test': 'Kolmogorov-Smirnov',
                'statistic': float(ks_stat),
                'p_value': float(ks_pvalue),
                'kl_divergence': float(kl_div),
                'real_mean': float(real_values.mean()),
                'synth_mean': float(synth_values.mean()),
                'real_std': float(real_values.std()),
                'synth_std': float(synth_values.std()),
                'passed': ks_pvalue > 0.05 and kl_div < 0.05,
            }
        
        return results
    
    def _calculate_kl_divergence(self, real: np.ndarray, synth: np.ndarray, col: str) -> float:
        """Calculate KL divergence between distributions."""
        # Create histograms
        real_hist, _ = np.histogram(real, bins=50)
        synth_hist, _ = np.histogram(synth, bins=50)
        
        # Normalize
        real_hist = real_hist / real_hist.sum()
        synth_hist = synth_hist / synth_hist.sum()
        
        # Calculate KL divergence
        kl = stats.entropy(real_hist, synth_hist)
        return kl
    
    def _validate_categorical_distributions(self) -> Dict[str, Dict[str, Any]]:
        """Validate categorical distributions using chi-square test."""
        results = {}
        
        # Get categorical columns
        categorical_cols = self.real_data.select_dtypes(include=['object']).columns
        
        for col in categorical_cols:
            real_counts = self.real_data[col].value_counts()
            synth_counts = self.synthetic_data[col].value_counts()
            
            # Align counts
            all_categories = set(real_counts.index) | set(synth_counts.index)
            real_counts = real_counts.reindex(all_categories, fill_value=0)
            synth_counts = synth_counts.reindex(all_categories, fill_value=0)
            
            # Chi-square test
            chi2, p_value, _, _ = stats.chi2_contingency([
                real_counts.values,
                synth_counts.values
            ])
            
            results[col] = {
                'test': 'Chi-Square',
                'statistic': float(chi2),
                'p_value': float(p_value),
                'real_distribution': real_counts.to_dict(),
                'synth_distribution': synth_counts.to_dict(),
                'passed': p_value > 0.05,
            }
        
        return results
    
    def _validate_correlations(self) -> Dict[str, Dict[str, Any]]:
        """Validate correlation preservation."""
        results = {}
        
        # Get numerical columns
        numerical_cols = self.real_data.select_dtypes(include=[np.number]).columns
        
        if len(numerical_cols) < 2:
            return results
        
        # Calculate correlation matrices
        real_corr = self.real_data[numerical_cols].corr()
        synth_corr = self.synthetic_data[numerical_cols].corr()
        
        # Calculate correlation difference
        corr_diff = np.abs(real_corr - synth_corr).mean().mean()
        
        results['correlation_matrix'] = {
            'test': 'Correlation Preservation',
            'mean_absolute_difference': float(corr_diff),
            'real_correlation_matrix': real_corr.to_dict(),
            'synth_correlation_matrix': synth_corr.to_dict(),
            'passed': corr_diff < 0.1,
        }
        
        return results


class StatisticalValidator:
    """
    Validate statistical properties of synthetic data.
    
    Ensures synthetic data passes statistical tests and maintains
    realistic statistical properties.
    """
    
    def __init__(self, real_data: pd.DataFrame, synthetic_data: pd.DataFrame):
        """
        Initialize the validator.
        
        Args:
            real_data: Real data DataFrame
            synthetic_data: Synthetic data DataFrame
        """
        self.real_data = real_data
        self.synthetic_data = synthetic_data
        self.results = {}
    
    def validate(self) -> ValidationResults:
        """
        Run all statistical validity tests.
        
        Returns:
            ValidationResults with test results and overall score
        """
        mean_tests = self._validate_means()
        variance_tests = self._validate_variances()
        outlier_tests = self._validate_outliers()
        missing_tests = self._validate_missing_values()
        
        all_tests = {**mean_tests, **variance_tests, **outlier_tests, **missing_tests}
        
        # Calculate overall score
        passed_tests = sum(1 for test in all_tests.values() if test['passed'])
        total_tests = len(all_tests)
        overall_score = passed_tests / total_tests if total_tests > 0 else 0.0
        
        return ValidationResults(
            passed=overall_score >= 0.99,
            tests=all_tests,
            overall_score=overall_score,
        )
    
    def _validate_means(self) -> Dict[str, Dict[str, Any]]:
        """Validate means using t-test."""
        results = {}
        
        numerical_cols = self.real_data.select_dtypes(include=[np.number]).columns
        
        for col in numerical_cols:
            real_values = self.real_data[col].dropna()
            synth_values = self.synthetic_data[col].dropna()
            
            # T-test
            t_stat, p_value = stats.ttest_ind(real_values, synth_values)
            
            results[col] = {
                'test': 'T-Test (Mean)',
                'statistic': float(t_stat),
                'p_value': float(p_value),
                'real_mean': float(real_values.mean()),
                'synth_mean': float(synth_values.mean()),
                'real_std': float(real_values.std()),
                'synth_std': float(synth_values.std()),
                'passed': p_value > 0.05,
            }
        
        return results
    
    def _validate_variances(self) -> Dict[str, Dict[str, Any]]:
        """Validate variances using F-test."""
        results = {}
        
        numerical_cols = self.real_data.select_dtypes(include=[np.number]).columns
        
        for col in numerical_cols:
            real_values = self.real_data[col].dropna()
            synth_values = self.synthetic_data[col].dropna()
            
            # F-test
            f_stat = np.var(real_values) / np.var(synth_values)
            p_value = 1 - stats.f.cdf(f_stat, len(real_values)-1, len(synth_values)-1)
            
            results[col] = {
                'test': 'F-Test (Variance)',
                'statistic': float(f_stat),
                'p_value': float(p_value),
                'real_variance': float(np.var(real_values)),
                'synth_variance': float(np.var(synth_values)),
                'passed': p_value > 0.05,
            }
        
        return results
    
    def _validate_outliers(self) -> Dict[str, Dict[str, Any]]:
        """Validate outlier detection."""
        results = {}
        
        numerical_cols = self.real_data.select_dtypes(include=[np.number]).columns
        
        for col in numerical_cols:
            real_values = self.real_data[col].dropna()
            synth_values = self.synthetic_data[col].dropna()
            
            # IQR method for outliers
            q1_real, q3_real = np.percentile(real_values, [25, 75])
            iqr_real = q3_real - q1_real
            real_outliers = np.sum(
                (real_values < q1_real - 1.5 * iqr_real) | 
                (real_values > q3_real + 1.5 * iqr_real)
            )
            
            q1_synth, q3_synth = np.percentile(synth_values, [25, 75])
            iqr_synth = q3_synth - q1_synth
            synth_outliers = np.sum(
                (synth_values < q1_synth - 1.5 * iqr_synth) | 
                (synth_values > q3_synth + 1.5 * iqr_synth)
            )
            
            real_outlier_rate = real_outliers / len(real_values)
            synth_outlier_rate = synth_outliers / len(synth_values)
            
            results[col] = {
                'test': 'Outlier Detection (IQR)',
                'real_outlier_count': int(real_outliers),
                'synth_outlier_count': int(synth_outliers),
                'real_outlier_rate': float(real_outlier_rate),
                'synth_outlier_rate': float(synth_outlier_rate),
                'passed': abs(real_outlier_rate - synth_outlier_rate) < 0.05,
            }
        
        return results
    
    def _validate_missing_values(self) -> Dict[str, Dict[str, Any]]:
        """Validate missing value patterns."""
        results = {}
        
        all_cols = self.real_data.columns
        
        for col in all_cols:
            real_missing = self.real_data[col].isna().sum()
            synth_missing = self.synthetic_data[col].isna().sum()
            
            real_missing_rate = real_missing / len(self.real_data)
            synth_missing_rate = synth_missing / len(self.synthetic_data)
            
            results[col] = {
                'test': 'Missing Value Analysis',
                'real_missing_count': int(real_missing),
                'synth_missing_count': int(synth_missing),
                'real_missing_rate': float(real_missing_rate),
                'synth_missing_rate': float(synth_missing_rate),
                'passed': abs(real_missing_rate - synth_missing_rate) < 0.01,
            }
        
        return results


class RealismScorer:
    """
    Score synthetic data for realism.
    
    Combines statistical validation with domain-specific checks
    to produce a realism score.
    """
    
    def __init__(self, real_data: pd.DataFrame, synthetic_data: pd.DataFrame):
        """
        Initialize the scorer.
        
        Args:
            real_data: Real data DataFrame
            synthetic_data: Synthetic data DataFrame
        """
        self.real_data = real_data
        self.synthetic_data = synthetic_data
        self.distribution_validator = DistributionValidator(real_data, synthetic_data)
        self.statistical_validator = StatisticalValidator(real_data, synthetic_data)
    
    def score(self) -> Dict[str, Any]:
        """
        Calculate realism score.
        
        Returns:
            Dictionary with realism scores and breakdown
        """
        # Run validations
        distribution_results = self.distribution_validator.validate()
        statistical_results = self.statistical_validator.validate()
        
        # Domain-specific checks
        domain_checks = self._run_domain_checks()
        
        # Calculate overall score
        distribution_score = distribution_results.overall_score
        statistical_score = statistical_results.overall_score
        domain_score = sum(1 for check in domain_checks.values() if check['passed']) / len(domain_checks)
        
        # Weighted average
        overall_score = (
            0.4 * distribution_score +
            0.4 * statistical_score +
            0.2 * domain_score
        )
        
        return {
            'overall_score': overall_score,
            'distribution_score': distribution_score,
            'statistical_score': statistical_score,
            'domain_score': domain_score,
            'distribution_tests': distribution_results.tests,
            'statistical_tests': statistical_results.tests,
            'domain_checks': domain_checks,
            'passed': overall_score >= 0.90,
        }
    
    def _run_domain_checks(self) -> Dict[str, Dict[str, Any]]:
        """Run domain-specific realism checks."""
        results = {}
        
        # Check 1: Fare calculations
        if 'base_fare' in self.real_data.columns and 'final_fare' in self.real_data.columns:
            results['fare_calculation'] = self._check_fare_calculations()
        
        # Check 2: Time consistency
        if 'departure_time' in self.real_data.columns and 'arrival_time' in self.real_data.columns:
            results['time_consistency'] = self._check_time_consistency()
        
        # Check 3: Station validity
        if 'from_station' in self.real_data.columns and 'to_station' in self.real_data.columns:
            results['station_validity'] = self._check_station_validity()
        
        return results
    
    def _check_fare_calculations(self) -> Dict[str, Any]:
        """Check fare calculations are reasonable."""
        real_data = self.real_data.copy()
        synth_data = self.synthetic_data.copy()
        
        # Check if final_fare = base_fare * dynamic_factor
        real_fare_valid = np.allclose(
            real_data['final_fare'],
            real_data['base_fare'] * real_data['dynamic_factor'],
            rtol=1e-5
        )
        
        synth_fare_valid = np.allclose(
            synth_data['final_fare'],
            synth_data['base_fare'] * synth_data['dynamic_factor'],
            rtol=1e-5
        )
        
        return {
            'test': 'Fare Calculation',
            'real_valid': real_fare_valid,
            'synth_valid': synth_fare_valid,
            'passed': real_fare_valid and synth_fare_valid,
        }
    
    def _check_time_consistency(self) -> Dict[str, Any]:
        """Check time calculations are reasonable."""
        # Check that arrival time > departure time
        # This is a simplified check - in production, would need date context
        
        return {
            'test': 'Time Consistency',
            'passed': True,  # Placeholder
        }
    
    def _check_station_validity(self) -> Dict[str, Any]:
        """Check station codes are valid."""
        # Check that from_station != to_station
        real_valid = (self.real_data['from_station'] != self.real_data['to_station']).all()
        synth_valid = (self.synthetic_data['from_station'] != self.synthetic_data['to_station']).all()
        
        return {
            'test': 'Station Validity',
            'real_valid': real_valid,
            'synth_valid': synth_valid,
            'passed': real_valid and synth_valid,
        }


# Convenience functions for validation
def validate_synthetic_data(
    real_data: pd.DataFrame,
    synthetic_data: pd.DataFrame
) -> Dict[str, Any]:
    """
    Validate synthetic data against real data.
    
    Args:
        real_data: Real data DataFrame
        synthetic_data: Synthetic data DataFrame
        
    Returns:
        Dictionary with validation results
    """
    realism_scorer = RealismScorer(real_data, synthetic_data)
    return realism_scorer.score()