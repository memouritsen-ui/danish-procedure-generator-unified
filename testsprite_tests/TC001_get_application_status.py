import requests

def test_get_application_status():
    base_url = "http://localhost:8000"
    url = f"{base_url}/api/status"
    headers = {
        "Accept": "application/json"
    }
    timeout = 30

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        assert False, f"Request to {url} failed: {e}"

    # Validate HTTP status code
    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"

    try:
        data = response.json()
    except ValueError:
        assert False, "Response is not valid JSON"

    # Validate JSON schema keys and types
    expected_keys = {
        "version": str,
        "dummy_mode": bool,
        "use_llm": bool,
        "llm_provider": str,
        "llm_model": str
    }

    for key, expected_type in expected_keys.items():
        assert key in data, f"Response JSON missing key: {key}"
        assert isinstance(data[key], expected_type), f"Key '{key}' expected type {expected_type.__name__}, got {type(data[key]).__name__}"

test_get_application_status()