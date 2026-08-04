import pytest
from app.core.circuit_breaker import circuit_breaker, CircuitState, _breakers
from app.core.circuit_breaker import get_breaker


@pytest.fixture(autouse=True)
def clear_breakers():
    """Clear circuit breakers before each test."""
    _breakers.clear()
    yield
    _breakers.clear()


def test_circuit_breaker_thread_safe():
    import threading
    breaker = get_breaker("concurrent", max_failures=3, window_seconds=300)
    def hit():
        for _ in range(50):
            if breaker.should_allow_call():
                breaker.record_success()
    threads = [threading.Thread(target=hit) for _ in range(8)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert breaker.state in (CircuitState.CLOSED, CircuitState.OPEN, CircuitState.HALF_OPEN)


def test_circuit_breaker_closed_on_success():
    @circuit_breaker("test_service")
    async def success_func():
        return "success"
    
    import asyncio
    result = asyncio.run(success_func())
    assert result == "success"
    assert _breakers["test_service"].state == CircuitState.CLOSED


def test_circuit_breaker_opens_after_failures():
    call_count = 0
    
    @circuit_breaker("test_failing", max_failures=3, window_seconds=300)
    async def failing_func():
        nonlocal call_count
        call_count += 1
        raise Exception("Service unavailable")
    
    import asyncio
    # First 3 calls should fail normally
    for _ in range(3):
        with pytest.raises(Exception):
            asyncio.run(failing_func())
    
    # Circuit should now be open
    assert _breakers["test_failing"].state == CircuitState.OPEN


def test_circuit_breaker_fallback_on_open():
    @circuit_breaker("test_open", max_failures=1, window_seconds=300)
    async def failing_func():
        raise Exception("Service unavailable")
    
    import asyncio
    # Trigger circuit open
    with pytest.raises(Exception):
        asyncio.run(failing_func())
    
    # Should use fallback when circuit is open
    @circuit_breaker("test_open", max_failures=1, window_seconds=300, fallback="cached_data")
    async def failing_func_with_fallback():
        raise Exception("Service unavailable")
    
    result = asyncio.run(failing_func_with_fallback())
    assert result == "cached_data"


def test_circuit_breaker_success_resets_count():
    call_count = 0
    
    @circuit_breaker("test_reset", max_failures=3, window_seconds=300)
    async def sometimes_failing():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("First call fails")
        return "success"
    
    import asyncio
    # First call fails
    with pytest.raises(Exception):
        asyncio.run(sometimes_failing())
    
    # Second call succeeds - should reset failure count
    result = asyncio.run(sometimes_failing())
    assert result == "success"
    assert _breakers["test_reset"].failure_count == 0


def test_circuit_breaker_callable_fallback():
    def fallback_func(x, y):
        return f"fallback_{x}_{y}"
    
    @circuit_breaker("test_callable", max_failures=1, window_seconds=300, fallback=fallback_func)
    async def failing_func(a, b):
        raise Exception("Service unavailable")
    
    import asyncio
    # Trigger circuit open
    with pytest.raises(Exception):
        asyncio.run(failing_func(1, 2))
    
    # Should use callable fallback
    result = asyncio.run(failing_func(1, 2))
    assert result == "fallback_1_2"
