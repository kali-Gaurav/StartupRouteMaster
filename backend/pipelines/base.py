"""
Base Pipeline Classes - Foundation for all 4 pipelines

Provides abstract base classes and interfaces for pipeline implementations.
All pipelines inherit from these to ensure consistent structure and behavior.
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class PipelineStatus(str, Enum):
    """Pipeline execution status."""
    IDLE = "IDLE"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


class PipelineMetrics:
    """Track pipeline performance and quality metrics."""

    def __init__(self, name: str):
        self.name = name
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.execution_time_ms: float = 0
        self.status: PipelineStatus = PipelineStatus.IDLE
        self.items_processed: int = 0
        self.items_succeeded: int = 0
        self.items_failed: int = 0
        self.errors: List[str] = []
        self.metadata: Dict[str, Any] = {}

    def start(self):
        """Mark pipeline start."""
        self.start_time = datetime.utcnow()
        self.status = PipelineStatus.PROCESSING

    def stop(self):
        """Mark pipeline end and calculate timing."""
        self.end_time = datetime.utcnow()
        if self.start_time:
            delta = self.end_time - self.start_time
            self.execution_time_ms = delta.total_seconds() * 1000

    def record_success(self, count: int = 1):
        """Record successful item processing."""
        self.items_processed += count
        self.items_succeeded += count

    def record_failure(self, count: int = 1, error: str = None):
        """Record failed item processing."""
        self.items_processed += count
        self.items_failed += count
        if error:
            self.errors.append(error)

    def finalize(self):
        """Finalize metrics and determine overall status."""
        if self.items_failed == 0:
            self.status = PipelineStatus.SUCCESS
        elif self.items_succeeded > 0:
            self.status = PipelineStatus.PARTIAL_SUCCESS
        else:
            self.status = PipelineStatus.FAILED

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            'name': self.name,
            'status': self.status.value,
            'execution_time_ms': round(self.execution_time_ms, 2),
            'items_processed': self.items_processed,
            'items_succeeded': self.items_succeeded,
            'items_failed': self.items_failed,
            'success_rate': round(
                self.items_succeeded / self.items_processed * 100, 2
            ) if self.items_processed > 0 else 0,
            'error_count': len(self.errors),
            'errors': self.errors[:5],  # First 5 errors
            'metadata': self.metadata
        }


class BasePipelineStage(ABC):
    """Abstract base class for pipeline stages.

    Each stage is a distinct processing step in a pipeline.
    Stages can be composed to build complex pipelines.
    """

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
        self.metrics = PipelineMetrics(name)

    @abstractmethod
    async def process(self, input_data: Any) -> Any:
        """
        Process input data through this stage.

        Args:
            input_data: Data to process

        Returns:
            Processed data for next stage
        """
        pass

    async def execute(self, input_data: Any) -> Any:
        """
        Execute stage with metrics tracking.

        Args:
            input_data: Data to process

        Returns:
            Processed data
        """
        self.metrics.start()
        try:
            result = await self.process(input_data)
            self.metrics.record_success()
            self.metrics.status = PipelineStatus.SUCCESS
            return result
        except Exception as e:
            self.logger.error(f"Stage {self.name} failed: {e}")
            self.metrics.record_failure(error=str(e))
            self.metrics.status = PipelineStatus.FAILED
            raise
        finally:
            self.metrics.stop()

    def get_metrics(self) -> Dict[str, Any]:
        """Get stage metrics."""
        return self.metrics.to_dict()


class BasePipeline(ABC):
    """Abstract base class for pipelines.

    A pipeline is composed of multiple stages that process data sequentially.
    """

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
        self.stages: List[BasePipelineStage] = []
        self.metrics = PipelineMetrics(name)
        self.enabled: bool = True

    def add_stage(self, stage: BasePipelineStage) -> None:
        """Add a stage to the pipeline."""
        self.stages.append(stage)
        self.logger.info(f"Added stage: {stage.name}")

    async def execute(self, input_data: Any) -> Any:
        """
        Execute pipeline, passing data through all stages.

        Args:
            input_data: Initial data

        Returns:
            Processed data from final stage
        """
        if not self.enabled:
            self.logger.warning(f"Pipeline {self.name} is disabled")
            return input_data

        self.metrics.start()
        current_data = input_data

        try:
            for stage in self.stages:
                self.logger.debug(f"Executing stage: {stage.name}")
                current_data = await stage.execute(current_data)

            self.metrics.record_success()
            self.metrics.status = PipelineStatus.SUCCESS
            return current_data

        except Exception as e:
            self.logger.error(f"Pipeline {self.name} failed: {e}")
            self.metrics.record_failure(error=str(e))
            self.metrics.status = PipelineStatus.FAILED
            raise
        finally:
            self.metrics.stop()

    def get_metrics(self) -> Dict[str, Any]:
        """Get pipeline metrics including all stages."""
        return {
            'pipeline': self.metrics.to_dict(),
            'stages': [stage.get_metrics() for stage in self.stages]
        }

    def disable(self):
        """Disable pipeline (bypass processing)."""
        self.enabled = False
        self.logger.info(f"Pipeline {self.name} disabled")

    def enable(self):
        """Enable pipeline."""
        self.enabled = True
        self.logger.info(f"Pipeline {self.name} enabled")


class PipelineOrchestrator:
    """Orchestrates multiple pipelines.

    Routes data through pipelines, handles errors, and tracks metrics.
    """

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
        self.pipelines: Dict[str, BasePipeline] = {}

    def register_pipeline(self, pipeline: BasePipeline) -> None:
        """Register a pipeline."""
        self.pipelines[pipeline.name] = pipeline
        self.logger.info(f"Registered pipeline: {pipeline.name}")

    async def execute_pipeline(
        self,
        pipeline_name: str,
        input_data: Any
    ) -> Any:
        """Execute specific pipeline."""
        if pipeline_name not in self.pipelines:
            raise ValueError(f"Unknown pipeline: {pipeline_name}")

        return await self.pipelines[pipeline_name].execute(input_data)

    async def execute_all_pipelines(
        self,
        input_data: Any
    ) -> Dict[str, Any]:
        """Execute all registered pipelines.

        Args:
            input_data: Input data

        Returns:
            Dict of pipeline_name -> output
        """
        results = {}
        for name, pipeline in self.pipelines.items():
            try:
                results[name] = await pipeline.execute(input_data)
            except Exception as e:
                self.logger.error(f"Pipeline {name} failed: {e}")
                results[name] = {'error': str(e)}

        return results

    def get_metrics(self) -> Dict[str, Any]:
        """Get metrics from all pipelines."""
        return {
            pipeline_name: pipeline.get_metrics()
            for pipeline_name, pipeline in self.pipelines.items()
        }


# Context carriers for data flow

class PipelineContext:
    """Context data passed through pipeline stages.

    Maintains state, metadata, and configuration across stages.
    """

    def __init__(self, **kwargs):
        self.data: Dict[str, Any] = kwargs
        self.metadata: Dict[str, Any] = {
            'created_at': datetime.utcnow(),
            'stages_processed': []
        }
        self.errors: List[str] = []

    def set(self, key: str, value: Any) -> None:
        """Set context value."""
        self.data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get context value."""
        return self.data.get(key, default)

    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata."""
        self.metadata[key] = value

    def add_error(self, error: str) -> None:
        """Record error."""
        self.errors.append(error)

    def mark_stage_processed(self, stage_name: str) -> None:
        """Record that a stage has been processed."""
        self.metadata['stages_processed'].append(stage_name)

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary."""
        return {
            'data': self.data,
            'metadata': self.metadata,
            'errors': self.errors
        }
