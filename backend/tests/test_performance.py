import time
import statistics
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def measure_response_time(endpoint, method="GET", iterations=10):
    """Measure response time for an endpoint."""
    times = []
    for _ in range(iterations):
        start = time.time()
        if method == "GET":
            client.get(endpoint)
        elif method == "POST":
            client.post(endpoint, json={})
        end = time.time()
        times.append((end - start) * 1000)  # Convert to ms
    return {
        "min": min(times),
        "max": max(times),
        "avg": statistics.mean(times),
        "p50": statistics.median(times),
        "p95": sorted(times)[int(len(times) * 0.95)] if len(times) >= 20 else max(times),
    }


def test_api_performance():
    """Test API response times."""
    endpoints = [
        ("/api/health", "GET"),
        ("/api/farms", "GET"),
        ("/api/auth/me", "GET"),
    ]
    
    results = {}
    for endpoint, method in endpoints:
        results[endpoint] = measure_response_time(endpoint, method)
    
    # Assert performance thresholds
    for endpoint, stats in results.items():
        assert stats["avg"] < 500, f"{endpoint} average response time too high: {stats['avg']}ms"
        assert stats["p95"] < 1000, f"{endpoint} p95 response time too high: {stats['p95']}ms"
    
    return results


if __name__ == "__main__":
    results = test_api_performance()
    for endpoint, stats in results.items():
        print(f"{endpoint}: avg={stats['avg']:.2f}ms, p95={stats['p95']:.2f}ms")
