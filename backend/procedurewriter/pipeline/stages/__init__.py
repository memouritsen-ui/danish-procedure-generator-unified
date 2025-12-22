"""Pipeline stages module.

Contains the PipelineStage base class and all stage implementations.

Stage order:
- 00: Bootstrap - Init run, dirs
- 01: TermExpand - Danish→English
- 02: Retrieve - Source fetching
- 03: Chunk - Evidence chunking
- 04: EvidenceNotes - LLM summarization
- 05: Draft - Writer agent
- 06: ClaimExtract - Parse claims
- 07: Bind - Link to evidence
- 08: Evals - Run lints
- 09: ReviseLoop - Max 3 iterations
- 10: PackageRelease - ZIP bundle
"""

from procedurewriter.pipeline.stages.base import PipelineStage
from procedurewriter.pipeline.stages.s00_bootstrap import (
    BootstrapInput,
    BootstrapOutput,
    BootstrapStage,
)
from procedurewriter.pipeline.stages.s01_termexpand import (
    TermExpandInput,
    TermExpandOutput,
    TermExpandStage,
)
from procedurewriter.pipeline.stages.s02_retrieve import (
    RetrieveInput,
    RetrieveOutput,
    RetrieveStage,
    SourceInfo,
)
from procedurewriter.pipeline.stages.s03_chunk import (
    ChunkInput,
    ChunkOutput,
    ChunkStage,
)

__all__ = [
    "PipelineStage",
    "BootstrapInput",
    "BootstrapOutput",
    "BootstrapStage",
    "TermExpandInput",
    "TermExpandOutput",
    "TermExpandStage",
    "RetrieveInput",
    "RetrieveOutput",
    "RetrieveStage",
    "SourceInfo",
    "ChunkInput",
    "ChunkOutput",
    "ChunkStage",
]
