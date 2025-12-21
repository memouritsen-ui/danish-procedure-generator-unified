import requests


def test_list_all_procedure_generation_runs():
    base_url = "http://localhost:8000"
    endpoint = f"{base_url}/api/runs"
    headers = {
        "Accept": "application/json",
    }
    try:
        response = requests.get(endpoint, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        assert False, f"Request to {endpoint} failed: {e}"

    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    try:
        runs_list = response.json()
    except ValueError:
        assert False, "Response content is not valid JSON"

    # The response should be a list or array-like structure
    assert isinstance(runs_list, list), f"Expected response to be a list, got {type(runs_list)}"


test_list_all_procedure_generation_runs()