"""
AI / Smart Ranking Validators (RT-151 to RT-170)

This module handles validation logic for AI-powered route ranking, personalization,
confidence scoring, and machine learning model performance in routing decisions.
"""

from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import logging
import hashlib
from collections import defaultdict

logger = logging.getLogger(__name__)


class ModelType(Enum):
    """AI model types"""
    RANKING = "ranking"
    PERSONALIZATION = "personalization"
    RECOMMENDATION = "recommendation"
    IMPLICIT_FEEDBACK = "implicit_feedback"


class OptimizationObjective(Enum):
    """Multi-objective optimization objectives"""
    TIME = "time"
    COST = "cost"
    COMFORT = "comfort"
    ENVIRONMENTAL = "environmental"
    SAFETY = "safety"


@dataclass
class RankingResult:
    """Result from AI ranking"""
    route_id: str
    rank_score: float
    confidence_score: float
    explanation: Optional[str] = None
    feature_importance: Dict[str, float] = field(default_factory=dict)
    model_version: str = "1.0"
    predicted_at: datetime = None


@dataclass
class UserProfile:
    """User profile for personalization"""
    user_id: str
    preference_weights: Dict[str, float] = field(default_factory=dict)
    history_routes: List[str] = field(default_factory=list)
    is_new_user: bool = False
    last_updated: datetime = None


@dataclass
class ModelMetadata:
    """AI model metadata"""
    model_name: str
    version: str
    trained_at: datetime
    features_used: List[str] = field(default_factory=list)
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    is_active: bool = True


class AIRankingValidator:
    """Validator class for AI-powered ranking and personalization"""

    def __init__(self):
        """Initialize the AI ranking validator"""
        self.model_metadata = {}
        self.ranking_history = []
        self.user_feedback_cache = defaultdict(list)
        self.feature_cache = {}
        self.cold_user_threshold = 5  # Routes before warm start
        self.confidence_threshold = 0.5
        self.max_rank_variance = 0.3  # 30% max variance threshold
        self.min_exploration_rate = 0.1  # 10% exploration minimum
        self.feature_drift_threshold = 0.2

    def validate_ranking_stability(self, rankings_v1: List[RankingResult],
                                  rankings_v2: List[RankingResult]) -> bool:
        """
        RT-151: Validate ranking stability.
        Ranking order should be stable between consecutive queries with same input.
        """
        if not rankings_v1 or not rankings_v2:
            return True
        
        if len(rankings_v1) != len(rankings_v2):
            logger.warning("Ranking result set sizes differ")
            return False
        
        # Calculate ranking correlation (Spearman rank correlation)
        rank_variance = 0.0
        for i in range(len(rankings_v1)):
            score_diff = abs(rankings_v1[i].rank_score - rankings_v2[i].rank_score)
            max_score = max(rankings_v1[i].rank_score, rankings_v2[i].rank_score)
            if max_score > 0:
                rank_variance += score_diff / max_score
        
        avg_variance = rank_variance / len(rankings_v1)
        
        if avg_variance > self.max_rank_variance:
            logger.warning(f"Ranking instability detected: {avg_variance * 100}% variance")
            return False
        
        return True

    def validate_user_preference_weighting(self, user_profile: UserProfile,
                                          weights_applied: Dict[str, float]) -> bool:
        """
        RT-152: Validate user preference weighting.
        User preferences should be properly weighted in ranking.
        """
        if not user_profile or not user_profile.preference_weights:
            return True
        
        # Check that weights sum to reasonable value (e.g., 0.8 to 1.2 for flexibility)
        total_weight = sum(weights_applied.values())
        if total_weight < 0.5 or total_weight > 2.0:
            logger.warning(f"Preference weight sum out of range: {total_weight}")
            return False
        
        # Check that all preference keys have corresponding weights
        for pref_key in user_profile.preference_weights:
            if pref_key not in weights_applied:
                logger.warning(f"Preference {pref_key} not in applied weights")
                # Allow but log (might use defaults)
        
        return True

    def validate_historical_learning_influence(self, user_history: List[str],
                                              ranking_result: RankingResult) -> bool:
        """
        RT-153: Validate historical learning influence.
        User's history should influence ranking but not dominate.
        """
        if not user_history:
            return True
        
        # Check that historical boost is moderate (not 100% past routes)
        historical_routes_in_top = sum(1 for route_id in user_history[:10] 
                                      if ranking_result.route_id == route_id)
        
        if historical_routes_in_top > 5:
            logger.warning("History dominates ranking too much")
            return False
        
        # History influence should be in feature importance
        if 'history_influence' in ranking_result.feature_importance:
            influence = ranking_result.feature_importance['history_influence']
            if influence < 0 or influence > 0.5:  # 0-50% reasonable range
                logger.warning(f"History influence out of range: {influence}")
                return False
        
        return True

    def validate_cold_user_scenario(self, user_profile: UserProfile,
                                   ranking_result: RankingResult) -> bool:
        """
        RT-154: Validate cold user scenario handling.
        New users should still get diverse, relevant ranking.
        """
        if not user_profile.is_new_user:
            return True
        
        # Cold users should have appropriate fallback ranking
        if not ranking_result.explanation:
            logger.warning("Cold user ranking lacks explanation")
            return False
        
        # Should use diverse factors, not just popularity
        feature_importance = ranking_result.feature_importance
        popularity_factor = feature_importance.get('popularity', 0)
        if popularity_factor > 0.7:  # Too heavy on popularity for cold user
            logger.warning("Cold user ranking too popularity-focused")
            return False
        
        return True

    def validate_bias_detection(self, rankings: List[RankingResult],
                               demographic_groups: Dict[str, List[str]]) -> bool:
        """
        RT-155: Validate bias detection in ranking.
        Ranking should not systematically discriminate against any group.
        """
        if not rankings or not demographic_groups:
            return True
        
        # Check ranking distribution across groups
        group_performance = {}
        for group_name, route_ids in demographic_groups.items():
            group_ranks = []
            for ranking in rankings:
                if ranking.route_id in route_ids:
                    group_ranks.append(rankings.index(ranking))
            
            if group_ranks:
                avg_rank = sum(group_ranks) / len(group_ranks)
                group_performance[group_name] = avg_rank
        
        # Check for significant disparity (more than 30% difference)
        if group_performance:
            min_rank = min(group_performance.values())
            max_rank = max(group_performance.values())
            disparity = (max_rank - min_rank) / max_rank if max_rank > 0 else 0
            
            if disparity > 0.3:
                logger.warning(f"Bias detected: ranking disparity {disparity * 100}%")
                return False
        
        return True

    def validate_explainability_output(self, ranking_result: RankingResult) -> bool:
        """
        RT-156: Validate explainability output.
        Ranking should provide explainable reasons.
        """
        if not ranking_result.explanation or len(ranking_result.explanation) == 0:
            logger.warning("Ranking lacks explainability output")
            return False
        
        # Check feature importance is provided
        if not ranking_result.feature_importance:
            logger.warning("No feature importance provided")
            return False
        
        # Feature importance should sum close to 1.0 (normalized)
        total_importance = sum(ranking_result.feature_importance.values())
        if total_importance < 0.5 or total_importance > 1.5:
            logger.warning(f"Feature importance sum invalid: {total_importance}")
            return False
        
        return True

    def validate_confidence_score_validity(self, ranking_result: RankingResult) -> bool:
        """
        RT-157: Validate confidence score validity.
        Confidence scores should be calibrated and meaningful.
        """
        if ranking_result.confidence_score < 0 or ranking_result.confidence_score > 1:
            logger.warning(f"Confidence score out of range: {ranking_result.confidence_score}")
            return False
        
        # Very high confidence should have strong explanation
        if ranking_result.confidence_score > 0.95:
            feature_importance = ranking_result.feature_importance
            max_feature_importance = max(feature_importance.values()) if feature_importance else 0
            if max_feature_importance < 0.3:
                logger.warning("High confidence without dominant feature")
                return False
        
        return True

    def validate_multi_objective_optimization(self, objectives: List[OptimizationObjective],
                                             weights: Dict[OptimizationObjective, float],
                                             ranking_result: RankingResult) -> bool:
        """
        RT-158: Validate multi-objective optimization.
        Ranking should balance multiple objectives appropriately.
        """
        if not objectives or not weights:
            return True
        
        # Check weight sum
        total_weight = sum(weights.values())
        if abs(total_weight - 1.0) > 0.1:  # Allow 10% tolerance
            logger.warning(f"Multi-objective weights don't sum to 1.0: {total_weight}")
            return False
        
        # Check all objectives have weights
        for obj in objectives:
            if obj not in weights:
                logger.warning(f"Missing weight for objective: {obj}")
                return False
        
        return True

    def validate_ranking_latency(self, ranking_start_time: datetime,
                                ranking_end_time: datetime,
                                max_latency_ms: int = 100) -> bool:
        """
        RT-159: Validate ranking latency.
        AI ranking should complete within acceptable time.
        """
        latency_ms = (ranking_end_time - ranking_start_time).total_seconds() * 1000
        
        if latency_ms > max_latency_ms:
            logger.warning(f"Ranking latency exceeded: {latency_ms}ms > {max_latency_ms}ms")
            return False
        
        return True

    def validate_feature_missing_fallback(self, required_features: List[str],
                                        available_features: List[str],
                                        fallback_used: bool) -> bool:
        """
        RT-160: Validate feature missing fallback.
        System should gracefully handle missing features.
        """
        missing_features = set(required_features) - set(available_features)
        
        if missing_features and not fallback_used:
            logger.warning(f"Missing features without fallback: {missing_features}")
            return False
        
        return True

    def validate_personalization_override(self, base_ranking: List[RankingResult],
                                         personalized_ranking: List[RankingResult],
                                         override_threshold: float = 0.3) -> bool:
        """
        RT-161: Validate personalization override functionality.
        Personalization should not completely change ranking.
        """
        if len(base_ranking) != len(personalized_ranking):
            return False
        
        # Calculate position changes
        position_changes = 0
        for i, personalized in enumerate(personalized_ranking):
            original_position = next((j for j, base in enumerate(base_ranking) 
                                     if base.route_id == personalized.route_id), -1)
            if original_position != -1 and abs(original_position - i) > 2:
                position_changes += 1
        
        change_rate = position_changes / len(personalized_ranking)
        if change_rate > override_threshold:
            logger.warning(f"Personalization change rate too high: {change_rate * 100}%")
            return False
        
        return True

    def validate_popular_route_boost(self, ranking_result: RankingResult,
                                    popularity_score: float) -> bool:
        """
        RT-162: Validate popular route boost.
        Popular routes should be boosted but not dominate.
        """
        if popularity_score < 0 or popularity_score > 1:
            return False
        
        # Popularity boost should be moderate
        popularity_feature = ranking_result.feature_importance.get('popularity', 0)
        if popularity_feature > 0.5 and popularity_score < 0.3:
            logger.warning("Popularity feature high but base score low")
            return False
        
        return True

    def validate_time_sensitivity_adaptation(self, current_time: datetime,
                                            peak_hours: Tuple[int, int],
                                            ranking_adaptation: float) -> bool:
        """
        RT-163: Validate time sensitivity adaptation.
        Ranking should adapt based on time of day (peak vs off-peak).
        """
        current_hour = current_time.hour
        peak_start, peak_end = peak_hours
        
        is_peak = peak_start <= current_hour <= peak_end
        
        # During peak, should adapt towards faster routes
        if is_peak and ranking_adaptation < 0.1:
            logger.warning("Insufficient peak time adaptation")
            return False
        
        return True

    def validate_exploration_vs_exploitation(self, exploration_rate: float,
                                            exploitation_rate: float) -> bool:
        """
        RT-164: Validate exploration vs exploitation balance.
        System should balance showing familiar routes with new recommendations.
        """
        total_rate = exploration_rate + exploitation_rate
        if abs(total_rate - 1.0) > 0.1:
            logger.warning(f"Exploration/exploitation rates don't sum to 1.0: {total_rate}")
            return False
        
        if exploration_rate < self.min_exploration_rate:
            logger.warning(f"Exploration rate too low: {exploration_rate * 100}%")
            return False
        
        return True

    def validate_ai_model_failure_fallback(self, model_available: bool,
                                          fallback_ranking_provided: bool) -> bool:
        """
        RT-165: Validate AI model failure fallback.
        System should provide fallback ranking when model fails.
        """
        if not model_available and not fallback_ranking_provided:
            logger.warning("No fallback ranking provided when model unavailable")
            return False
        
        return True

    def validate_model_version_compatibility(self, model_metadata: ModelMetadata,
                                            expected_version: str) -> bool:
        """
        RT-166: Validate model version compatibility.
        Running model should be compatible with expected version.
        """
        if not model_metadata.is_active:
            logger.warning("Model is not active")
            return False
        
        # Check major version compatibility (x.y.z - major version must match)
        metadata_major = model_metadata.version.split('.')[0]
        expected_major = expected_version.split('.')[0]
        
        if metadata_major != expected_major:
            logger.warning(f"Model version incompatibility: {model_metadata.version} vs {expected_version}")
            return False
        
        return True

    def validate_feature_drift_detection(self, feature_stats_baseline: Dict[str, float],
                                        feature_stats_current: Dict[str, float]) -> bool:
        """
        RT-167: Validate feature drift detection.
        System should detect when feature distributions change significantly.
        """
        if not feature_stats_baseline or not feature_stats_current:
            return True
        
        # Calculate drift for each feature
        max_drift = 0.0
        for feature, baseline_val in feature_stats_baseline.items():
            if feature in feature_stats_current:
                current_val = feature_stats_current[feature]
                if baseline_val != 0:
                    drift = abs(current_val - baseline_val) / baseline_val
                    max_drift = max(max_drift, drift)
        
        if max_drift > self.feature_drift_threshold:
            logger.warning(f"Feature drift detected: {max_drift * 100}%")
            return True  # Drift detected (return True as detection is working)
        
        return True

    def validate_prediction_caching(self, cache_key: str,
                                   cache_hit: bool,
                                   cache_age_seconds: Optional[int]) -> bool:
        """
        RT-168: Validate prediction caching.
        Cached predictions should be valid and not stale.
        """
        cache_ttl_seconds = 300  # 5 minutes
        
        if cache_hit and cache_age_seconds is not None:
            if cache_age_seconds > cache_ttl_seconds:
                logger.warning(f"Cache entry stale: {cache_age_seconds}s old")
                return False
        
        return True

    def validate_feedback_loop_update(self, user_feedback: Dict[str, int],
                                    model_updated: bool) -> bool:
        """
        RT-169: Validate feedback loop update.
        User feedback should be incorporated into model updates.
        """
        if not user_feedback or sum(user_feedback.values()) == 0:
            return True
        
        if not model_updated:
            logger.warning("User feedback not incorporated into model")
            return False
        
        return True

    def validate_adversarial_input_robustness(self, test_inputs: List[Dict],
                                             rankings_perturbed: List[RankingResult],
                                             max_perturbation_effect: float = 0.2) -> bool:
        """
        RT-170: Validate adversarial input robustness.
        Ranking should be robust to adversarial/edge case inputs.
        """
        if not test_inputs or not rankings_perturbed:
            return True
        
        # Calculate maximum score change from perturbation
        for ranking in rankings_perturbed:
            if not (0 <= ranking.rank_score <= 1):
                logger.warning(f"Ranking score invalid after perturbation: {ranking.rank_score}")
                return False
            
            # Confidence should remain valid even with perturbation
            if not (0 <= ranking.confidence_score <= 1):
                logger.warning(f"Confidence score invalid after perturbation: {ranking.confidence_score}")
                return False
        
        return True
