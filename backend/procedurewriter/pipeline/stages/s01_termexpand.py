"""Stage 01: TermExpand - Expand Danish medical terms.

The TermExpand stage transforms Danish procedure titles into:
1. English translation/equivalents
2. MeSH (Medical Subject Headings) terms
3. Synonyms and related terms
4. Common abbreviations

This provides structured search terms for the Retrieve stage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from procedurewriter.pipeline.events import EventType
from procedurewriter.pipeline.stages.base import PipelineStage

if TYPE_CHECKING:
    from procedurewriter.pipeline.events import EventEmitter


# Static mapping of Danish medical terms to English equivalents and MeSH terms
# This covers common emergency medicine procedures
DANISH_TO_ENGLISH: dict[str, dict[str, Any]] = {
    "anafylaksi": {
        "english": ["anaphylaxis", "anaphylactic reaction", "anaphylactic shock"],
        "mesh": ["Anaphylaxis", "Hypersensitivity, Immediate"],
    },
    "behandling": {
        "english": ["treatment", "management", "therapy"],
        "mesh": ["Therapeutics"],
    },
    "pneumoni": {
        "english": ["pneumonia", "lung infection"],
        "mesh": ["Pneumonia", "Community-Acquired Infections"],
    },
    "akut": {
        "english": ["acute", "emergency", "urgent"],
        "mesh": ["Acute Disease", "Emergencies"],
    },
    "astma": {
        "english": ["asthma", "bronchial asthma"],
        "mesh": ["Asthma", "Status Asthmaticus"],
    },
    "thoraxdræn": {
        "english": ["chest drain", "chest tube", "thoracostomy", "tube thoracostomy"],
        "mesh": ["Chest Tubes", "Thoracostomy"],
    },
    "hjertestop": {
        "english": ["cardiac arrest", "heart arrest", "cardiopulmonary arrest"],
        "mesh": ["Heart Arrest", "Cardiopulmonary Resuscitation"],
    },
    "sepsis": {
        "english": ["sepsis", "septicemia", "systemic infection"],
        "mesh": ["Sepsis", "Systemic Inflammatory Response Syndrome"],
    },
    "blødning": {
        "english": ["bleeding", "hemorrhage", "haemorrhage"],
        "mesh": ["Hemorrhage"],
    },
    "shock": {
        "english": ["shock", "circulatory shock"],
        "mesh": ["Shock", "Shock, Cardiogenic", "Shock, Hypovolemic"],
    },
    "forgiftning": {
        "english": ["poisoning", "intoxication", "toxicity"],
        "mesh": ["Poisoning", "Drug Overdose"],
    },
    "fraktur": {
        "english": ["fracture", "bone fracture", "broken bone"],
        "mesh": ["Fractures, Bone"],
    },
    "forbrænding": {
        "english": ["burn", "thermal injury", "burn injury"],
        "mesh": ["Burns"],
    },
    "meningitis": {
        "english": ["meningitis", "meningeal infection"],
        "mesh": ["Meningitis", "Meningitis, Bacterial"],
    },
    "stroke": {
        "english": ["stroke", "cerebrovascular accident", "CVA"],
        "mesh": ["Stroke", "Brain Ischemia"],
    },
    "apopleksi": {
        "english": ["stroke", "apoplexy", "cerebrovascular accident"],
        "mesh": ["Stroke", "Cerebral Hemorrhage"],
    },
    "myokardieinfarkt": {
        "english": ["myocardial infarction", "heart attack", "MI", "STEMI"],
        "mesh": ["Myocardial Infarction", "ST Elevation Myocardial Infarction"],
    },
    "ami": {
        "english": ["acute myocardial infarction", "heart attack", "AMI"],
        "mesh": ["Myocardial Infarction"],
    },
    "lungeemboli": {
        "english": ["pulmonary embolism", "PE", "lung clot"],
        "mesh": ["Pulmonary Embolism"],
    },
    "dyb venetrombose": {
        "english": ["deep vein thrombosis", "DVT", "venous thrombosis"],
        "mesh": ["Venous Thrombosis"],
    },
    "hyperglykæmi": {
        "english": ["hyperglycemia", "high blood sugar", "diabetic emergency"],
        "mesh": ["Hyperglycemia"],
    },
    "hypoglykæmi": {
        "english": ["hypoglycemia", "low blood sugar", "insulin shock"],
        "mesh": ["Hypoglycemia"],
    },
    "kramper": {
        "english": ["seizures", "convulsions", "epileptic seizure"],
        "mesh": ["Seizures", "Epilepsy"],
    },
    "status epilepticus": {
        "english": ["status epilepticus", "prolonged seizure"],
        "mesh": ["Status Epilepticus"],
    },
    "allergisk reaktion": {
        "english": ["allergic reaction", "hypersensitivity reaction"],
        "mesh": ["Hypersensitivity"],
    },
    "luftvejsobstruktion": {
        "english": ["airway obstruction", "choking", "airway blockage"],
        "mesh": ["Airway Obstruction"],
    },
    "respiratorisk insufficiens": {
        "english": ["respiratory failure", "respiratory insufficiency"],
        "mesh": ["Respiratory Insufficiency"],
    },
}


def _normalize_term(term: str) -> str:
    """Normalize a term for matching."""
    return term.lower().strip()


def _extract_danish_words(procedure_title: str) -> list[str]:
    """Extract individual words and known compound terms from procedure title."""
    normalized = _normalize_term(procedure_title)
    words = []

    # First check for known compound terms (multi-word)
    for danish_term in sorted(DANISH_TO_ENGLISH.keys(), key=len, reverse=True):
        if danish_term in normalized:
            words.append(danish_term)
            # Remove found term to avoid duplication
            normalized = normalized.replace(danish_term, " ")

    # Then extract remaining single words
    for word in normalized.split():
        cleaned = word.strip()
        if cleaned and len(cleaned) > 2:  # Skip very short words
            words.append(cleaned)

    return words


@dataclass
class TermExpandInput:
    """Input for the TermExpand stage."""

    run_id: str
    run_dir: Path
    procedure_title: str
    emitter: EventEmitter | None = None


@dataclass
class TermExpandOutput:
    """Output from the TermExpand stage."""

    run_id: str
    run_dir: Path
    procedure_title: str
    danish_terms: list[str]
    english_terms: list[str]
    mesh_terms: list[str]
    all_search_terms: list[str]


class TermExpandStage(PipelineStage[TermExpandInput, TermExpandOutput]):
    """Stage 01: TermExpand - Expand Danish medical terms to English."""

    @property
    def name(self) -> str:
        """Return the stage name."""
        return "termexpand"

    def execute(self, input_data: TermExpandInput) -> TermExpandOutput:
        """Execute the term expansion stage.

        Transforms Danish procedure title into structured search terms
        including English translations and MeSH terms.

        Args:
            input_data: TermExpand input containing procedure_title

        Returns:
            TermExpand output with expanded search terms

        Raises:
            ValueError: If procedure_title is empty (R4-004)
        """
        # R4-004: Validate input - empty procedure_title not allowed
        if not input_data.procedure_title or not input_data.procedure_title.strip():
            raise ValueError(
                "procedure_title is required and cannot be empty. "
                "Cannot expand terms without a procedure name."
            )

        # Emit progress event if emitter provided
        if input_data.emitter is not None:
            input_data.emitter.emit(
                EventType.PROGRESS,
                {"message": "Expanding search terms", "stage": "termexpand"},
            )

        # Start with original Danish terms
        danish_terms: list[str] = [input_data.procedure_title.strip()]
        english_terms: list[str] = []
        mesh_terms: list[str] = []

        # Extract words from procedure title
        words = _extract_danish_words(input_data.procedure_title)

        # Look up each word in the mapping
        for word in words:
            if word in DANISH_TO_ENGLISH:
                mapping = DANISH_TO_ENGLISH[word]
                english_terms.extend(mapping.get("english", []))
                mesh_terms.extend(mapping.get("mesh", []))

        # Deduplicate while preserving order
        english_terms = list(dict.fromkeys(english_terms))
        mesh_terms = list(dict.fromkeys(mesh_terms))

        # Build combined search terms list
        all_search_terms = danish_terms.copy()
        all_search_terms.extend(english_terms)

        # Add common search patterns for medical literature
        if english_terms:
            # Add guideline-focused terms
            for eng in english_terms[:2]:  # Use top 2 English terms
                all_search_terms.append(f"{eng} guidelines")
                all_search_terms.append(f"{eng} treatment")

        # Add MeSH terms for precise searching
        all_search_terms.extend(mesh_terms)

        # Deduplicate final list
        all_search_terms = list(dict.fromkeys(all_search_terms))

        return TermExpandOutput(
            run_id=input_data.run_id,
            run_dir=input_data.run_dir,
            procedure_title=input_data.procedure_title,
            danish_terms=danish_terms,
            english_terms=english_terms,
            mesh_terms=mesh_terms,
            all_search_terms=all_search_terms,
        )
