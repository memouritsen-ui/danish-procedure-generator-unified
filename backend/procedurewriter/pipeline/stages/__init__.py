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
from procedurewriter.pipeline.stages.s04_evidencenotes import (
    EvidenceNotesInput,
    EvidenceNotesOutput,
    EvidenceNotesStage,
)
from procedurewriter.pipeline.stages.s05_draft import (
    DraftInput,
    DraftOutput,
    DraftStage,
)
from procedurewriter.pipeline.stages.s06_claimextract import (
    ClaimExtractInput,
    ClaimExtractOutput,
    ClaimExtractStage,
)
from procedurewriter.pipeline.stages.s07_bind import (
    BindInput,
    BindOutput,
    BindStage,
)
from procedurewriter.pipeline.stages.s08_evals import (
    EvalsInput,
    EvalsOutput,
    EvalsStage,
)
from procedurewriter.pipeline.stages.s09_reviseloop import (
    ReviseLoopInput,
    ReviseLoopOutput,
    ReviseLoopStage,
)
from procedurewriter.pipeline.stages.s10_package import (
    PackageReleaseInput,
    PackageReleaseOutput,
    PackageReleaseStage,
)

__all__ = [
    # Base
    "PipelineStage",
    # Stage 00: Bootstrap
    "BootstrapInput",
    "BootstrapOutput",
    "BootstrapStage",
    # Stage 01: TermExpand
    "TermExpandInput",
    "TermExpandOutput",
    "TermExpandStage",
    # Stage 02: Retrieve
    "RetrieveInput",
    "RetrieveOutput",
    "RetrieveStage",
    "SourceInfo",
    # Stage 03: Chunk
    "ChunkInput",
    "ChunkOutput",
    "ChunkStage",
    # Stage 04: EvidenceNotes
    "EvidenceNotesInput",
    "EvidenceNotesOutput",
    "EvidenceNotesStage",
    # Stage 05: Draft
    "DraftInput",
    "DraftOutput",
    "DraftStage",
    # Stage 06: ClaimExtract
    "ClaimExtractInput",
    "ClaimExtractOutput",
    "ClaimExtractStage",
    # Stage 07: Bind
    "BindInput",
    "BindOutput",
    "BindStage",
    # Stage 08: Evals
    "EvalsInput",
    "EvalsOutput",
    "EvalsStage",
    # Stage 09: ReviseLoop
    "ReviseLoopInput",
    "ReviseLoopOutput",
    "ReviseLoopStage",
    # Stage 10: PackageRelease
    "PackageReleaseInput",
    "PackageReleaseOutput",
    "PackageReleaseStage",
]
