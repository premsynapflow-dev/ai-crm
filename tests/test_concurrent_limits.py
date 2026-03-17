import pytest
from concurrent.futures import ThreadPoolExecutor


def test_concurrent_requests(client, test_client_record):
    """Test handling of concurrent requests"""
    
    def make_request():
        return client.post(
            "/webhook/complaint",
            headers={"x-api-key": test_client_record.api_key},
            json={"message": "Concurrent test"}
        )
    
    # Fire 20 concurrent requests
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_request) for _ in range(20)]
        results = [f.result() for f in futures]
    
    # All should succeed (within limit)
    success_count = sum(1 for r in results if r.status_code == 200)
    assert success_count == 20


def test_rate_limiting(client, test_client_record):
    """Test rate limiting works"""
    # Depends on your rate limit config
    # If webhook limit is 100/hour, fire 101 requests
    
    responses = []
    for i in range(101):
        response = client.post(
            "/webhook/complaint",
            headers={"x-api-key": test_client_record.api_key},
            json={"message": f"Rate test {i}"}
        )
        responses.append(response)
    
    # Last request should be rate limited
    assert responses[-1].status_code == 429
