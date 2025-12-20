"""Tests for snippet classification.

TDD Phase 1: Source Diversification - Content Type Classification
"""

from __future__ import annotations

import pytest


class TestSnippetTypeEnum:
    """Test SnippetType enum for content classification."""

    def test_snippet_type_has_technique(self):
        """SnippetType should have TECHNIQUE value."""
        from procedurewriter.pipeline.snippet_classifier import SnippetType

        assert SnippetType.TECHNIQUE.value == "technique"

    def test_snippet_type_has_workflow(self):
        """SnippetType should have WORKFLOW value."""
        from procedurewriter.pipeline.snippet_classifier import SnippetType

        assert SnippetType.WORKFLOW.value == "workflow"

    def test_snippet_type_has_evidence(self):
        """SnippetType should have EVIDENCE value."""
        from procedurewriter.pipeline.snippet_classifier import SnippetType

        assert SnippetType.EVIDENCE.value == "evidence"

    def test_snippet_type_has_safety(self):
        """SnippetType should have SAFETY value."""
        from procedurewriter.pipeline.snippet_classifier import SnippetType

        assert SnippetType.SAFETY.value == "safety"

    def test_snippet_type_has_equipment(self):
        """SnippetType should have EQUIPMENT value."""
        from procedurewriter.pipeline.snippet_classifier import SnippetType

        assert SnippetType.EQUIPMENT.value == "equipment"

    def test_snippet_type_has_local_protocol(self):
        """SnippetType should have LOCAL_PROTOCOL value."""
        from procedurewriter.pipeline.snippet_classifier import SnippetType

        assert SnippetType.LOCAL_PROTOCOL.value == "local_protocol"


class TestClassifiedSnippet:
    """Test ClassifiedSnippet dataclass."""

    def test_classified_snippet_has_required_fields(self):
        """ClassifiedSnippet should have text, snippet_type, and confidence."""
        from procedurewriter.pipeline.snippet_classifier import (
            ClassifiedSnippet,
            SnippetType,
        )

        snippet = ClassifiedSnippet(
            text="Insert the needle at a 45 degree angle",
            snippet_type=SnippetType.TECHNIQUE,
            confidence=0.95,
        )

        assert snippet.text == "Insert the needle at a 45 degree angle"
        assert snippet.snippet_type == SnippetType.TECHNIQUE
        assert snippet.confidence == 0.95

    def test_classified_snippet_has_optional_source_id(self):
        """ClassifiedSnippet should support optional source_id."""
        from procedurewriter.pipeline.snippet_classifier import (
            ClassifiedSnippet,
            SnippetType,
        )

        snippet = ClassifiedSnippet(
            text="Call anesthesia if airway compromised",
            snippet_type=SnippetType.WORKFLOW,
            confidence=0.88,
            source_id="SRC0001",
        )

        assert snippet.source_id == "SRC0001"


class TestSnippetClassifier:
    """Test SnippetClassifier for content classification."""

    def test_classifier_can_be_instantiated(self):
        """SnippetClassifier should be instantiable."""
        from procedurewriter.pipeline.snippet_classifier import SnippetClassifier

        classifier = SnippetClassifier()
        assert classifier is not None

    def test_classifier_has_classify_method(self):
        """SnippetClassifier should have classify method."""
        from procedurewriter.pipeline.snippet_classifier import SnippetClassifier

        classifier = SnippetClassifier()
        assert hasattr(classifier, "classify")
        assert callable(classifier.classify)

    def test_classifier_returns_classified_snippet(self):
        """classify() should return ClassifiedSnippet."""
        from procedurewriter.pipeline.snippet_classifier import (
            SnippetClassifier,
            ClassifiedSnippet,
        )

        classifier = SnippetClassifier()
        result = classifier.classify("Insert needle at 45 degrees")

        assert isinstance(result, ClassifiedSnippet)


class TestTechniqueClassification:
    """Test classification of technique-type content."""

    def test_classifies_anatomical_content_as_technique(self):
        """Anatomical landmarks should be classified as TECHNIQUE."""
        from procedurewriter.pipeline.snippet_classifier import (
            SnippetClassifier,
            SnippetType,
        )

        classifier = SnippetClassifier()
        text = "Identificer 5. interkostalrum i midtaksillærlinjen"
        result = classifier.classify(text)

        assert result.snippet_type == SnippetType.TECHNIQUE

    def test_classifies_procedural_steps_as_technique(self):
        """Procedural steps with technique details should be TECHNIQUE."""
        from procedurewriter.pipeline.snippet_classifier import (
            SnippetClassifier,
            SnippetType,
        )

        classifier = SnippetClassifier()
        text = "Indsæt nålen i en vinkel på 45 grader til hudoverfladen"
        result = classifier.classify(text)

        assert result.snippet_type == SnippetType.TECHNIQUE

    def test_classifies_depth_guidance_as_technique(self):
        """Depth guidance should be classified as TECHNIQUE."""
        from procedurewriter.pipeline.snippet_classifier import (
            SnippetClassifier,
            SnippetType,
        )

        classifier = SnippetClassifier()
        text = "Avancér nålen 2-3 cm indtil der aspireres luft eller væske"
        result = classifier.classify(text)

        assert result.snippet_type == SnippetType.TECHNIQUE


class TestWorkflowClassification:
    """Test classification of workflow-type content."""

    def test_classifies_call_instructions_as_workflow(self):
        """Instructions to call someone should be WORKFLOW."""
        from procedurewriter.pipeline.snippet_classifier import (
            SnippetClassifier,
            SnippetType,
        )

        classifier = SnippetClassifier()
        text = "Ring til bagvagt ved komplikationer"
        result = classifier.classify(text)

        assert result.snippet_type == SnippetType.WORKFLOW

    def test_classifies_phone_numbers_as_workflow(self):
        """Phone numbers should be WORKFLOW."""
        from procedurewriter.pipeline.snippet_classifier import (
            SnippetClassifier,
            SnippetType,
        )

        classifier = SnippetClassifier()
        text = "Kontakt anæstesi på tlf. 12345"
        result = classifier.classify(text)

        assert result.snippet_type == SnippetType.WORKFLOW

    def test_classifies_role_delegation_as_workflow(self):
        """Role delegation should be WORKFLOW."""
        from procedurewriter.pipeline.snippet_classifier import (
            SnippetClassifier,
            SnippetType,
        )

        classifier = SnippetClassifier()
        text = "Aftal rollefordeling: én leder ABCDE, én klargør udstyr"
        result = classifier.classify(text)

        assert result.snippet_type == SnippetType.WORKFLOW

    def test_classifies_local_protocol_reference_as_workflow(self):
        """References to local protocol should be WORKFLOW."""
        from procedurewriter.pipeline.snippet_classifier import (
            SnippetClassifier,
            SnippetType,
        )

        classifier = SnippetClassifier()
        text = "Følg lokal retningslinje for dosering"
        result = classifier.classify(text)

        assert result.snippet_type == SnippetType.WORKFLOW


class TestSafetyClassification:
    """Test classification of safety-type content."""

    def test_classifies_complications_as_safety(self):
        """Complications should be SAFETY."""
        from procedurewriter.pipeline.snippet_classifier import (
            SnippetClassifier,
            SnippetType,
        )

        classifier = SnippetClassifier()
        text = "Komplikationer omfatter pneumothorax, blødning og infektion"
        result = classifier.classify(text)

        assert result.snippet_type == SnippetType.SAFETY

    def test_classifies_warnings_as_safety(self):
        """Warnings and cautions should be SAFETY."""
        from procedurewriter.pipeline.snippet_classifier import (
            SnippetClassifier,
            SnippetType,
        )

        classifier = SnippetClassifier()
        text = "ADVARSEL: Undgå at punktere a. intercostalis"
        result = classifier.classify(text)

        assert result.snippet_type == SnippetType.SAFETY

    def test_classifies_contraindications_as_safety(self):
        """Contraindications should be SAFETY."""
        from procedurewriter.pipeline.snippet_classifier import (
            SnippetClassifier,
            SnippetType,
        )

        classifier = SnippetClassifier()
        text = "Kontraindikationer: koagulopati, infektion over punktursted"
        result = classifier.classify(text)

        assert result.snippet_type == SnippetType.SAFETY


class TestEquipmentClassification:
    """Test classification of equipment-type content."""

    def test_classifies_equipment_list_as_equipment(self):
        """Equipment lists should be EQUIPMENT."""
        from procedurewriter.pipeline.snippet_classifier import (
            SnippetClassifier,
            SnippetType,
        )

        classifier = SnippetClassifier()
        text = "Udstyr: Sterile handsker, steriliseringskit, pleuradrænkateter"
        result = classifier.classify(text)

        assert result.snippet_type == SnippetType.EQUIPMENT

    def test_classifies_needle_sizes_as_equipment(self):
        """Needle sizes should be EQUIPMENT."""
        from procedurewriter.pipeline.snippet_classifier import (
            SnippetClassifier,
            SnippetType,
        )

        classifier = SnippetClassifier()
        text = "Brug 18G eller 16G kanyle afhængigt af indikation"
        result = classifier.classify(text)

        assert result.snippet_type == SnippetType.EQUIPMENT


class TestEvidenceClassification:
    """Test classification of evidence-type content."""

    def test_classifies_study_references_as_evidence(self):
        """Study references should be EVIDENCE."""
        from procedurewriter.pipeline.snippet_classifier import (
            SnippetClassifier,
            SnippetType,
        )

        classifier = SnippetClassifier()
        text = "Et randomiseret studie af Hansen et al. (2023) viste..."
        result = classifier.classify(text)

        assert result.snippet_type == SnippetType.EVIDENCE

    def test_classifies_guidelines_references_as_evidence(self):
        """Guideline references should be EVIDENCE."""
        from procedurewriter.pipeline.snippet_classifier import (
            SnippetClassifier,
            SnippetType,
        )

        classifier = SnippetClassifier()
        text = "Ifølge British Thoracic Society guidelines anbefales..."
        result = classifier.classify(text)

        assert result.snippet_type == SnippetType.EVIDENCE


class TestBatchClassification:
    """Test batch classification of multiple snippets."""

    def test_classifier_has_classify_batch_method(self):
        """SnippetClassifier should have classify_batch method."""
        from procedurewriter.pipeline.snippet_classifier import SnippetClassifier

        classifier = SnippetClassifier()
        assert hasattr(classifier, "classify_batch")
        assert callable(classifier.classify_batch)

    def test_classify_batch_returns_list(self):
        """classify_batch should return list of ClassifiedSnippet."""
        from procedurewriter.pipeline.snippet_classifier import (
            SnippetClassifier,
            ClassifiedSnippet,
        )

        classifier = SnippetClassifier()
        texts = [
            "Insert needle at 45 degrees",
            "Ring til bagvagt ved behov",
        ]
        results = classifier.classify_batch(texts)

        assert isinstance(results, list)
        assert len(results) == 2
        for result in results:
            assert isinstance(result, ClassifiedSnippet)
