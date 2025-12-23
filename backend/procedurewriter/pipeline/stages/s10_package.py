"""Stage 10: PackageRelease - Create final release bundle.

The PackageRelease stage handles final bundle creation:
1. Receives all artifacts from previous stages
2. Creates a ZIP bundle with all files
3. Generates a manifest with checksums
4. Writes metadata for audit trail
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from procedurewriter.models.gates import Gate
from procedurewriter.models.issues import Issue
from procedurewriter.pipeline.events import EventType
from procedurewriter.pipeline.stages.base import PipelineStage

if TYPE_CHECKING:
    from procedurewriter.pipeline.events import EventEmitter

logger = logging.getLogger(__name__)


@dataclass
class PackageReleaseInput:
    """Input for the PackageRelease stage."""

    run_id: str
    run_dir: Path
    procedure_title: str
    issues: list[Issue]
    gates: list[Gate]
    iteration: int = 1
    emitter: "EventEmitter | None" = None


@dataclass
class PackageReleaseOutput:
    """Output from the PackageRelease stage."""

    run_id: str
    run_dir: Path
    procedure_title: str
    bundle_path: Path | None
    manifest: dict[str, Any]
    success: bool
    issues: list[Issue] = field(default_factory=list)
    gates: list[Gate] = field(default_factory=list)
    error_message: str | None = None


class PackageReleaseStage(PipelineStage[PackageReleaseInput, PackageReleaseOutput]):
    """Stage 10: PackageRelease - Create final release bundle."""

    @property
    def name(self) -> str:
        """Return the stage name."""
        return "package"

    def execute(self, input_data: PackageReleaseInput) -> PackageReleaseOutput:
        """Execute the package release stage.

        Creates a ZIP bundle with all artifacts and a manifest.

        Args:
            input_data: PackageRelease input containing run directory

        Returns:
            PackageRelease output with bundle path and manifest
        """
        # Emit progress event if emitter provided
        if input_data.emitter is not None:
            input_data.emitter.emit(
                EventType.PROGRESS,
                {
                    "message": f"Creating release bundle for {input_data.procedure_title}",
                    "stage": "package",
                },
            )

        try:
            # Collect files to include in bundle
            files_to_bundle = self._collect_files(input_data.run_dir)

            # Generate manifest with checksums
            manifest = self._generate_manifest(
                run_id=input_data.run_id,
                procedure_title=input_data.procedure_title,
                files=files_to_bundle,
            )

            # Write manifest to run directory
            manifest_path = input_data.run_dir / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2))

            # Create ZIP bundle
            bundle_path = self._create_zip_bundle(
                run_dir=input_data.run_dir,
                run_id=input_data.run_id,
                files=files_to_bundle,
                manifest_path=manifest_path,
            )

            logger.info(f"Created release bundle at {bundle_path}")

            return PackageReleaseOutput(
                run_id=input_data.run_id,
                run_dir=input_data.run_dir,
                procedure_title=input_data.procedure_title,
                bundle_path=bundle_path,
                manifest=manifest,
                success=True,
                issues=input_data.issues,
                gates=input_data.gates,
            )

        except Exception as e:
            logger.error(f"Failed to create release bundle: {e}")
            return PackageReleaseOutput(
                run_id=input_data.run_id,
                run_dir=input_data.run_dir,
                procedure_title=input_data.procedure_title,
                bundle_path=None,
                manifest={},
                success=False,
                issues=input_data.issues,
                gates=input_data.gates,
                error_message=str(e),
            )

    def _collect_files(self, run_dir: Path) -> list[Path]:
        """Collect files to include in the bundle.

        Args:
            run_dir: The run directory

        Returns:
            List of file paths to include
        """
        files: list[Path] = []

        # Include key files if they exist
        key_files = [
            "procedure.docx",
            "evidence_notes.json",
            "claims.json",
            "issues.json",
            "gates.json",
            "draft.md",
            "sources.json",
        ]

        for filename in key_files:
            file_path = run_dir / filename
            if file_path.exists():
                files.append(file_path)

        return files

    def _generate_manifest(
        self,
        run_id: str,
        procedure_title: str,
        files: list[Path],
    ) -> dict[str, Any]:
        """Generate manifest with file checksums.

        Args:
            run_id: The run ID
            procedure_title: The procedure title
            files: List of files to include

        Returns:
            Manifest dictionary
        """
        file_entries: list[dict[str, Any]] = []

        for file_path in files:
            sha256 = self._compute_sha256(file_path)
            file_entries.append(
                {
                    "filename": file_path.name,
                    "sha256": sha256,
                    "size": file_path.stat().st_size,
                }
            )

        return {
            "run_id": run_id,
            "procedure_title": procedure_title,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "files": file_entries,
            "version": "1.0",
        }

    def _compute_sha256(self, file_path: Path) -> str:
        """Compute SHA-256 checksum of a file.

        Args:
            file_path: Path to the file

        Returns:
            Hex-encoded SHA-256 checksum
        """
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _create_zip_bundle(
        self,
        run_dir: Path,
        run_id: str,
        files: list[Path],
        manifest_path: Path,
    ) -> Path:
        """Create the ZIP bundle atomically.

        R4-018: Uses temp file + rename pattern to prevent partial ZIP on failure.

        Args:
            run_dir: The run directory
            run_id: The run ID
            files: List of files to include
            manifest_path: Path to the manifest file

        Returns:
            Path to the created ZIP file
        """
        bundle_path = run_dir / f"release_{run_id}.zip"

        # R4-018: Write to temp file first, rename on success for atomicity
        fd, temp_path = tempfile.mkstemp(suffix=".zip", dir=run_dir)
        try:
            os.close(fd)  # Close the file descriptor, we'll open it with zipfile

            with zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as zf:
                # Add all collected files
                for file_path in files:
                    zf.write(file_path, file_path.name)

                # Add manifest
                zf.write(manifest_path, manifest_path.name)

            # Atomic rename on success (same filesystem)
            os.replace(temp_path, bundle_path)
            logger.debug(f"R4-018: Atomically created ZIP bundle at {bundle_path}")

        except Exception:
            # Clean up temp file on failure
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

        return bundle_path
