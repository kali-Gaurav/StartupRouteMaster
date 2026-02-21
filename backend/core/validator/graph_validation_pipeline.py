"""
Graph Building Validation & Integration Layer
Integrates all validators (transfer graph, ETL mapping, distance/time consistency)
into the graph builder workflow
"""

import logging
import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from sqlalchemy.orm import Session

from ...database import SessionLocal
from ..etl_mapping_validator import (
    ETLValidator, ETLLineageTracker, ETLExecutionLog, 
    ETLStatus, ETLMappingRegistry
)
from ..distance_time_validator import DistanceTimeConsistencyValidator, DistanceTimeValidationReport
from .transfer_graph_builder import TransferGraphBuilder, TransferEdge
from .graph import TimeDependentGraph, StaticGraphSnapshot

logger = logging.getLogger(__name__)


class GraphBuildingValidationPipeline:
    """
    Orchestrates the complete validation pipeline for graph building:
    1. ETL validation (data integrity checks)
    2. Distance/time consistency validation
    3. Transfer graph building and validation
    4. Final snapshot validation before use
    """

    def __init__(self, session: Optional[Session] = None):
        self.session = session or SessionLocal()
        self.etl_validator: Optional[ETLValidator] = None
        self.distance_time_validator: Optional[DistanceTimeConsistencyValidator] = None
        self.transfer_graph_builder: Optional[TransferGraphBuilder] = None
        self.etl_execution_log: Optional[ETLExecutionLog] = None
        self.validation_results: Dict[str, Any] = {}

    async def validate_and_prepare_for_graph_build(self, date: datetime) -> Dict[str, Any]:
        """
        Run complete validation pipeline before building graph.
        Returns validation results and indicators of what needs attention.
        """
        execution_id = str(uuid.uuid4())
        self.etl_execution_log = ETLExecutionLog(
            execution_id=execution_id,
            status=ETLStatus.IN_PROGRESS,
            start_time=datetime.utcnow()
        )
        
        logger.info(f"Starting graph building validation pipeline (execution_id={execution_id})")
        
        validation_results = {
            "execution_id": execution_id,
            "date": date,
            "etl_validation": None,
            "distance_time_validation": None,
            "transfer_graph_preparation": None,
            "overall_passed": False,
            "warnings": [],
            "errors": []
        }
        
        try:
            # Phase 1: ETL Validation
            logger.info("Phase 1: Running ETL validation...")
            etl_result = await self._validate_etl()
            validation_results["etl_validation"] = etl_result
            
            if not etl_result["passed"]:
                validation_results["errors"].extend(etl_result["errors"])
                logger.warning(f"ETL validation failed: {etl_result['errors']}")
            else:
                logger.info("✓ ETL validation passed")
            
            # Phase 2: Distance/Time Consistency Validation
            logger.info("Phase 2: Running distance/time consistency validation...")
            distance_result = await self._validate_distance_time_consistency()
            validation_results["distance_time_validation"] = distance_result
            
            if distance_result["issues"]:
                validation_results["warnings"].extend(distance_result["issues"])
                logger.warning(f"Distance/time validation found {len(distance_result['issues'])} issues")
            else:
                logger.info("✓ Distance/time validation passed")
            
            # Phase 3: Transfer Graph Preparation
            logger.info("Phase 3: Preparing transfer graph...")
            transfer_result = await self._prepare_transfer_graph()
            validation_results["transfer_graph_preparation"] = transfer_result
            
            if not transfer_result["passed"]:
                validation_results["errors"].append(f"Transfer graph preparation failed: {transfer_result['error']}")
                logger.warning(f"Transfer graph preparation failed: {transfer_result['error']}")
            else:
                logger.info(f"✓ Transfer graph prepared: {transfer_result['transfer_count']} transfers")
            
            # Overall status
            validation_results["overall_passed"] = (
                etl_result["passed"] and 
                transfer_result["passed"] and
                not any(issue["severity"] == "error" for issue in distance_result["issues"])
            )
            
            if validation_results["overall_passed"]:
                self.etl_execution_log.status = ETLStatus.SUCCESS
                logger.info("✅ All validations passed - ready for graph building")
            else:
                self.etl_execution_log.status = ETLStatus.VALIDATION_ERROR
                logger.warning("⚠️  Some validations failed - review errors before proceeding")
            
        except Exception as e:
            logger.error(f"Validation pipeline failed with exception: {e}")
            self.etl_execution_log.status = ETLStatus.FAILED
            self.etl_execution_log.validation_errors.append(str(e))
            validation_results["errors"].append(f"Pipeline exception: {str(e)}")
            validation_results["overall_passed"] = False
        
        finally:
            self.etl_execution_log.end_time = datetime.utcnow()
        
        self.validation_results = validation_results
        return validation_results

    async def _validate_etl(self) -> Dict[str, Any]:
        """Validate ETL data integrity"""
        result = {
            "passed": True,
            "errors": [],
            "warnings": [],
            "mapping_count": len(ETLMappingRegistry.get_all_mappings()),
            "checks_performed": []
        }
        
        try:
            # Create target session (we'll use the same for now)
            target_session = SessionLocal()
            
            self.etl_validator = ETLValidator(self.session, target_session)
            
            # Run validation checks
            checks = [
                ("referential_integrity", self.etl_validator.validate_referential_integrity),
                ("temporal_consistency", self.etl_validator.validate_temporal_consistency),
                ("geometric_consistency", self.etl_validator.validate_geometric_consistency),
                ("distance_consistency", self.etl_validator.validate_distance_consistency),
            ]
            
            all_passed = True
            for check_name, check_func in checks:
                try:
                    passed = await check_func()
                    result["checks_performed"].append({
                        "name": check_name,
                        "passed": passed
                    })
                    if not passed:
                        all_passed = False
                        result["errors"].extend(self.etl_validator.validation_errors)
                except Exception as e:
                    all_passed = False
                    result["errors"].append(f"Check '{check_name}' raised: {str(e)}")
            
            result["warnings"].extend(self.etl_validator.warnings)
            result["passed"] = all_passed
            
            target_session.close()
            
        except Exception as e:
            logger.exception(f"ETL validation failed: {e}")
            result["passed"] = False
            result["errors"].append(f"ETL validation exception: {str(e)}")
        
        return result

    async def _validate_distance_time_consistency(self) -> Dict[str, Any]:
        """Validate distance and time consistency"""
        result = {
            "passed": True,
            "issues": [],
            "statistics": {},
            "segments_checked": 0,
            "valid_segments": 0
        }
        
        try:
            self.distance_time_validator = DistanceTimeConsistencyValidator(self.session)
            report = await self.distance_time_validator.validate_all_segments()
            
            result["segments_checked"] = report.total_segments_checked
            result["valid_segments"] = report.valid_segments
            result["statistics"] = report.statistics
            result["passed"] = report.validation_passed
            
            # Convert issues to serializable format
            for issue in report.issues_found:
                result["issues"].append({
                    "type": issue.issue_type,
                    "severity": issue.severity,
                    "trip_id": issue.trip_id,
                    "from_stop": issue.from_stop_id,
                    "to_stop": issue.to_stop_id,
                    "message": issue.message,
                    "confidence": issue.confidence
                })
            
        except Exception as e:
            logger.exception(f"Distance/time validation failed: {e}")
            result["passed"] = False
            result["issues"].append({
                "type": "validation_error",
                "severity": "error",
                "message": f"Distance/time validator exception: {str(e)}"
            })
        
        return result

    async def _prepare_transfer_graph(self) -> Dict[str, Any]:
        """Prepare transfer graph"""
        result = {
            "passed": False,
            "transfer_count": 0,
            "error": None,
            "stops_connected": 0
        }
        
        try:
            self.transfer_graph_builder = TransferGraphBuilder(self.session)
            transfer_graph = await self.transfer_graph_builder.build_transfer_graph()
            
            result["transfer_count"] = sum(len(v) for v in transfer_graph.values())
            result["stops_connected"] = len(transfer_graph)
            result["passed"] = True
            
            logger.info(f"Transfer graph built: {result['stops_connected']} stops, {result['transfer_count']} edges")
            
        except Exception as e:
            logger.exception(f"Transfer graph preparation failed: {e}")
            result["error"] = str(e)
            result["passed"] = False
        
        return result

    def get_validation_report(self) -> Dict[str, Any]:
        """Get human-readable validation report"""
        if not self.validation_results:
            return {"status": "No validation run yet"}
        
        report = {
            "execution_id": self.validation_results.get("execution_id"),
            "date": str(self.validation_results.get("date")),
            "overall_status": "✅ PASSED" if self.validation_results["overall_passed"] else "❌ FAILED",
            "etl_validation": self.validation_results.get("etl_validation", {}).get("passed"),
            "distance_time_validation": self.validation_results.get("distance_time_validation", {}).get("passed"),
            "transfer_graph_ready": self.validation_results.get("transfer_graph_preparation", {}).get("passed"),
            "error_count": len(self.validation_results.get("errors", [])),
            "warning_count": len(self.validation_results.get("warnings", [])),
        }
        
        if self.validation_results.get("errors"):
            report["errors"] = self.validation_results["errors"]
        
        if self.validation_results.get("warnings"):
            report["warnings"] = self.validation_results["warnings"]
        
        return report

    async def apply_validated_data_to_graph(self, snapshot: StaticGraphSnapshot) -> StaticGraphSnapshot:
        """Apply validated data (transfer graph, etc.) to the snapshot"""
        try:
            # Inject transfer graph into snapshot if available
            if self.transfer_graph_builder:
                snapshot.transfer_graph = self.transfer_graph_builder._transfer_graph
                logger.info("Applied transfer graph to snapshot")
            
            # Could add more snapshot enrichments here
            
            return snapshot
            
        except Exception as e:
            logger.error(f"Failed to apply validated data to snapshot: {e}")
            return snapshot


async def validate_graph_before_build(date: datetime) -> Dict[str, Any]:
    """Convenience function to run complete validation"""
    pipeline = GraphBuildingValidationPipeline()
    return await pipeline.validate_and_prepare_for_graph_build(date)


def get_validation_report() -> Dict[str, Any]:
    """Get the validation report from the last run"""
    # This would need to be persisted somewhere in a production system
    pass
