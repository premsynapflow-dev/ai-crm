"""
Load testing script using httpx
Run: python tests/load_test.py
"""

import asyncio
import httpx
import time
from statistics import mean, median
import os

API_URL = os.getenv("API_URL", "http://localhost:8000")
API_KEY = os.getenv("TEST_API_KEY", "test_key")


async def make_request(client: httpx.AsyncClient):
    """Make single complaint request"""
    start = time.time()
    try:
        response = await client.post(
            f"{API_URL}/webhook/complaint",
            headers={"x-api-key": API_KEY},
            json={
                "message": "Load test complaint",
                "source": "api"
            },
            timeout=30.0
        )
        duration = (time.time() - start) * 1000  # ms
        return {
            "status": response.status_code,
            "duration": duration,
            "success": response.status_code == 200
        }
    except Exception as e:
        return {
            "status": 0,
            "duration": (time.time() - start) * 1000,
            "success": False,
            "error": str(e)
        }


async def run_load_test(concurrent_requests: int = 50, total_requests: int = 500):
    """Run load test"""
    print(f"Starting load test:")
    print(f"  - Concurrent requests: {concurrent_requests}")
    print(f"  - Total requests: {total_requests}")
    print(f"  - Target URL: {API_URL}")
    
    async with httpx.AsyncClient() as client:
        batches = total_requests // concurrent_requests
        all_results = []
        
        start_time = time.time()
        
        for batch in range(batches):
            tasks = [make_request(client) for _ in range(concurrent_requests)]
            results = await asyncio.gather(*tasks)
            all_results.extend(results)
            
            print(f"Batch {batch + 1}/{batches} complete")
        
        total_time = time.time() - start_time
        
        # Calculate stats
        successes = [r for r in all_results if r["success"]]
        failures = [r for r in all_results if not r["success"]]
        durations = [r["duration"] for r in successes]
        
        print(f"\n=== Load Test Results ===")
        print(f"Total time: {total_time:.2f}s")
        print(f"Requests/sec: {total_requests / total_time:.2f}")
        print(f"Success rate: {len(successes)}/{total_requests} ({len(successes)/total_requests*100:.1f}%)")
        print(f"Failed requests: {len(failures)}")
        
        if durations:
            print(f"\nLatency (ms):")
            print(f"  - Mean: {mean(durations):.2f}")
            print(f"  - Median: {median(durations):.2f}")
            print(f"  - Min: {min(durations):.2f}")
            print(f"  - Max: {max(durations):.2f}")
            print(f"  - P95: {sorted(durations)[int(len(durations)*0.95)]:.2f}")
            print(f"  - P99: {sorted(durations)[int(len(durations)*0.99)]:.2f}")


if __name__ == "__main__":
    asyncio.run(run_load_test(concurrent_requests=50, total_requests=500))
