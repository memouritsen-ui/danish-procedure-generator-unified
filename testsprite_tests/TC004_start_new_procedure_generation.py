import requests

BASE_URL = "http://localhost:8000"
TIMEOUT = 30
HEADERS = {"Content-Type": "application/json"}


def test_start_new_procedure_generation():
    url = f"{BASE_URL}/api/write"
    payload = {
        "procedure": "Acute myocardial infarction treatment",
        "context": "Include recent guidelines and common emergency measures"
    }

    try:
        response = requests.post(url, json=payload, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        assert response.status_code == 200, f"Unexpected status code: {response.status_code}"
        data = response.json()
        assert isinstance(data, dict), "Response is not a JSON object"
        assert "run_id" in data, "Response JSON does not contain 'run_id'"
        assert isinstance(data["run_id"], str) and data["run_id"], "'run_id' is not a non-empty string"
    except requests.RequestException as e:
        assert False, f"Request failed: {e}"


test_start_new_procedure_generation()