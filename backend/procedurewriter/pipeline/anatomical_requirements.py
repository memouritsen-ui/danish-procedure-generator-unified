"""Anatomical requirements validation for invasive procedures.

Phase 3: Anatomical Content Requirements
Ensures invasive procedures include required anatomical landmarks,
depth guidance, and surface anatomy information.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Pattern


class ProcedureType(Enum):
    """Classification of procedure types."""

    INVASIVE = "invasive"
    NON_INVASIVE = "non_invasive"


@dataclass(frozen=True)
class AnatomicalLandmark:
    """Represents an anatomical landmark required for a procedure."""

    name: str
    aliases: list[str] = field(default_factory=list)
    category: str = "general"  # thorax, spine, vascular, etc.

    def matches(self, text: str) -> bool:
        """Check if this landmark is mentioned in text."""
        text_lower = text.lower()

        # Check main name
        if self.name.lower() in text_lower:
            return True

        # Check aliases
        for alias in self.aliases:
            if alias.lower() in text_lower:
                return True

        return False


@dataclass
class ProcedureRequirements:
    """Requirements for a specific procedure."""

    procedure_name: str
    procedure_type: str
    landmarks: list[AnatomicalLandmark]
    requires_depth_guidance: bool = False
    requires_surface_anatomy: bool = False
    requires_angle_guidance: bool = False
    requires_verification_step: bool = False


@dataclass
class ValidationResult:
    """Result of validating procedure content against requirements."""

    is_valid: bool
    missing_landmarks: list[str]
    found_landmarks: list[str] = field(default_factory=list)
    has_depth_guidance: bool = False
    has_angle_guidance: bool = False
    has_surface_anatomy: bool = False
    suggestions: list[str] = field(default_factory=list)

    @property
    def completeness_score(self) -> float:
        """Calculate completeness score from 0.0 to 1.0."""
        if self.is_valid:
            base_score = 0.6

            # Bonus for additional elements
            if self.has_depth_guidance:
                base_score += 0.15
            if self.has_angle_guidance:
                base_score += 0.1
            if self.has_surface_anatomy:
                base_score += 0.15

            return min(1.0, base_score)

        # Partial score based on found landmarks
        total = len(self.missing_landmarks) + len(self.found_landmarks)
        if total == 0:
            return 0.0

        found_ratio = len(self.found_landmarks) / total
        return found_ratio * 0.5  # Max 0.5 if not valid


# Depth guidance patterns
DEPTH_PATTERNS: list[Pattern[str]] = [
    re.compile(r"\d+[-–]\d+\s*cm", re.I),  # 2-3 cm
    re.compile(r"\d+\s*cm", re.I),  # 5 cm
    re.compile(r"\d+[-–]\d+\s*mm", re.I),  # 10-15 mm
    re.compile(r"dybde", re.I),  # dybde
    re.compile(r"avancér\s+.*\d+", re.I),  # avancér ... [number]
]

# Angle guidance patterns
ANGLE_PATTERNS: list[Pattern[str]] = [
    re.compile(r"\d+\s*grader?", re.I),  # 45 grader
    re.compile(r"\d+\s*°", re.I),  # 45°
    re.compile(r"vinkel", re.I),  # vinkel
    re.compile(r"kranial\s*vinkel", re.I),  # kranial vinkel
    re.compile(r"kaudal\s*vinkel", re.I),  # kaudal vinkel
]

# Surface anatomy patterns
SURFACE_ANATOMY_PATTERNS: list[Pattern[str]] = [
    re.compile(r"palpér", re.I),
    re.compile(r"overflade", re.I),
    re.compile(r"hudmarkering", re.I),
    re.compile(r"midtlinje", re.I),
    re.compile(r"lateral", re.I),
    re.compile(r"medial", re.I),
]


# Built-in procedure requirements
PROCEDURE_REQUIREMENTS: dict[str, ProcedureRequirements] = {
    "pleuradræn": ProcedureRequirements(
        procedure_name="pleuradræn",
        procedure_type="invasive",
        landmarks=[
            AnatomicalLandmark(
                name="5. interkostalrum",
                aliases=[
                    "femte interkostalrum",
                    "5th intercostal space",
                    "5. ICR",
                    "ICS 5",
                ],
                category="thorax",
            ),
            AnatomicalLandmark(
                name="midtaksillærlinjen",
                aliases=[
                    "midaxillærlinjen",
                    "mid-axillary line",
                    "MAL",
                    "midtaksillær",
                ],
                category="thorax",
            ),
            AnatomicalLandmark(
                name="triangle of safety",
                aliases=[
                    "safety triangle",
                    "sikkerhedstriangel",
                    "det sikre område",
                ],
                category="thorax",
            ),
        ],
        requires_depth_guidance=True,
        requires_surface_anatomy=True,
        requires_angle_guidance=True,
    ),
    "lumbalpunktur": ProcedureRequirements(
        procedure_name="lumbalpunktur",
        procedure_type="invasive",
        landmarks=[
            AnatomicalLandmark(
                name="L3-L4",
                aliases=[
                    "L3/L4",
                    "L3-4",
                    "tredje-fjerde lumbale",
                    "intervertebralrum L3-L4",
                ],
                category="spine",
            ),
            AnatomicalLandmark(
                name="L4-L5",
                aliases=[
                    "L4/L5",
                    "L4-5",
                    "fjerde-femte lumbale",
                    "intervertebralrum L4-L5",
                ],
                category="spine",
            ),
            AnatomicalLandmark(
                name="crista iliaca",
                aliases=[
                    "hoftekammen",
                    "iliac crest",
                    "cristae iliacae",
                    "L4 niveau",
                ],
                category="spine",
            ),
            AnatomicalLandmark(
                name="processus spinosus",
                aliases=[
                    "spinous process",
                    "torntappen",
                    "proc. spinosus",
                ],
                category="spine",
            ),
        ],
        requires_depth_guidance=True,
        requires_surface_anatomy=True,
        requires_angle_guidance=True,
    ),
    "central_venous_access": ProcedureRequirements(
        procedure_name="central_venous_access",
        procedure_type="invasive",
        landmarks=[
            AnatomicalLandmark(
                name="v. jugularis interna",
                aliases=[
                    "vena jugularis interna",
                    "internal jugular vein",
                    "IJV",
                    "jugularis",
                ],
                category="vascular",
            ),
            AnatomicalLandmark(
                name="a. carotis",
                aliases=[
                    "arteria carotis",
                    "carotid artery",
                    "carotis communis",
                ],
                category="vascular",
            ),
            AnatomicalLandmark(
                name="m. sternocleidomastoideus",
                aliases=[
                    "SCM",
                    "sternocleidomastoid",
                    "kopnikker",
                ],
                category="vascular",
            ),
        ],
        requires_depth_guidance=True,
        requires_surface_anatomy=True,
        requires_angle_guidance=True,
        requires_verification_step=True,
    ),
    "arteriel_kanyle": ProcedureRequirements(
        procedure_name="arteriel_kanyle",
        procedure_type="invasive",
        landmarks=[
            AnatomicalLandmark(
                name="a. radialis",
                aliases=[
                    "arteria radialis",
                    "radial artery",
                    "radialarterien",
                ],
                category="vascular",
            ),
            AnatomicalLandmark(
                name="processus styloideus radii",
                aliases=[
                    "styloid process",
                    "radiusstyloid",
                ],
                category="vascular",
            ),
        ],
        requires_depth_guidance=False,
        requires_surface_anatomy=True,
        requires_angle_guidance=True,
    ),
    "pericardiocentese": ProcedureRequirements(
        procedure_name="pericardiocentese",
        procedure_type="invasive",
        landmarks=[
            AnatomicalLandmark(
                name="processus xiphoideus",
                aliases=[
                    "xiphoid process",
                    "sværdtappen",
                    "xiphoid",
                ],
                category="thorax",
            ),
            AnatomicalLandmark(
                name="venstre costalbue",
                aliases=[
                    "left costal margin",
                    "venstre ribbensrand",
                ],
                category="thorax",
            ),
        ],
        requires_depth_guidance=True,
        requires_surface_anatomy=True,
        requires_angle_guidance=True,
        requires_verification_step=True,
    ),
}


class AnatomicalRequirementsRegistry:
    """Registry for procedure anatomical requirements."""

    def __init__(self) -> None:
        self._requirements = PROCEDURE_REQUIREMENTS.copy()

    def get_requirements(self, procedure_name: str) -> ProcedureRequirements | None:
        """Get requirements for a procedure by name.

        Args:
            procedure_name: Name of the procedure (e.g., "pleuradræn")

        Returns:
            ProcedureRequirements or None if not found
        """
        # Normalize name
        normalized = procedure_name.lower().strip()

        # Direct match
        if normalized in self._requirements:
            return self._requirements[normalized]

        # Try partial matching
        for name, reqs in self._requirements.items():
            if normalized in name or name in normalized:
                return reqs

        return None

    def list_invasive_procedures(self) -> list[str]:
        """List all registered invasive procedures.

        Returns:
            List of procedure names
        """
        return [
            name
            for name, reqs in self._requirements.items()
            if reqs.procedure_type == "invasive"
        ]

    def register_procedure(self, requirements: ProcedureRequirements) -> None:
        """Register a new procedure's requirements.

        Args:
            requirements: The procedure requirements to register
        """
        self._requirements[requirements.procedure_name.lower()] = requirements


class AnatomicalValidator:
    """Validates procedure content against anatomical requirements."""

    def __init__(self) -> None:
        self._registry = AnatomicalRequirementsRegistry()

    def validate(self, procedure_name: str, content: str) -> ValidationResult:
        """Validate content against procedure requirements.

        Args:
            procedure_name: Name of the procedure
            content: Text content to validate

        Returns:
            ValidationResult with validation details
        """
        requirements = self._registry.get_requirements(procedure_name)

        if requirements is None:
            # Unknown procedure - assume valid with no requirements
            return ValidationResult(
                is_valid=True,
                missing_landmarks=[],
                found_landmarks=[],
                has_depth_guidance=self._has_depth_guidance(content),
                has_angle_guidance=self._has_angle_guidance(content),
                has_surface_anatomy=self._has_surface_anatomy(content),
            )

        # Check landmarks
        found_landmarks: list[str] = []
        missing_landmarks: list[str] = []

        for landmark in requirements.landmarks:
            if landmark.matches(content):
                found_landmarks.append(landmark.name)
            else:
                missing_landmarks.append(landmark.name)

        # Check other requirements
        has_depth = self._has_depth_guidance(content)
        has_angle = self._has_angle_guidance(content)
        has_surface = self._has_surface_anatomy(content)

        # Determine validity
        # For procedures with multiple landmarks (like L3-L4 OR L4-L5),
        # we need at least some landmarks
        if procedure_name.lower() == "lumbalpunktur":
            # Need at least one vertebral level and crista iliaca
            has_vertebral = any(
                lm in found_landmarks for lm in ["L3-L4", "L4-L5"]
            )
            has_crista = "crista iliaca" in found_landmarks
            is_valid = has_vertebral and has_crista
        else:
            # For other procedures, need majority of landmarks
            required_count = len(requirements.landmarks)
            found_count = len(found_landmarks)
            is_valid = found_count >= (required_count * 0.5)

        # Generate suggestions
        suggestions = self._generate_suggestions(
            requirements, missing_landmarks, has_depth, has_angle, has_surface
        )

        return ValidationResult(
            is_valid=is_valid,
            missing_landmarks=missing_landmarks,
            found_landmarks=found_landmarks,
            has_depth_guidance=has_depth,
            has_angle_guidance=has_angle,
            has_surface_anatomy=has_surface,
            suggestions=suggestions,
        )

    def _has_depth_guidance(self, content: str) -> bool:
        """Check if content contains depth guidance."""
        for pattern in DEPTH_PATTERNS:
            if pattern.search(content):
                return True
        return False

    def _has_angle_guidance(self, content: str) -> bool:
        """Check if content contains angle guidance."""
        for pattern in ANGLE_PATTERNS:
            if pattern.search(content):
                return True
        return False

    def _has_surface_anatomy(self, content: str) -> bool:
        """Check if content contains surface anatomy references."""
        for pattern in SURFACE_ANATOMY_PATTERNS:
            if pattern.search(content):
                return True
        return False

    def _generate_suggestions(
        self,
        requirements: ProcedureRequirements,
        missing_landmarks: list[str],
        has_depth: bool,
        has_angle: bool,
        has_surface: bool,
    ) -> list[str]:
        """Generate improvement suggestions."""
        suggestions = []

        if missing_landmarks:
            suggestions.append(
                f"Add anatomical landmarks: {', '.join(missing_landmarks)}"
            )

        if requirements.requires_depth_guidance and not has_depth:
            suggestions.append(
                "Add depth guidance (e.g., 'avancér 2-3 cm')"
            )

        if requirements.requires_angle_guidance and not has_angle:
            suggestions.append(
                "Add angle guidance (e.g., 'i en vinkel på 45 grader')"
            )

        if requirements.requires_surface_anatomy and not has_surface:
            suggestions.append(
                "Add surface anatomy references (palpation, landmarks)"
            )

        return suggestions
