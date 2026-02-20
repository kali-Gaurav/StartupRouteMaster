"""
Pipeline Initialization and Orchestration

Sets up all 4 pipelines and provides unified interface for system.
"""

import logging
from typing import Optional

from .base import BasePipeline, PipelineOrchestrator
from .enrichment.enrichment_engine import (
    LiveFareConnector,
    LiveDelayConnector,
    LiveSeatConnector,
    LiveBookingConnector,
    DataReconciler,
    DataWriter,
)

logger = logging.getLogger(__name__)


class EnrichmentPipeline(BasePipeline):
    """Pipeline 1: Data Enrichment Pipeline

    Fetches live data and enriches database.
    """

    def __init__(self, config=None):
        super().__init__('EnrichmentPipeline')

        if config is None:
            try:
                from ..config import Config
                config = Config
            except ImportError:
                logger.warning("Config not available, enrichment pipeline disabled")
                self.disable()
                return

        # Add stages
        self.add_stage(LiveFareConnector(getattr(config, 'LIVE_FARES_API', None)))
        self.add_stage(LiveDelayConnector(getattr(config, 'LIVE_DELAY_API', None)))
        self.add_stage(LiveSeatConnector(getattr(config, 'LIVE_SEAT_API', None)))
        self.add_stage(LiveBookingConnector(getattr(config, 'LIVE_BOOKING_API', None)))
        self.add_stage(DataReconciler())
        self.add_stage(DataWriter())

        logger.info("EnrichmentPipeline initialized with {} stages".format(len(self.stages)))


class PipelineSystemInitializer:
    """Initialize pipeline system at application startup."""

    def __init__(self):
        self.orchestrator = PipelineOrchestrator('BackendPipelineSystem')
        self.enrichment_pipeline: Optional[EnrichmentPipeline] = None

    def initialize(self, config=None):
        """Initialize all pipelines."""
        logger.info("")
        logger.info("=" * 70)
        logger.info("🔄 Initializing Backend Pipeline System (4-Pipeline Architecture)")
        logger.info("=" * 70)

        if config is None:
            try:
                from ..config import Config
                config = Config
            except ImportError:
                logger.error("Config not available, pipelines cannot initialize")
                return False

        try:
            # Initialize Pipeline 1: Enrichment
            self.enrichment_pipeline = EnrichmentPipeline(config)
            self.orchestrator.register_pipeline(self.enrichment_pipeline)
            logger.info("✅ Pipeline 1 (Data Enrichment): Initialized")

            # TODO: Initialize Pipeline 2: ML Training
            logger.info("⏳ Pipeline 2 (ML Training): Pending implementation")

            # TODO: Initialize Pipeline 3: Prediction
            logger.info("⏳ Pipeline 3 (Prediction & Correction): Pending implementation")

            # TODO: Initialize Pipeline 4: Verification
            logger.info("⏳ Pipeline 4 (Verification): Pending implementation")

            logger.info("")
            logger.info("🎯 Pipeline System Status: READY")
            logger.info(f"   Mode: {config.get_mode() if hasattr(config, 'get_mode') else 'OFFLINE'}")
            logger.info(f"   Enabled Pipelines: {len(self.orchestrator.pipelines)}/4")
            logger.info("=" * 70)
            logger.info("")

            return True

        except Exception as e:
            logger.error(f"Pipeline system initialization failed: {e}")
            return False

    def get_orchestrator(self) -> PipelineOrchestrator:
        """Get the orchestrator instance."""
        return self.orchestrator


# Global pipeline system instance
_pipeline_system: Optional[PipelineSystemInitializer] = None


def get_pipeline_system() -> PipelineSystemInitializer:
    """Get or create pipeline system singleton."""
    global _pipeline_system
    if _pipeline_system is None:
        _pipeline_system = PipelineSystemInitializer()
    return _pipeline_system


def initialize_pipelines(config=None) -> bool:
    """Initialize pipeline system at application startup."""
    system = get_pipeline_system()
    return system.initialize(config)
