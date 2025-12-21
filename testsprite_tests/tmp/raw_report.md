
# TestSprite AI Testing Report(MCP)

---

## 1️⃣ Document Metadata
- **Project Name:** danish-procedure-generator-unified
- **Date:** 2025-12-18
- **Prepared by:** TestSprite AI Team

---

## 2️⃣ Requirement Validation Summary

#### Test TC001
- **Test Name:** get application status
- **Test Code:** [TC001_get_application_status.py](./TC001_get_application_status.py)
- **Test Error:** Traceback (most recent call last):
  File "/var/task/handler.py", line 258, in run_with_retry
    exec(code, exec_env)
  File "<string>", line 37, in <module>
  File "<string>", line 17, in test_get_application_status
AssertionError: Expected status code 200, got 404

- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/ce948c20-7ecd-4cfb-831b-73d1bc2fc90c/04f5ae45-fc6e-41aa-ae01-e4326a9fb089
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC002
- **Test Name:** list all procedure generation runs
- **Test Code:** [TC002_list_all_procedure_generation_runs.py](./TC002_list_all_procedure_generation_runs.py)
- **Test Error:** Traceback (most recent call last):
  File "<string>", line 12, in test_list_all_procedure_generation_runs
  File "/var/task/requests/models.py", line 1024, in raise_for_status
    raise HTTPError(http_error_msg, response=self)
requests.exceptions.HTTPError: 404 Client Error: Not Found for url: http://localhost:8000/api/runs

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/var/task/handler.py", line 258, in run_with_retry
    exec(code, exec_env)
  File "<string>", line 26, in <module>
  File "<string>", line 14, in test_list_all_procedure_generation_runs
AssertionError: Request to http://localhost:8000/api/runs failed: 404 Client Error: Not Found for url: http://localhost:8000/api/runs

- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/ce948c20-7ecd-4cfb-831b-73d1bc2fc90c/a798c3c0-627a-41e7-831d-51c29b6ce656
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC003
- **Test Name:** get run details by id
- **Test Code:** [TC003_get_run_details_by_id.py](./TC003_get_run_details_by_id.py)
- **Test Error:** Traceback (most recent call last):
  File "/var/task/handler.py", line 258, in run_with_retry
    exec(code, exec_env)
  File "<string>", line 45, in <module>
  File "<string>", line 22, in test_get_run_details_by_id
  File "<string>", line 14, in start_run
  File "/var/task/requests/models.py", line 1024, in raise_for_status
    raise HTTPError(http_error_msg, response=self)
requests.exceptions.HTTPError: 404 Client Error: Not Found for url: http://localhost:8000/api/write

- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/ce948c20-7ecd-4cfb-831b-73d1bc2fc90c/1c6ed664-4571-4814-ad77-cfbc076544bc
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC004
- **Test Name:** start new procedure generation
- **Test Code:** [TC004_start_new_procedure_generation.py](./TC004_start_new_procedure_generation.py)
- **Test Error:** Traceback (most recent call last):
  File "<string>", line 17, in test_start_new_procedure_generation
  File "/var/task/requests/models.py", line 1024, in raise_for_status
    raise HTTPError(http_error_msg, response=self)
requests.exceptions.HTTPError: 404 Client Error: Not Found for url: http://localhost:8000/api/write

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/var/task/handler.py", line 258, in run_with_retry
    exec(code, exec_env)
  File "<string>", line 27, in <module>
  File "<string>", line 24, in test_start_new_procedure_generation
AssertionError: Request failed: 404 Client Error: Not Found for url: http://localhost:8000/api/write

- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/ce948c20-7ecd-4cfb-831b-73d1bc2fc90c/6d610291-371c-4aa6-a562-502d2eaadd53
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC005
- **Test Name:** manage openai api key
- **Test Code:** [TC005_manage_openai_api_key.py](./TC005_manage_openai_api_key.py)
- **Test Error:** Traceback (most recent call last):
  File "/var/task/handler.py", line 258, in run_with_retry
    exec(code, exec_env)
  File "<string>", line 61, in <module>
  File "<string>", line 32, in test_manage_openai_api_key
AssertionError

- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/ce948c20-7ecd-4cfb-831b-73d1bc2fc90c/faa1d766-1bf1-44a7-aa02-aedd01018136
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC006
- **Test Name:** manage anthropic api key
- **Test Code:** [TC006_manage_anthropic_api_key.py](./TC006_manage_anthropic_api_key.py)
- **Test Error:** Traceback (most recent call last):
  File "/var/task/handler.py", line 258, in run_with_retry
    exec(code, exec_env)
  File "<string>", line 56, in <module>
  File "<string>", line 27, in test_manage_anthropic_api_key
AssertionError: Failed to set Anthropic API key, status 404

- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/ce948c20-7ecd-4cfb-831b-73d1bc2fc90c/479a6aa0-ac25-4887-9131-ac2edce801a3
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC007
- **Test Name:** manage ncbi api key
- **Test Code:** [TC007_manage_ncbi_api_key.py](./TC007_manage_ncbi_api_key.py)
- **Test Error:** Traceback (most recent call last):
  File "/var/task/handler.py", line 258, in run_with_retry
    exec(code, exec_env)
  File "<string>", line 87, in <module>
  File "<string>", line 38, in test_manage_ncbi_api_key
AssertionError: PUT set key failed with status 404

- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/ce948c20-7ecd-4cfb-831b-73d1bc2fc90c/e4aea6ce-758a-4680-bc66-0e731dea9a35
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC008
- **Test Name:** upload pdf document to library
- **Test Code:** [TC008_upload_pdf_document_to_library.py](./TC008_upload_pdf_document_to_library.py)
- **Test Error:** Traceback (most recent call last):
  File "/var/task/handler.py", line 258, in run_with_retry
    exec(code, exec_env)
  File "<string>", line 46, in <module>
  File "<string>", line 33, in test_upload_pdf_document_to_library
AssertionError: Expected status code 200, got 404

- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/ce948c20-7ecd-4cfb-831b-73d1bc2fc90c/a3f81e9b-c5d0-4581-a416-91151665dea9
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC009
- **Test Name:** upload docx document to library
- **Test Code:** [TC009_upload_docx_document_to_library.py](./TC009_upload_docx_document_to_library.py)
- **Test Error:** Traceback (most recent call last):
  File "/var/task/handler.py", line 258, in run_with_retry
    exec(code, exec_env)
  File "<string>", line 35, in <module>
  File "<string>", line 22, in test_upload_docx_document_to_library
AssertionError: Expected status code 200, got 404

- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/ce948c20-7ecd-4cfb-831b-73d1bc2fc90c/1dc17e10-66e2-4504-b6ed-ec7eeb03f26e
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC010
- **Test Name:** ingest url to library
- **Test Code:** [TC010_ingest_url_to_library.py](./TC010_ingest_url_to_library.py)
- **Test Error:** Traceback (most recent call last):
  File "/var/task/handler.py", line 258, in run_with_retry
    exec(code, exec_env)
  File "<string>", line 36, in <module>
  File "<string>", line 23, in test_ingest_url_to_library
AssertionError: Expected status code 200, got 404

- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/ce948c20-7ecd-4cfb-831b-73d1bc2fc90c/47086c23-7c62-420c-8fbe-9f9b6b2d456f
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---


## 3️⃣ Coverage & Matching Metrics

- **0.00** of tests passed

| Requirement        | Total Tests | ✅ Passed | ❌ Failed  |
|--------------------|-------------|-----------|------------|
| ...                | ...         | ...       | ...        |
---


## 4️⃣ Key Gaps / Risks
{AI_GNERATED_KET_GAPS_AND_RISKS}
---