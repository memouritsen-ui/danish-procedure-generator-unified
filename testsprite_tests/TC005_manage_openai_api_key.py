import requests

BASE_URL = "http://localhost:8000"
TIMEOUT = 30
HEADERS_JSON = {"Content-Type": "application/json"}

def test_manage_openai_api_key():
    key_endpoint = f"{BASE_URL}/api/keys/openai"
    test_api_key = "sk-test-1234567890abcdef"

    # 1. Ensure no key is set or delete existing key to start fresh (ignore errors)
    try:
        resp_delete_init = requests.delete(key_endpoint, timeout=TIMEOUT)
        assert resp_delete_init.status_code in (200, 204, 404)
    except requests.RequestException:
        pass  # Continue anyway

    # 2. GET key status when no key is set - expect 404 or 200
    resp_get_no_key = requests.get(key_endpoint, timeout=TIMEOUT)
    assert resp_get_no_key.status_code in (200, 404)
    if resp_get_no_key.status_code == 200:
        data = resp_get_no_key.json()
        assert isinstance(data, dict)
        if "key" in data:
            assert isinstance(data["key"], str)
            # Key should be empty or masked, not raw
            assert data["key"] == "" or ("*" in data["key"] or data["key"] != test_api_key)

    # 3. PUT to set a new key
    put_payload = {"key": test_api_key}
    resp_put = requests.put(key_endpoint, json=put_payload, headers=HEADERS_JSON, timeout=TIMEOUT)
    assert resp_put.status_code == 200
    resp_put_data = resp_put.json()
    assert isinstance(resp_put_data, dict)

    # 4. GET key status after setting key - expect 200 and masked key
    resp_get_after_put = requests.get(key_endpoint, timeout=TIMEOUT)
    assert resp_get_after_put.status_code == 200
    data_after_put = resp_get_after_put.json()
    assert isinstance(data_after_put, dict)
    if "key" in data_after_put:
        returned_key = data_after_put["key"]
        assert isinstance(returned_key, str)
        assert returned_key != test_api_key
        assert returned_key != ""  # Should not be empty after setting

    # 5. DELETE the key
    resp_delete = requests.delete(key_endpoint, timeout=TIMEOUT)
    assert resp_delete.status_code in (200, 204)

    # 6. Confirm deletion by GET should return 404 or empty or masked key
    resp_get_after_delete = requests.get(key_endpoint, timeout=TIMEOUT)
    assert resp_get_after_delete.status_code in (200, 404)
    if resp_get_after_delete.status_code == 200:
        data_after_del = resp_get_after_delete.json()
        if "key" in data_after_del:
            assert isinstance(data_after_del["key"], str)
            assert data_after_del["key"] == "" or ("*" in data_after_del["key"] or data_after_del["key"] != test_api_key)


test_manage_openai_api_key()
