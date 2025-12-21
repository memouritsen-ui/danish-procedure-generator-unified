import requests
import json

BASE_URL = "http://localhost:8000"
TIMEOUT = 30
HEADERS = {"Content-Type": "application/json"}

def test_manage_anthropic_api_key():
    key_endpoint = f"{BASE_URL}/api/keys/anthropic"
    test_api_key = "test-anthropic-api-key-1234567890"

    # Ensure no key at start: delete if exists (ignore errors)
    try:
        requests.delete(key_endpoint, timeout=TIMEOUT)
    except Exception:
        pass

    try:
        # 1) GET key status - expect 404 or no key set (assumption: 404 or 204 or empty)
        resp_get_before = requests.get(key_endpoint, timeout=TIMEOUT)
        assert resp_get_before.status_code in (200, 404, 204), f"Unexpected status {resp_get_before.status_code} on initial GET"
        # If 200, key might be set, we will overwrite it anyway

        # 2) PUT set new key - send JSON payload with api_key
        put_payload = {"api_key": test_api_key}
        resp_put = requests.put(key_endpoint, headers=HEADERS, json=put_payload, timeout=TIMEOUT)
        assert resp_put.status_code == 200, f"Failed to set Anthropic API key, status {resp_put.status_code}"
        put_json = resp_put.json()
        # Validate response does not expose full key - typically a masked or status message expected
        assert "key" not in put_json or (isinstance(put_json.get("key"), str) and put_json.get("key").startswith("***")), "Key exposure detected in PUT response"

        # 3) GET key status again - verify key is reported as set without exposing the actual key
        resp_get_after = requests.get(key_endpoint, timeout=TIMEOUT)
        assert resp_get_after.status_code == 200, f"Failed to get Anthropic key status after setting, status {resp_get_after.status_code}"
        get_json = resp_get_after.json()
        # The key should be present but masked or partially hidden, not the full test_api_key
        assert "key" in get_json, "Key field missing in status response"
        assert isinstance(get_json["key"], str), "Key field should be a string"
        assert test_api_key not in get_json["key"], "Full API key exposed in GET response"

        # 4) DELETE the key - should return success status (204 or 200)
        resp_del = requests.delete(key_endpoint, timeout=TIMEOUT)
        assert resp_del.status_code in (200, 204), f"Failed to delete Anthropic API key, status {resp_del.status_code}"

        # 5) GET key status after deletion - expect 404 or 204 or empty/no key
        resp_get_after_del = requests.get(key_endpoint, timeout=TIMEOUT)
        assert resp_get_after_del.status_code in (404, 204), f"Expected no Anthropic key after deletion, got status {resp_get_after_del.status_code}"

    finally:
        # Cleanup: ensure deletion of key to avoid test pollution
        try:
            requests.delete(key_endpoint, timeout=TIMEOUT)
        except Exception:
            pass

test_manage_anthropic_api_key()
