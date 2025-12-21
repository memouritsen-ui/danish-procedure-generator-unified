from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from procedurewriter.db import RunRow

# Important: Must be at top level before other imports
from procedurewriter.main import app

client = TestClient(app)

@pytest.fixture
def mock_run_with_meta(tmp_path):
    """Fixture to create a mock run directory with both docx files."""
    run_id = "test-run-with-meta"
    run_dir = tmp_path / run_id
    run_dir.mkdir()

    # Create dummy docx files
    procedure_docx_path = run_dir / "Procedure.docx"
    procedure_docx_path.write_text("This is the main procedure.")

    meta_docx_path = run_dir / "Procedure_MetaAnalysis.docx"
    meta_docx_path.write_text("This is the meta-analysis report.")

    # Mock RunRow object that the API will receive from the db
    mock_run = RunRow(
        run_id=run_id,
        created_at_utc="2025-01-01T12:00:00Z",
        updated_at_utc="2025-01-01T12:05:00Z",
        procedure="Test POCUS",
        context="Emergency",
        status="DONE",
        error=None,
        run_dir=str(run_dir),
        manifest_path=str(run_dir / "run_manifest.json"),
        docx_path=str(procedure_docx_path),
        quality_score=9,
        iterations_used=1,
        total_cost_usd=0.1,
        total_input_tokens=1000,
        total_output_tokens=500
    )
    return mock_run

def test_run_detail_endpoint_with_meta_analysis(mock_run_with_meta):
    """
    Test that the /api/runs/{run_id} endpoint correctly identifies
    the presence of a meta-analysis report.
    """
    with patch("procedurewriter.main.get_run") as mock_get_run:
        mock_get_run.return_value = mock_run_with_meta
        
        run_id = mock_run_with_meta.run_id
        response = client.get(f"/api/runs/{run_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == run_id
        assert data["has_meta_analysis_report"] is True

def test_download_meta_analysis_docx(mock_run_with_meta):
    """
    Test the new endpoint for downloading the meta-analysis docx.
    """
    with patch("procedurewriter.main.get_run") as mock_get_run:
        mock_get_run.return_value = mock_run_with_meta
        
        run_id = mock_run_with_meta.run_id
        response = client.get(f"/api/runs/{run_id}/docx/meta-analysis")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert "attachment" in response.headers["content-disposition"]
        assert "Test_POCUS_MetaAnalysis.docx" in response.headers["content-disposition"]
        assert response.text == "This is the meta-analysis report."

def test_download_meta_analysis_docx_not_found():
    """
    Test that the endpoint returns 404 if the meta-analysis docx does not exist.
    """
    # Use the same fixture but remove the meta-analysis file
    run_id = "test-run-no-meta"
    mock_run = MagicMock()
    mock_run.run_id = run_id
    mock_run.run_dir = "/tmp/fake-dir" # Does not matter as get_run is mocked
    
    with patch("procedurewriter.main.get_run") as mock_get_run:
        mock_get_run.return_value = mock_run
        
        # Simulate file not existing by having the endpoint check for it
        # The endpoint logic itself will handle the file check
        
        response = client.get(f"/api/runs/{run_id}/docx/meta-analysis")
        
        assert response.status_code == 404
        assert "Meta-analysis document not found" in response.json()["detail"]

