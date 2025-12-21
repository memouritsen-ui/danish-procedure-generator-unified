import requests
import os

def test_upload_pdf_document_to_library():
    base_url = "http://localhost:8000"
    endpoint = "/api/ingest/pdf"
    url = base_url + endpoint
    headers = {}
    timeout = 30

    # Prepare a sample PDF content (as bytes).
    # For testing purpose, we create a minimal valid PDF file content.
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Count 1 /Kids [3 0 R] >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
        b"/Contents 4 0 R >>\nendobj\n"
        b"4 0 obj\n<< /Length 44 >>\nstream\n"
        b"BT\n/F1 24 Tf\n100 100 Td\n(Test PDF) Tj\nET\nendstream\nendobj\n"
        b"xref\n0 5\n0000000000 65535 f \n0000000010 00000 n \n0000000060 00000 n \n"
        b"0000000117 00000 n \n0000000214 00000 n \ntrailer\n<< /Size 5 /Root 1 0 R >>\n"
        b"startxref\n311\n%%EOF"
    )

    files = {
        "file": ("test_upload.pdf", pdf_content, "application/pdf")
    }

    response = None
    try:
        response = requests.post(url, files=files, headers=headers, timeout=timeout)
        assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
        # Response content check: assume JSON with some confirmation fields
        try:
            json_response = response.json()
            # Expect some keys confirming ingestion, e.g. "id", "message" or similar
            assert isinstance(json_response, dict), "Response is not a JSON object"
            assert ("id" in json_response) or ("message" in json_response), \
                "Response JSON does not contain expected keys ('id' or 'message')"
        except ValueError:
            assert False, "Response is not valid JSON"
    except requests.RequestException as e:
        assert False, f"Request failed with exception: {e}"

test_upload_pdf_document_to_library()