import asyncio
import time
import pytest
from httpx import AsyncClient
from procedurewriter.main import app

@pytest.mark.asyncio
async def test_concurrency_ingest_pdf():
    """Verify that multiple PDF ingest requests can run concurrently.
    
    This test mocks the extract_pdf_pages to take some time, and verifies
    that N requests don't take N * T time.
    """
    from procedurewriter.pipeline import normalize
    from unittest import mock
    
    # Mock a slow extraction function
    SLEEP_TIME = 0.5
    def slow_extract(*args, **kwargs):
        time.sleep(SLEEP_TIME)
        return ["Page 1 content"]
    
    with mock.patch("procedurewriter.main.extract_pdf_pages", side_effect=slow_extract):
        from httpx import ASGITransport
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # Create a dummy PDF file
            files = {'file': ('test.pdf', b'%PDF-1.4 content', 'application/pdf')}
            
            start_time = time.perf_counter()
            
            # Send 3 concurrent requests
            tasks = [
                ac.post("/api/ingest/pdf", files={'file': ('test.pdf', b'%PDF-1.4 content', 'application/pdf')})
                for _ in range(3)
            ]
            responses = await asyncio.gather(*tasks)
            
            end_time = time.perf_counter()
            total_duration = end_time - start_time
            
            for resp in responses:
                assert resp.status_code == 200
                
            # If serial, it would take at least 3 * SLEEP_TIME = 1.5s
            # If concurrent, it should take significantly less (around SLEEP_TIME + overhead)
            # We use a generous threshold of 1.2s to account for CI overhead but ensure it's < 1.5s
            assert total_duration < (SLEEP_TIME * 2.5), f"Total duration {total_duration}s suggests serial execution"
            print(f"Concurrency verified: 3 requests took {total_duration:.4f}s (serial would be >= {3*SLEEP_TIME}s)")
