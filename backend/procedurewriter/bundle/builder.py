"""ZipBuilder - Structured ZIP bundle creation for procedure releases.

This module provides the ZipBuilder class which creates release bundles
from procedure run directories with support for:
- File exclusion patterns
- SHA-256 checksums for integrity verification
- DEFLATE compression

Example:
    builder = ZipBuilder(run_dir)
    builder.exclude("*.log").exclude("__pycache__/**")
    builder.build(output_path)
    checksums = builder.get_checksums()
"""

from __future__ import annotations

import fnmatch
import hashlib
import zipfile
from pathlib import Path


class ZipBuilder:
    """Creates ZIP bundles from run directories.

    Provides a fluent interface for configuring and building release bundles.

    Attributes:
        run_dir: The source directory to bundle.
    """

    def __init__(self, run_dir: Path) -> None:
        """Initialize ZipBuilder with a run directory.

        Args:
            run_dir: Path to the run directory to bundle.

        Raises:
            FileNotFoundError: If run_dir does not exist.
            ValueError: If run_dir is not a directory.
        """
        if not run_dir.exists():
            raise FileNotFoundError(f"Run directory not found: {run_dir}")
        if not run_dir.is_dir():
            raise ValueError(f"Path is not a directory: {run_dir}")

        self.run_dir = run_dir
        self._exclude_patterns: list[str] = []

    def exclude(self, pattern: str) -> ZipBuilder:
        """Add a glob pattern to exclude from the bundle.

        Args:
            pattern: Glob pattern to exclude (e.g., "*.log", "__pycache__/**").

        Returns:
            Self for method chaining.
        """
        self._exclude_patterns.append(pattern)
        return self

    def _is_excluded(self, relative_path: str) -> bool:
        """Check if a relative path matches any exclude pattern.

        Args:
            relative_path: Path relative to run_dir (using forward slashes).

        Returns:
            True if the path should be excluded.
        """
        for pattern in self._exclude_patterns:
            if fnmatch.fnmatch(relative_path, pattern):
                return True
            # Also check if any parent directory matches for ** patterns
            if "**" in pattern:
                # For patterns like "__pycache__/**", check if path starts with prefix
                prefix = pattern.split("**")[0].rstrip("/")
                if relative_path.startswith(prefix + "/") or relative_path == prefix:
                    return True
        return False

    def list_files(self) -> list[str]:
        """List all files that would be included in the bundle.

        Returns:
            List of relative file paths (using forward slashes).
        """
        files = []
        for path in sorted(self.run_dir.rglob("*")):
            if path.is_dir():
                continue

            relative = path.relative_to(self.run_dir)
            # Use forward slashes for consistency
            relative_str = str(relative).replace("\\", "/")

            if not self._is_excluded(relative_str):
                files.append(relative_str)

        return files

    def get_checksums(self) -> dict[str, str]:
        """Calculate SHA-256 checksums for all included files.

        Returns:
            Dict mapping relative file paths to hex-encoded SHA-256 digests.
        """
        checksums = {}

        for relative_path in self.list_files():
            full_path = self.run_dir / relative_path
            content = full_path.read_bytes()
            digest = hashlib.sha256(content).hexdigest()
            checksums[relative_path] = digest

        return checksums

    def build(self, output_path: Path) -> None:
        """Build the ZIP bundle.

        Args:
            output_path: Where to write the ZIP file.
        """
        # Create parent directories if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Resolve paths for comparison (avoid including output in itself)
        output_resolved = output_path.resolve()

        with zipfile.ZipFile(
            output_path, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as zf:
            for relative_path in self.list_files():
                full_path = self.run_dir / relative_path

                # Skip the output file itself if it's inside run_dir
                if full_path.resolve() == output_resolved:
                    continue

                zf.write(full_path, arcname=relative_path)
