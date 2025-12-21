import requests

def test_upload_docx_document_to_library():
    url = "http://localhost:8000/api/ingest/docx"
    timeout = 30
    headers = {}
    docx_content = (
        b"PK\x03\x04\x14\x00\x06\x00\x08\x00\x00\x00!\x00\xad\xae\xb6N"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x13\x00\x1c"
        b"\x00word/document.xml\xaaVmo\xc30\x0c\xfc}a\xff\xfe\x9cZ"
        b"\xbfH\x08J\x8c\xcc\xf4\xf4\x0b\xb4\xb0\xb6\x08\xdd!;\xef\x81"
        b"f\x1d\xd4*\x81\x02>\xc3<\x8f\x89\xe9\x9a\x84\xce\x01\x19E,"
        b"\xdc\xc3\xf7\xf7e\xb5N\x1e}"
    )  # minimal valid DOCX signature + some dummy content

    files = {
        "file": ("test_document.docx", docx_content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    }

    try:
        response = requests.post(url, headers=headers, files=files, timeout=timeout)
        assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
        json_response = response.json()
        # We expect some confirmation in response JSON that document is stored.
        # Validate presence of typical keys if available, else just assert valid JSON.
        assert isinstance(json_response, dict), "Response is not a JSON object"
        # Based on the PRD, no detailed schema given for this endpoint's response,
        # so just check successful processing indication.
        # We check for keys like 'id', 'message', or 'status' if present.
        assert any(key in json_response for key in ("id", "message", "status")), \
            "Response JSON does not contain expected keys indicating success"
    except requests.exceptions.RequestException as e:
        assert False, f"Request failed: {e}"

test_upload_docx_document_to_library()
