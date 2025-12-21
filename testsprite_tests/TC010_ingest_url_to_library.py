import requests

BASE_URL = "http://localhost:8000"
TIMEOUT = 30

def test_ingest_url_to_library():
    ingest_url_endpoint = f"{BASE_URL}/api/ingest/url"
    test_url = "https://example.com/sample-document"

    headers = {
        "Content-Type": "application/json"
    }

    payload = {
        "url": test_url
    }

    try:
        response = requests.post(ingest_url_endpoint, json=payload, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as e:
        assert False, f"Request failed: {e}"

    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"

    # Validate response content is json and contains expected keys or structure
    try:
        data = response.json()
    except ValueError:
        assert False, "Response is not in JSON format"

    # The PRD does not specify exact response schema for this endpoint,
    # but we can verify it is a non-empty dict indicating success
    assert isinstance(data, dict), "Response JSON is not an object"
    assert data, "Response JSON is empty"

test_ingest_url_to_library()