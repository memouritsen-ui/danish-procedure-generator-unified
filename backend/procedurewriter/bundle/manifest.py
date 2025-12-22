"""ManifestBuilder - Structured manifest creation for procedure releases.

This module provides the ManifestBuilder class which creates manifest.json files
for release bundles with support for:
- Metadata (run_id, procedure, version, timestamps)
- File checksums via ZipBuilder integration
- Optional sections (LLM config, quality, runtime, sources, cost)

Example:
    builder = ManifestBuilder(run_dir)
    builder.set_run_id(run_id).set_procedure("Akut astma").set_version("1.0.0")
    builder.include_checksums()
    builder.build(output_path)
"""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from procedurewriter.bundle.builder import ZipBuilder


class ManifestBuilder:
    """Creates manifest.json files for procedure release bundles.

    Provides a fluent interface for configuring and building manifest files.

    Attributes:
        run_dir: The source directory to create manifest for.
    """

    def __init__(self, run_dir: Path) -> None:
        """Initialize ManifestBuilder with a run directory.

        Args:
            run_dir: Path to the run directory.

        Raises:
            FileNotFoundError: If run_dir does not exist.
            ValueError: If run_dir is not a directory.
        """
        if not run_dir.exists():
            raise FileNotFoundError(f"Run directory not found: {run_dir}")
        if not run_dir.is_dir():
            raise ValueError(f"Path is not a directory: {run_dir}")

        self.run_dir = run_dir
        self._data: dict[str, Any] = {
            "version": "1.0.0",  # Default manifest version
        }
        self._exclude_patterns: list[str] = []
        self._include_checksums: bool = False

    def set_run_id(self, run_id: str) -> ManifestBuilder:
        """Set the run ID in the manifest.

        Args:
            run_id: Unique identifier for the run.

        Returns:
            Self for method chaining.
        """
        self._data["run_id"] = run_id
        return self

    def set_procedure(self, procedure: str) -> ManifestBuilder:
        """Set the procedure name in the manifest.

        Args:
            procedure: Name of the procedure (e.g., "Akut astma behandling").

        Returns:
            Self for method chaining.
        """
        self._data["procedure"] = procedure
        return self

    def set_version(self, version: str) -> ManifestBuilder:
        """Set the manifest version.

        Args:
            version: Version string (e.g., "1.0.0").

        Returns:
            Self for method chaining.
        """
        self._data["version"] = version
        return self

    def set_created_at(self, timestamp: str) -> ManifestBuilder:
        """Set the created_at timestamp.

        Args:
            timestamp: ISO 8601 timestamp string.

        Returns:
            Self for method chaining.
        """
        self._data["created_at"] = timestamp
        return self

    def add_llm_config(self, config: dict[str, Any]) -> ManifestBuilder:
        """Add LLM configuration section.

        Args:
            config: Dictionary with LLM settings (provider, model, etc.).

        Returns:
            Self for method chaining.
        """
        self._data["llm_config"] = config
        return self

    def add_quality(self, quality: dict[str, Any]) -> ManifestBuilder:
        """Add quality metrics section.

        Args:
            quality: Dictionary with quality info (final_score, gates_passed, etc.).

        Returns:
            Self for method chaining.
        """
        self._data["quality"] = quality
        return self

    def add_runtime(self, runtime: dict[str, Any]) -> ManifestBuilder:
        """Add runtime information section.

        Args:
            runtime: Dictionary with runtime info (duration, stage_timings, etc.).

        Returns:
            Self for method chaining.
        """
        self._data["runtime"] = runtime
        return self

    def add_sources(self, sources: dict[str, Any]) -> ManifestBuilder:
        """Add sources information section.

        Args:
            sources: Dictionary with source info (total_count, by_tier, etc.).

        Returns:
            Self for method chaining.
        """
        self._data["sources"] = sources
        return self

    def add_cost(self, cost: dict[str, Any]) -> ManifestBuilder:
        """Add cost information section.

        Args:
            cost: Dictionary with cost info (total_usd, input_tokens, etc.).

        Returns:
            Self for method chaining.
        """
        self._data["cost"] = cost
        return self

    def exclude(self, pattern: str) -> ManifestBuilder:
        """Add a glob pattern to exclude from checksums.

        Args:
            pattern: Glob pattern to exclude (e.g., "*.log", "__pycache__/**").

        Returns:
            Self for method chaining.
        """
        self._exclude_patterns.append(pattern)
        return self

    def include_checksums(self) -> ManifestBuilder:
        """Include file checksums in the manifest.

        Uses ZipBuilder to calculate SHA-256 checksums for all included files.

        Returns:
            Self for method chaining.
        """
        self._include_checksums = True
        return self

    def _calculate_checksums(self) -> dict[str, str]:
        """Calculate checksums using ZipBuilder.

        Returns:
            Dict mapping relative file paths to SHA-256 hex digests.
        """
        zip_builder = ZipBuilder(self.run_dir)
        for pattern in self._exclude_patterns:
            zip_builder.exclude(pattern)
        return zip_builder.get_checksums()

    def to_dict(self) -> dict[str, Any]:
        """Get the current manifest as a dictionary.

        Returns:
            Deep copy of the manifest data.
        """
        result = copy.deepcopy(self._data)

        # Calculate checksums if requested
        if self._include_checksums:
            result["checksums"] = self._calculate_checksums()

        return result

    def build(self, output_path: Path) -> str:
        """Build the manifest JSON file.

        Args:
            output_path: Where to write the manifest.json file.

        Returns:
            SHA-256 hash of the manifest content.
        """
        # Create parent directories if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Add created_at if not set
        if "created_at" not in self._data:
            self._data["created_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # Build the manifest dict
        manifest = self.to_dict()

        # Serialize with sorted keys for reproducibility
        serialized = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

        # Write to file
        output_path.write_text(serialized, encoding="utf-8")

        # Return SHA-256 hash
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
