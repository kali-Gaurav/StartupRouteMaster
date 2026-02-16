"""
Decision Engine — Autonomous Decision Making

Makes intelligent decisions about:
- Data validity and quality
- Storage actions (insert/update/ignore)
- Retry strategies
- Source prioritization
- Error recovery
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class DecisionEngine:
    """
    Autonomous decision-making system for data handling.
    """

    def __init__(self, gemini_client=None):
        """
        Initialize DecisionEngine.

        Args:
            gemini_client: GeminiClient for AI-powered decisions
        """
        self.gemini = gemini_client
        self.decision_history = []  # Track decisions for learning

    async def decide_data_validity(
        self, extracted_data: Dict[str, Any], data_type: str = ""
    ) -> Dict[str, Any]:
        """
        Evaluate if extracted data is valid and should be stored.

        Args:
            extracted_data: Extracted data fields
            data_type: Type of data (e.g., 'train_schedule', 'flight_results')

        Returns:
            {
                'valid': bool,
                'confidence': 0.0-1.0,
                'issues': [str, ...],
                'recommendation': 'STORE' | 'REVIEW' | 'DISCARD' | 'INVESTIGATE',
                'missing_fields': [str, ...],
                'corrupted_fields': [str, ...]
            }
        """
        logger.info(f"Evaluating data validity (type: {data_type})...")

        decision = {
            "valid": True,
            "confidence": 1.0,
            "issues": [],
            "recommendation": "STORE",
            "missing_fields": [],
            "corrupted_fields": [],
        }

        # Check for missing required fields
        required_field_count = len([v for v in extracted_data.values() if v.get("value")])
        total_field_count = len(extracted_data)

        if required_field_count == 0:
            decision["valid"] = False
            decision["confidence"] = 0.0
            decision["recommendation"] = "DISCARD"
            decision["issues"].append("No fields extracted")
            logger.warning("No fields extracted - marking as invalid")
            return decision

        if required_field_count < total_field_count * 0.5:
            decision["issues"].append(
                f"Only {required_field_count}/{total_field_count} fields extracted"
            )
            decision["confidence"] = 0.6
            decision["recommendation"] = "REVIEW"

        # Check field-level confidence
        low_confidence_fields = [
            name for name, info in extracted_data.items()
            if info.get("confidence", 1.0) < 0.5
        ]
        if low_confidence_fields:
            decision["issues"].append(
                f"Low confidence on fields: {', '.join(low_confidence_fields[:3])}"
            )
            decision["confidence"] = min(decision["confidence"], 0.7)

        # Check validation results
        failed_validations = [
            name for name, info in extracted_data.items()
            if not info.get("validation_passed", True)
        ]
        if failed_validations:
            decision["corrupted_fields"] = failed_validations
            decision["issues"].append(
                f"Validation failed on: {', '.join(failed_validations[:3])}"
            )
            decision["confidence"] = min(decision["confidence"], 0.5)

        # Make recommendation
        if decision["confidence"] >= 0.85:
            decision["recommendation"] = "STORE"
            decision["valid"] = True
        elif decision["confidence"] >= 0.60:
            decision["recommendation"] = "REVIEW"
            decision["valid"] = True
        elif decision["confidence"] >= 0.30:
            decision["recommendation"] = "INVESTIGATE"
            decision["valid"] = False
        else:
            decision["recommendation"] = "DISCARD"
            decision["valid"] = False

        logger.info(
            f"Data validity: {decision['recommendation']} "
            f"(confidence: {decision['confidence']:.2f}, issues: {len(decision['issues'])})"
        )

        return decision

    async def decide_storage_action(
        self, extracted_data: Dict[str, Any], existing_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Decide what storage action to take (insert/update/duplicate/conflict).

        Args:
            extracted_data: Newly extracted data
            existing_data: Existing data in DB (if any)

        Returns:
            {
                'action': 'NEW_INSERT' | 'UPDATE_EXISTING' | 'DUPLICATE_IGNORE' | 'CONFLICT_ALERT',
                'rationale': str,
                'confidence': 0.0-1.0
            }
        """
        logger.info("Deciding storage action...")

        if not existing_data:
            logger.info("No existing data - action: NEW_INSERT")
            return {
                "action": "NEW_INSERT",
                "rationale": "No existing record found",
                "confidence": 1.0,
            }

        # Compare key fields
        differences = self._compare_data(extracted_data, existing_data)

        if not differences["changed_fields"]:
            logger.info("No changes detected - action: DUPLICATE_IGNORE")
            return {
                "action": "DUPLICATE_IGNORE",
                "rationale": "Identical to existing record",
                "confidence": 0.95,
            }

        # Check if changes are significant
        change_significance = self._calculate_change_significance(differences)

        if change_significance < 0.1:
            return {
                "action": "DUPLICATE_IGNORE",
                "rationale": f"Minor changes only ({change_significance:.1%})",
                "confidence": 0.8,
            }

        if change_significance < 0.3:
            return {
                "action": "UPDATE_EXISTING",
                "rationale": f"Moderate changes detected ({change_significance:.1%})",
                "confidence": 0.85,
            }

        if change_significance >= 0.3:
            # Could be data corruption or significant update
            if self._has_suspicious_changes(differences):
                logger.warning("Suspicious changes detected")
                return {
                    "action": "CONFLICT_ALERT",
                    "rationale": "Suspicious changes - manual review recommended",
                    "confidence": 0.7,
                }
            else:
                return {
                    "action": "UPDATE_EXISTING",
                    "rationale": f"Significant changes ({change_significance:.1%})",
                    "confidence": 0.75,
                }

        return {
            "action": "UPDATE_EXISTING",
            "rationale": "Changes detected",
            "confidence": 0.8,
        }

    async def decide_retry_strategy(
        self, error_info: Dict[str, Any], attempt_number: int = 1, max_attempts: int = 3
    ) -> Dict[str, Any]:
        """
        Recommend retry strategy based on error type.

        Args:
            error_info: Error details
            attempt_number: Current attempt number
            max_attempts: Maximum retry attempts

        Returns:
            {
                'should_retry': bool,
                'strategy': 'RESET_BROWSER' | 'ROTATE_PROXY' | 'CHANGE_UA' | 'FALLBACK_API' | 'ESCALATE' | None,
                'wait_seconds': int,
                'rationale': str
            }
        """
        logger.info(f"Determining retry strategy (attempt {attempt_number}/{max_attempts})...")

        error_type = error_info.get("type", "unknown")
        error_message = error_info.get("message", "").lower()

        # Don't retry if max attempts reached
        if attempt_number >= max_attempts:
            logger.info("Max attempts reached - no retry")
            return {
                "should_retry": False,
                "strategy": None,
                "wait_seconds": 0,
                "rationale": "Max retry attempts reached",
            }

        # Analyze error and recommend strategy
        if "403" in error_message or "blocked" in error_message:
            return {
                "should_retry": True,
                "strategy": "ROTATE_PROXY",
                "wait_seconds": 30,
                "rationale": "Blocked/403 error - rotate proxy",
            }

        elif "timeout" in error_message or "504" in error_message:
            wait_time = min(2 ** attempt_number, 60)  # Exponential backoff
            return {
                "should_retry": True,
                "strategy": "RESET_BROWSER",
                "wait_seconds": wait_time,
                "rationale": f"Timeout error - reset browser and wait {wait_time}s",
            }

        elif "selector" in error_message or "not found" in error_message:
            return {
                "should_retry": True,
                "strategy": "CHANGE_UA",
                "wait_seconds": 10,
                "rationale": "Selector not found - layout might have changed, try different UA",
            }

        elif "network" in error_message or "connection" in error_message:
            return {
                "should_retry": True,
                "strategy": "RESET_BROWSER",
                "wait_seconds": 20,
                "rationale": "Network error - reset browser and retry",
            }

        elif "javascript" in error_message or "js" in error_message.lower():
            return {
                "should_retry": True,
                "strategy": "FALLBACK_API",
                "wait_seconds": 5,
                "rationale": "JavaScript execution issue - try API fallback",
            }

        else:
            # Unknown error - generic retry
            return {
                "should_retry": True,
                "strategy": "RESET_BROWSER",
                "wait_seconds": 15,
                "rationale": f"Unknown error ({error_type}) - reset and retry",
            }

    async def decide_source_priority(
        self,
        data_type: str,
        available_sources: List[str],
        criteria: List[str] = None,
    ) -> List[str]:
        """
        Rank sources by priority for a specific data type.

        Args:
            data_type: 'schedule' | 'live_status' | 'availability' | 'booking'
            available_sources: List of available source names
            criteria: Priority criteria (e.g., ['reliability', 'freshness', 'completeness'])

        Returns:
            Ranked list of sources from best to worst
        """
        logger.info(f"Ranking sources for {data_type}...")

        if not criteria:
            criteria = ["reliability", "freshness", "completeness"]

        # Default source rankings by data type
        source_rankings = {
            "schedule": {
                "NTES": 100,  # Official, most reliable
                "IRCTC": 85,  # Official but sometimes incomplete
                "Abhaneri": 70,  # Alternative API
                "Wikipedia": 40,  # Community maintained
            },
            "live_status": {
                "NTES": 100,  # Most current
                "IRCTC": 90,
                "Abhaneri": 60,
            },
            "availability": {
                "IRCTC": 100,  # Official booking source
                "AskDisha": 95,  # IRCTC chatbot
                "MakeMyTrip": 80,  # Third-party aggregator
            },
            "booking": {
                "IRCTC": 100,  # Official
                "MakeMyTrip": 85,
                "Cleartrip": 85,
            },
        }

        rankings = source_rankings.get(data_type, {})

        # Score available sources
        scored_sources = [
            (source, rankings.get(source, 50)) for source in available_sources
        ]

        # Sort by score
        scored_sources.sort(key=lambda x: x[1], reverse=True)
        ranked = [source for source, score in scored_sources]

        logger.info(f"Source priority: {' > '.join(ranked)}")
        return ranked

    async def decide_data_freshness_requirement(
        self, data_type: str
    ) -> Dict[str, Any]:
        """
        Decide how fresh data needs to be for this data type.

        Args:
            data_type: Type of data

        Returns:
            {
                'max_age_minutes': int,
                'require_live_check': bool,
                'cache_strategy': 'no_cache' | 'short_term' | 'long_term'
            }
        """
        freshness_requirements = {
            "live_status": {
                "max_age_minutes": 5,
                "require_live_check": True,
                "cache_strategy": "no_cache",
            },
            "schedule": {
                "max_age_minutes": 1440,  # 24 hours
                "require_live_check": False,
                "cache_strategy": "long_term",
            },
            "availability": {
                "max_age_minutes": 30,
                "require_live_check": True,
                "cache_strategy": "short_term",
            },
            "booking": {
                "max_age_minutes": 2,
                "require_live_check": True,
                "cache_strategy": "no_cache",
            },
        }

        return freshness_requirements.get(
            data_type,
            {
                "max_age_minutes": 60,
                "require_live_check": False,
                "cache_strategy": "short_term",
            },
        )

    # Helper methods

    def _compare_data(
        self, new_data: Dict[str, Any], existing_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare two datasets and find differences."""
        differences = {
            "changed_fields": [],
            "new_fields": [],
            "removed_fields": [],
            "unchanged_fields": [],
        }

        for key, new_val in new_data.items():
            new_value = new_val.get("value") if isinstance(new_val, dict) else new_val
            existing_val = existing_data.get(key)
            existing_value = (
                existing_val.get("value") if isinstance(existing_val, dict) else existing_val
            )

            if key not in existing_data:
                differences["new_fields"].append(key)
            elif new_value != existing_value:
                differences["changed_fields"].append(
                    {"field": key, "old": existing_value, "new": new_value}
                )
            else:
                differences["unchanged_fields"].append(key)

        for key in existing_data:
            if key not in new_data:
                differences["removed_fields"].append(key)

        return differences

    def _calculate_change_significance(self, differences: Dict[str, Any]) -> float:
        """Calculate how significant the changes are (0.0-1.0)."""
        total_fields = (
            len(differences.get("changed_fields", []))
            + len(differences.get("unchanged_fields", []))
        )

        if total_fields == 0:
            return 0.0

        changed_count = len(differences.get("changed_fields", []))
        return changed_count / total_fields

    def _has_suspicious_changes(self, differences: Dict[str, Any]) -> bool:
        """Detect suspicious/anomalous changes."""
        for change in differences.get("changed_fields", []):
            old_val = str(change.get("old", "")).strip()
            new_val = str(change.get("new", "")).strip()

            # Check for sudden reversal of status
            if old_val in ["Active", "On Time"] and new_val in ["Cancelled", "Delayed"]:
                return True

            # Check for massive value changes
            try:
                old_num = float(old_val.replace(",", ""))
                new_num = float(new_val.replace(",", ""))
                if abs(new_num - old_num) / old_num > 2:  # > 200% change
                    return True
            except:
                pass

        return False
