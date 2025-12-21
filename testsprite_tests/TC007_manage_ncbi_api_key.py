import requests

BASE_URL = "http://localhost:8000"
TIMEOUT = 30
HEADERS = {
    "Content-Type": "application/json"
}

def test_manage_ncbi_api_key():
    key_endpoint = f"{BASE_URL}/api/keys/ncbi"
    test_api_key = "test_ncbi_api_key_1234567890"

    # Ensure any existing key is deleted before starting test
    try:
        del_resp = requests.delete(key_endpoint, timeout=TIMEOUT)
        assert del_resp.status_code in (200, 204, 404), f"Unexpected status when deleting existing key: {del_resp.status_code}"
    except requests.RequestException as e:
        raise AssertionError(f"Failed to delete existing key before test: {e}")

    # 1. GET key status before setting (should indicate no key)
    try:
        get_resp = requests.get(key_endpoint, timeout=TIMEOUT)
        assert get_resp.status_code in (200, 404), f"GET key status failed with status {get_resp.status_code}"
        if get_resp.status_code == 200:
            get_data = get_resp.json()
            # Expect the response to indicate no key is set (e.g. key status or a flag, assume key is null/empty or masked)
            assert "key" in get_data or "status" in get_data, "Response missing expected key status fields"
            # If key is present, it should reflect absence (e.g. null, "", or masked)
    except requests.RequestException as e:
        raise AssertionError(f"Failed to get key status: {e}")
    except ValueError:
        raise AssertionError("GET response is not valid JSON")

    # 2. PUT to set a new NCBI API key
    payload = {"key": test_api_key}
    try:
        put_resp = requests.put(key_endpoint, json=payload, headers=HEADERS, timeout=TIMEOUT)
        assert put_resp.status_code == 200, f"PUT set key failed with status {put_resp.status_code}"
        put_data = put_resp.json()
        # Validate response indicates success and does not expose the actual key
        assert "key" in put_data or "status" in put_data or "message" in put_data, "PUT response missing expected confirmation"
        if "key" in put_data:
            # The key should be masked or not the raw key
            assert put_data["key"] != test_api_key, "API key exposed in PUT response"
    except requests.RequestException as e:
        raise AssertionError(f"Failed to set API key: {e}")
    except ValueError:
        raise AssertionError("PUT response is not valid JSON")

    # 3. GET key status after setting to verify it is set
    try:
        get_resp2 = requests.get(key_endpoint, timeout=TIMEOUT)
        assert get_resp2.status_code == 200, f"GET key status after set failed with status {get_resp2.status_code}"
        get_data2 = get_resp2.json()
        # Validate key presence and masked, not exposing the raw key
        assert "key" in get_data2 or "status" in get_data2, "GET response missing expected key status fields after set"
        if "key" in get_data2:
            assert get_data2["key"] != test_api_key, "API key exposed in GET response after set"
    except requests.RequestException as e:
        raise AssertionError(f"Failed to get key status after set: {e}")
    except ValueError:
        raise AssertionError("GET response after set is not valid JSON")

    # 4. DELETE the key and verify deletion
    try:
        del_resp2 = requests.delete(key_endpoint, timeout=TIMEOUT)
        assert del_resp2.status_code in (200, 204), f"DELETE key failed with status {del_resp2.status_code}"
    except requests.RequestException as e:
        raise AssertionError(f"Failed to delete API key: {e}")

    # 5. GET key status after deletion to verify key is removed
    try:
        get_resp3 = requests.get(key_endpoint, timeout=TIMEOUT)
        assert get_resp3.status_code in (200, 404), f"GET key status after delete failed with status {get_resp3.status_code}"
        if get_resp3.status_code == 200:
            get_data3 = get_resp3.json()
            # Confirm key is now absent or empty
            if "key" in get_data3:
                # Expect empty or null to indicate no key
                assert not get_data3["key"], "API key still present after deletion"
    except requests.RequestException as e:
        raise AssertionError(f"Failed to get key status after delete: {e}")
    except ValueError:
        raise AssertionError("GET response after delete is not valid JSON")


test_manage_ncbi_api_key()
