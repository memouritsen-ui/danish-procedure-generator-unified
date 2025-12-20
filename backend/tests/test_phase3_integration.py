"""Integration tests for Phase 3: Anatomical Requirements.

Tests the integration of anatomical validation with the pipeline
and other Phase 1-2 components.
"""

from __future__ import annotations

import pytest
from pathlib import Path


class TestAnatomicalValidationWithPipeline:
    """Test integration of anatomical validation with pipeline data."""

    def test_validator_works_with_snippet_classifier(self):
        """AnatomicalValidator should work with classified snippets."""
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalValidator,
        )
        from procedurewriter.pipeline.snippet_classifier import (
            SnippetClassifier,
            SnippetType,
        )

        # Simulate technique snippets that should contain anatomical content
        technique_texts = [
            "Identificer 5. interkostalrum i midtaksillærlinjen.",
            "Indsæt nålen i en vinkel på 45 grader.",
            "Avancér 2-3 cm efter pleuragennembrud.",
        ]

        # Classify to confirm they're technique
        classifier = SnippetClassifier()
        classified = classifier.classify_batch(technique_texts)

        for c in classified:
            assert c.snippet_type == SnippetType.TECHNIQUE

        # Validate anatomical content
        validator = AnatomicalValidator()
        combined_text = " ".join(technique_texts)
        result = validator.validate("pleuradræn", combined_text)

        assert result.is_valid is True
        assert result.has_depth_guidance is True
        assert result.has_angle_guidance is True

    def test_workflow_filter_preserves_anatomical_content(self):
        """WorkflowFilter should preserve anatomical content."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalValidator,
        )

        # Mixed content with both anatomical and workflow
        text = """
        Identificer 5. interkostalrum i midtaksillærlinjen.
        Ring til bagvagt ved komplikationer.
        Triangle of safety markeres.
        Følg lokal retningslinje for sterilteknik.
        Indsæt trokar med 45 graders vinkel.
        Avancér 2-3 cm efter pleuragennembrud.
        """

        # Filter out workflow
        wf = WorkflowFilter()
        clinical, workflow = wf.filter_workflow_content(text)

        # Clinical content should still have anatomical info
        validator = AnatomicalValidator()
        result = validator.validate("pleuradræn", clinical)

        # Anatomical landmarks should be preserved
        assert "5. interkostalrum" not in result.missing_landmarks
        assert result.has_angle_guidance is True
        assert result.has_depth_guidance is True


class TestProcedureTypesConfig:
    """Test procedure_types.yaml configuration."""

    def test_config_file_exists(self):
        """procedure_types.yaml should exist."""
        config_dir = Path(__file__).parent.parent.parent / "config"
        config_path = config_dir / "procedure_types.yaml"

        assert config_path.exists(), f"Config not found at {config_path}"

    def test_config_has_invasive_procedures(self):
        """Config should list invasive procedures."""
        import yaml

        config_dir = Path(__file__).parent.parent.parent / "config"
        config_path = config_dir / "procedure_types.yaml"

        with open(config_path) as f:
            config = yaml.safe_load(f)

        invasive = config.get("invasive_procedures", [])

        assert "pleuradræn" in invasive
        assert "lumbalpunktur" in invasive
        assert len(invasive) >= 5

    def test_config_has_anatomical_requirements(self):
        """Config should have anatomical requirements per procedure."""
        import yaml

        config_dir = Path(__file__).parent.parent.parent / "config"
        config_path = config_dir / "procedure_types.yaml"

        with open(config_path) as f:
            config = yaml.safe_load(f)

        reqs = config.get("anatomical_requirements", {})

        # Should have requirements for key procedures
        assert "pleuradræn" in reqs
        assert "lumbalpunktur" in reqs

        # Check pleuradræn requirements structure
        pleura_reqs = reqs["pleuradræn"]
        assert "landmarks" in pleura_reqs
        assert "requires" in pleura_reqs
        assert len(pleura_reqs["landmarks"]) >= 2


class TestPhase3EndToEnd:
    """End-to-end tests for Phase 3 anatomical validation."""

    def test_full_pipeline_validation(self):
        """Test complete validation of generated procedure content."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter
        from procedurewriter.pipeline.deduplication import RepetitionDetector
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalValidator,
        )

        # Simulate generated procedure content (good quality)
        generated_content = {
            "Fremgangsmåde": [
                "Positionér patienten i lateral decubitus med syg side opad.",
                "Palpér thoraxvæggen og identificer 5. interkostalrum.",
                "Marker punktursted i midtaksillærlinjen.",
                "Identificer triangle of safety.",
                "Desinficér og drapér sterilt.",
                "Infiltrér med lokalbedøvelse.",
                "Indsæt nålen i en vinkel på 45 grader over øvre ribbenrand.",
                "Avancér nålen 2-3 cm til pleurahulen gennembrytes.",
                "Ring til bagvagt ved komplikationer.",
            ],
        }

        # Step 1: Filter workflow
        wf = WorkflowFilter()
        filtered_sections: dict[str, list[str]] = {}
        for section, texts in generated_content.items():
            clinical_texts = []
            for text in texts:
                clinical, _ = wf.filter_workflow_content(text)
                if clinical.strip():
                    clinical_texts.append(clinical)
            filtered_sections[section] = clinical_texts

        # Step 2: Deduplicate
        rd = RepetitionDetector()
        deduped = rd.deduplicate_sections(filtered_sections)

        # Step 3: Validate anatomical content
        validator = AnatomicalValidator()
        combined_text = " ".join(
            " ".join(texts) for texts in deduped.values()
        )
        result = validator.validate("pleuradræn", combined_text)

        # Should pass validation
        assert result.is_valid is True
        assert result.has_depth_guidance is True
        assert result.has_angle_guidance is True
        assert result.completeness_score >= 0.8

    def test_identifies_poor_quality_content(self):
        """Test that validator identifies poor quality content."""
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalValidator,
        )

        # Poor quality content (workflow-heavy, no anatomy)
        poor_content = """
        Følg lokal retningslinje for proceduren.
        Ring til bagvagt ved behov.
        Aftal rollefordeling med teamet.
        Tjek afdelingens protokol.
        Kontakt anæstesi ved sedationsbehov.
        """

        validator = AnatomicalValidator()
        result = validator.validate("pleuradræn", poor_content)

        # Should fail validation
        assert result.is_valid is False
        assert len(result.missing_landmarks) >= 2
        assert len(result.suggestions) >= 1

    def test_suggests_improvements(self):
        """Test that validator suggests specific improvements."""
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalValidator,
        )

        # Partial content (some landmarks, missing others)
        partial_content = """
        Identificer 5. interkostalrum.
        Indsæt dræn.
        """

        validator = AnatomicalValidator()
        result = validator.validate("pleuradræn", partial_content)

        # Should have suggestions
        assert len(result.suggestions) >= 1

        # Should suggest adding depth
        depth_suggestion = any("depth" in s.lower() or "dybde" in s.lower() for s in result.suggestions)
        assert depth_suggestion or result.has_depth_guidance


class TestMultipleProcedures:
    """Test validation across different procedure types."""

    def test_validates_all_registered_procedures(self):
        """All registered procedures should be validatable."""
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalRequirementsRegistry,
            AnatomicalValidator,
        )

        registry = AnatomicalRequirementsRegistry()
        validator = AnatomicalValidator()

        invasive = registry.list_invasive_procedures()

        for procedure_name in invasive:
            reqs = registry.get_requirements(procedure_name)
            assert reqs is not None, f"No requirements for {procedure_name}"

            # Minimal validation should work
            result = validator.validate(procedure_name, "")
            assert result is not None
            assert hasattr(result, "is_valid")

    def test_different_procedures_have_different_requirements(self):
        """Different procedures should have distinct requirements."""
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalRequirementsRegistry,
        )

        registry = AnatomicalRequirementsRegistry()

        pleura = registry.get_requirements("pleuradræn")
        lumbal = registry.get_requirements("lumbalpunktur")

        # Should have different landmarks
        pleura_landmarks = {lm.name for lm in pleura.landmarks}
        lumbal_landmarks = {lm.name for lm in lumbal.landmarks}

        # No overlap in landmarks
        assert pleura_landmarks.isdisjoint(lumbal_landmarks)


class TestValidationScoring:
    """Test validation scoring and completeness."""

    def test_completeness_score_increases_with_content(self):
        """Completeness score should increase as content improves."""
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalValidator,
        )

        validator = AnatomicalValidator()

        # Minimal content
        minimal = "Indsæt dræn."
        minimal_result = validator.validate("pleuradræn", minimal)

        # Better content
        better = """
        Identificer 5. interkostalrum i midtaksillærlinjen.
        Indsæt dræn.
        """
        better_result = validator.validate("pleuradræn", better)

        # Complete content
        complete = """
        Identificer 5. interkostalrum i midtaksillærlinjen.
        Marker triangle of safety.
        Indsæt nålen i 45 graders vinkel.
        Avancér 2-3 cm til pleuragennembrud.
        """
        complete_result = validator.validate("pleuradræn", complete)

        # Scores should increase
        assert better_result.completeness_score > minimal_result.completeness_score
        assert complete_result.completeness_score > better_result.completeness_score


class TestPhase3ModulesImport:
    """Test that all Phase 3 modules can be imported."""

    def test_can_import_anatomical_requirements(self):
        """anatomical_requirements module should be importable."""
        from procedurewriter.pipeline.anatomical_requirements import (
            ProcedureType,
            AnatomicalLandmark,
            ProcedureRequirements,
            ValidationResult,
            AnatomicalRequirementsRegistry,
            AnatomicalValidator,
        )

        assert ProcedureType is not None
        assert AnatomicalLandmark is not None
        assert ProcedureRequirements is not None
        assert ValidationResult is not None
        assert AnatomicalRequirementsRegistry is not None
        assert AnatomicalValidator is not None
