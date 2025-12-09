"""
Unit tests for circuit_breaker module.

Tests the circuit breaker pattern implementation including:
- with_circuit_breaker decorator
- get_circuit_state utility
- get_all_circuit_states utility
- reset_all_circuits utility
"""

import pytest
from unittest.mock import MagicMock, patch
from pybreaker import CircuitBreaker, CircuitBreakerError

from shared.circuit_breaker import (
    graph_breaker,
    openai_breaker,
    storage_breaker,
    with_circuit_breaker,
    get_circuit_state,
    get_all_circuit_states,
    reset_all_circuits,
)


@pytest.fixture(autouse=True)
def reset_breakers():
    """Reset all circuit breakers before and after each test."""
    graph_breaker.close()
    openai_breaker.close()
    storage_breaker.close()
    yield
    graph_breaker.close()
    openai_breaker.close()
    storage_breaker.close()


class TestWithCircuitBreakerDecorator:
    """Tests for the with_circuit_breaker decorator."""

    def test_decorator_passes_through_on_success(self):
        """Decorator allows successful calls to pass through."""
        test_breaker = CircuitBreaker(fail_max=3, reset_timeout=10, name="test")

        @with_circuit_breaker(test_breaker)
        def successful_function():
            return "success"

        result = successful_function()
        assert result == "success"

    def test_decorator_propagates_exceptions(self):
        """Decorator propagates exceptions from wrapped function."""
        test_breaker = CircuitBreaker(fail_max=3, reset_timeout=10, name="test")

        @with_circuit_breaker(test_breaker)
        def failing_function():
            raise RuntimeError("Test error")

        with pytest.raises(RuntimeError, match="Test error"):
            failing_function()

    def test_decorator_with_args_and_kwargs(self):
        """Decorator correctly passes args and kwargs."""
        test_breaker = CircuitBreaker(fail_max=3, reset_timeout=10, name="test")

        @with_circuit_breaker(test_breaker)
        def function_with_args(a, b, c=None):
            return f"{a}-{b}-{c}"

        result = function_with_args("x", "y", c="z")
        assert result == "x-y-z"

    def test_decorator_calls_fallback_when_circuit_open(self):
        """Decorator calls fallback function when circuit is open."""
        test_breaker = CircuitBreaker(fail_max=2, reset_timeout=60, name="test")

        def fallback_func(*args, **kwargs):
            return "fallback_result"

        @with_circuit_breaker(test_breaker, fallback=fallback_func)
        def failing_function():
            raise RuntimeError("Service unavailable")

        # Trip the circuit breaker (pybreaker opens on fail_max failure)
        # First failure
        with pytest.raises(RuntimeError):
            failing_function()
        # Second failure opens circuit and may raise either error
        try:
            failing_function()
        except (RuntimeError, CircuitBreakerError):
            pass

        # Circuit should now be open - next call should use fallback
        result = failing_function()
        assert result == "fallback_result"

    def test_decorator_raises_circuit_breaker_error_without_fallback(self):
        """Decorator raises CircuitBreakerError when circuit open and no fallback."""
        test_breaker = CircuitBreaker(fail_max=2, reset_timeout=60, name="test")

        @with_circuit_breaker(test_breaker)
        def failing_function():
            raise RuntimeError("Service unavailable")

        # Trip the circuit breaker (pybreaker opens on fail_max failure)
        # First failure
        with pytest.raises(RuntimeError):
            failing_function()
        # Second failure opens circuit and may raise either error
        try:
            failing_function()
        except (RuntimeError, CircuitBreakerError):
            pass

        # Circuit should now be open - next call should raise CircuitBreakerError
        with pytest.raises(CircuitBreakerError):
            failing_function()

    def test_decorator_logs_warning_when_circuit_open(self):
        """Decorator logs warning when circuit breaker is open."""
        test_breaker = CircuitBreaker(fail_max=2, reset_timeout=60, name="test")

        @with_circuit_breaker(test_breaker)
        def failing_function():
            raise RuntimeError("Service unavailable")

        # Trip the circuit breaker (pybreaker opens on fail_max failure)
        # First failure
        with pytest.raises(RuntimeError):
            failing_function()
        # Second failure opens circuit
        try:
            failing_function()
        except (RuntimeError, CircuitBreakerError):
            pass

        # Next call should log warning and raise CircuitBreakerError
        with patch("shared.circuit_breaker.logger") as mock_logger:
            with pytest.raises(CircuitBreakerError):
                failing_function()
            mock_logger.warning.assert_called_once()
            assert "OPEN" in mock_logger.warning.call_args[0][0]

    def test_decorator_preserves_function_metadata(self):
        """Decorator preserves the wrapped function's metadata."""
        test_breaker = CircuitBreaker(fail_max=3, reset_timeout=10, name="test")

        @with_circuit_breaker(test_breaker)
        def documented_function():
            """This function has documentation."""
            return "result"

        assert documented_function.__doc__ == "This function has documentation."
        assert documented_function.__name__ == "documented_function"


class TestGetCircuitState:
    """Tests for get_circuit_state function."""

    def test_get_circuit_state_closed(self):
        """Returns correct state info for closed circuit."""
        state = get_circuit_state(graph_breaker)

        assert state["name"] == "graph_api"
        assert state["state"] == "closed"
        assert state["fail_count"] == 0
        assert state["fail_max"] == 5
        assert state["reset_timeout"] == 60

    def test_get_circuit_state_open(self):
        """Returns correct state info for open circuit."""
        # Force circuit open by triggering failures
        for _ in range(5):
            try:
                graph_breaker.call(lambda: exec('raise RuntimeError("fail")'))
            except (RuntimeError, CircuitBreakerError):
                pass

        state = get_circuit_state(graph_breaker)
        assert state["state"] == "open"
        assert state["fail_count"] == 5

    def test_get_circuit_state_half_open(self):
        """Returns correct state info for half-open circuit."""
        # Force circuit open
        for _ in range(5):
            try:
                graph_breaker.call(lambda: exec('raise RuntimeError("fail")'))
            except (RuntimeError, CircuitBreakerError):
                pass

        # Manually transition to half-open
        graph_breaker.half_open()

        state = get_circuit_state(graph_breaker)
        assert state["state"] == "half-open"


class TestGetAllCircuitStates:
    """Tests for get_all_circuit_states function."""

    def test_returns_all_three_breakers(self):
        """Returns state info for all three circuit breakers."""
        states = get_all_circuit_states()

        assert "graph_api" in states
        assert "azure_openai" in states
        assert "azure_storage" in states

    def test_all_states_have_required_fields(self):
        """All states contain required fields."""
        states = get_all_circuit_states()

        for name, state in states.items():
            assert "name" in state
            assert "state" in state
            assert "fail_count" in state
            assert "fail_max" in state
            assert "reset_timeout" in state

    def test_returns_correct_breaker_names(self):
        """Returns correct names for each breaker."""
        states = get_all_circuit_states()

        assert states["graph_api"]["name"] == "graph_api"
        assert states["azure_openai"]["name"] == "azure_openai"
        assert states["azure_storage"]["name"] == "azure_storage"

    def test_returns_correct_configurations(self):
        """Returns correct configurations for each breaker."""
        states = get_all_circuit_states()

        # Graph API: fail_max=5, reset_timeout=60
        assert states["graph_api"]["fail_max"] == 5
        assert states["graph_api"]["reset_timeout"] == 60

        # Azure OpenAI: fail_max=3, reset_timeout=30
        assert states["azure_openai"]["fail_max"] == 3
        assert states["azure_openai"]["reset_timeout"] == 30

        # Azure Storage: fail_max=5, reset_timeout=45
        assert states["azure_storage"]["fail_max"] == 5
        assert states["azure_storage"]["reset_timeout"] == 45


class TestResetAllCircuits:
    """Tests for reset_all_circuits function."""

    def test_resets_all_circuits_to_closed(self):
        """All circuits are reset to closed state."""
        # Force all circuits open
        for breaker in [graph_breaker, openai_breaker, storage_breaker]:
            for _ in range(breaker.fail_max):
                try:
                    breaker.call(lambda: exec('raise RuntimeError("fail")'))
                except (RuntimeError, CircuitBreakerError):
                    pass

        # Verify all are open
        assert get_circuit_state(graph_breaker)["state"] == "open"
        assert get_circuit_state(openai_breaker)["state"] == "open"
        assert get_circuit_state(storage_breaker)["state"] == "open"

        # Reset all
        reset_all_circuits()

        # Verify all are closed
        assert get_circuit_state(graph_breaker)["state"] == "closed"
        assert get_circuit_state(openai_breaker)["state"] == "closed"
        assert get_circuit_state(storage_breaker)["state"] == "closed"

    def test_reset_logs_info_message(self):
        """Reset logs info message."""
        with patch("shared.circuit_breaker.logger") as mock_logger:
            reset_all_circuits()
            mock_logger.info.assert_called_once()
            assert "CLOSED" in mock_logger.info.call_args[0][0]

    def test_reset_clears_fail_counts(self):
        """Reset clears failure counts."""
        # Add some failures (not enough to open)
        for _ in range(2):
            try:
                graph_breaker.call(lambda: exec('raise RuntimeError("fail")'))
            except RuntimeError:
                pass

        assert get_circuit_state(graph_breaker)["fail_count"] > 0

        reset_all_circuits()

        assert get_circuit_state(graph_breaker)["fail_count"] == 0


class TestCircuitBreakerConfiguration:
    """Tests for circuit breaker configurations."""

    def test_graph_breaker_configuration(self):
        """Graph API breaker has correct configuration."""
        assert graph_breaker.name == "graph_api"
        assert graph_breaker.fail_max == 5
        assert graph_breaker.reset_timeout == 60

    def test_openai_breaker_configuration(self):
        """OpenAI breaker has more aggressive configuration."""
        assert openai_breaker.name == "azure_openai"
        assert openai_breaker.fail_max == 3  # More aggressive
        assert openai_breaker.reset_timeout == 30  # Shorter timeout

    def test_storage_breaker_configuration(self):
        """Storage breaker has correct configuration."""
        assert storage_breaker.name == "azure_storage"
        assert storage_breaker.fail_max == 5
        assert storage_breaker.reset_timeout == 45

    def test_breakers_exclude_validation_errors(self):
        """All breakers exclude ValueError and KeyError."""
        # These should NOT trip the circuit breaker
        for breaker in [graph_breaker, openai_breaker, storage_breaker]:
            for _ in range(10):
                try:
                    breaker.call(lambda: exec('raise ValueError("validation")'))
                except ValueError:
                    pass

            # Circuit should still be closed
            assert get_circuit_state(breaker)["state"] == "closed"
