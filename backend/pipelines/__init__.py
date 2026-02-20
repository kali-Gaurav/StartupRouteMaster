"""
Backend Pipelines - Advanced 4-Pipeline Data Architecture

Four specialized pipelines for different aspects of the system:
1. Data Enrichment Pipeline - Fill missing data from live sources
2. ML Training Pipeline - Continuous learning from events
3. Prediction Pipeline - Make intelligent predictions
4. Verification Pipeline - Verify data before booking

Each pipeline has multi-level stages for clean data flow and performance.
"""

from .base import (
    BasePipeline,
    BasePipelineStage,
    PipelineContext,
    PipelineMetrics,
    PipelineOrchestrator,
    PipelineStatus,
)

__all__ = [
    'BasePipeline',
    'BasePipelineStage',
    'PipelineContext',
    'PipelineMetrics',
    'PipelineOrchestrator',
    'PipelineStatus',
]
