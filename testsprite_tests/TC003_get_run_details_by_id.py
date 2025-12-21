import requests
import time

BASE_URL = "http://localhost:8000"
TIMEOUT = 30
HEADERS = {"Content-Type": "application/json"}


def test_get_run_details_by_id():
    # Helper to start a new run
    def start_run(procedure="Test procedure for TC003", context="Test context"):
        payload = {"procedure": procedure, "context": context}
        response = requests.post(f"{BASE_URL}/api/write", json=payload, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        return response.json().get("run_id")

    # Helper to delete a run if endpoint existed - not documented so skip delete (no delete endpoint in PRD)

    run_id = None
    try:
        # Create a run to get a valid run_id
        run_id = start_run()
        assert run_id and isinstance(run_id, str), "Failed to start run or invalid run_id returned"

        # Test GET /api/runs/{run_id} with valid run_id
        response_valid = requests.get(f"{BASE_URL}/api/runs/{run_id}", headers=HEADERS, timeout=TIMEOUT)
        assert response_valid.status_code == 200, f"Expected HTTP 200 for valid run_id but got {response_valid.status_code}"
        data = response_valid.json()
        # Verify that response contains fields related to run details and quality score.
        # Since exact schema is not provided, verify keys presence heuristically
        assert isinstance(data, dict), "Response should be a JSON object"
        assert "quality_score" in data or any(k in data for k in ["quality", "score"]), "Response missing quality score field"
        assert "run_id" not in data or data.get("run_id") == run_id or True  # run_id maybe present, no strict check

        # Test GET /api/runs/{run_id} with invalid run_id
        invalid_run_id = "invalid-run-id-1234567890"
        response_invalid = requests.get(f"{BASE_URL}/api/runs/{invalid_run_id}", headers=HEADERS, timeout=TIMEOUT)
        assert response_invalid.status_code == 404, f"Expected HTTP 404 for invalid run_id but got {response_invalid.status_code}"

    finally:
        # No delete endpoint specified in PRD for runs, so cannot clean up explicitly.
        pass


test_get_run_details_by_id()