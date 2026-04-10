"""
Unit tests for src.api.dependencies.auth module
Tests JWT Bearer token authentication and API Key functions
"""
import os
import sys
import asyncio
import jwt
from pathlib import Path
from datetime import timedelta, datetime, timezone

# Setup path
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(src_path))

import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException


def run_async(coro):
    """Helper to run async code in sync tests"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    new_loop = asyncio.new_event_loop()
    try:
        return new_loop.run_until_complete(coro)
    finally:
        new_loop.close()


@pytest.fixture
def clean_auth_module():
    """Fresh import of auth module for each test, with config state saved/restored"""
    import src.core.config
    # Save original state
    saved_keys = src.core.config.API_KEYS.copy()

    # Clear auth module from sys.modules so next import is fresh
    modules = [m for m in list(sys.modules.keys()) if
               m.startswith("api.dependencies.auth") or
               m.startswith("src.api.dependencies.auth")]
    for m in modules:
        sys.modules.pop(m, None)

    yield

    # Restore original API_KEYS state
    src.core.config.API_KEYS.clear()
    src.core.config.API_KEYS.update(saved_keys)


@pytest.fixture
def test_key():
    """A known test API key"""
    return "test-api-key-12345"


class TestRequireAuth:
    """Tests for require_auth dependency"""

    def test_no_api_keys_returns_no_auth_mode(self, clean_auth_module):
        """When no API keys configured, returns no-auth-mode"""
        # The config module's API_KEYS is a module-level set.
        # When auth module does 'from src.core.config import API_KEYS',
        # it gets a reference to that same set object.
        # Patching the set's content directly works:
        import src.core.config
        src.core.config.API_KEYS.clear()
        try:
            from src.api.dependencies.auth import require_auth
            result = run_async(require_auth(auth_header=None))
            assert result == "no-auth-mode"
        finally:
            src.core.config.API_KEYS.add("test-api-key-12345")

    def test_valid_api_key_via_bearer_token(self, clean_auth_module, test_key):
        """Valid API key in Bearer token format returns key"""
        with patch("src.api.dependencies.auth.API_KEYS", {test_key}):
            from src.api.dependencies.auth import require_auth, create_access_token
            token = create_access_token(test_key)
            result = run_async(require_auth(auth_header=f"Bearer {token}"))
            assert result == test_key

    def test_valid_raw_api_key(self, clean_auth_module, test_key):
        """Valid raw API key (non-Bearer) also accepted"""
        with patch("src.api.dependencies.auth.API_KEYS", {test_key}):
            from src.api.dependencies.auth import require_auth
            result = run_async(require_auth(auth_header=test_key))
            assert result == test_key

    def test_invalid_bearer_token_raises_401(self, clean_auth_module, test_key):
        """Invalid JWT raises 401"""
        with patch("src.api.dependencies.auth.API_KEYS", {test_key}):
            from src.api.dependencies.auth import require_auth
            with pytest.raises(HTTPException) as exc_info:
                run_async(require_auth(auth_header="Bearer invalid.token.here"))
            assert exc_info.value.status_code == 401

    def test_unknown_api_key_raises_401(self, clean_auth_module, test_key):
        """API key not in API_KEYS raises 401"""
        with patch("src.api.dependencies.auth.API_KEYS", {test_key}):
            from src.api.dependencies.auth import require_auth
            with pytest.raises(HTTPException) as exc_info:
                run_async(require_auth(auth_header="wrong-key"))
            assert exc_info.value.status_code == 401

    def test_missing_header_raises_401(self, clean_auth_module):
        """Missing auth header raises 401"""
        with patch("src.api.dependencies.auth.API_KEYS", {"some-key"}):
            from src.api.dependencies.auth import require_auth
            with pytest.raises(HTTPException) as exc_info:
                run_async(require_auth(auth_header=None))
            assert exc_info.value.status_code == 401


class TestJWTToken:
    """Tests for JWT token creation and decoding"""

    def test_create_and_decode_token(self, clean_auth_module, test_key):
        """JWT token can be created and decoded"""
        from src.api.dependencies.auth import create_access_token, decode_token
        token = create_access_token(test_key)
        payload = decode_token(token)
        assert payload["sub"] == test_key
        assert payload["type"] == "access"

    def test_expired_token_raises_401(self, clean_auth_module, test_key):
        """Expired JWT raises 401"""
        from src.api.dependencies.auth import decode_token
        from src.core.config import JWT_SECRET_KEY, JWT_ALGORITHM
        payload = {
            "sub": test_key,
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iat": datetime.now(timezone.utc) - timedelta(hours=1),
            "type": "access",
        }
        expired_token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        with pytest.raises(HTTPException) as exc_info:
            decode_token(expired_token)
        assert exc_info.value.status_code == 401

    def test_token_with_wrong_secret_raises_401(self, clean_auth_module, test_key):
        """Token signed with wrong secret raises 401"""
        from src.core.config import JWT_ALGORITHM
        from src.api.dependencies.auth import decode_token
        payload = {
            "sub": test_key,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
            "type": "access",
        }
        bad_token = jwt.encode(payload, "wrong-secret-long-enough-to-avoid-warning", algorithm=JWT_ALGORITHM)
        with pytest.raises(HTTPException) as exc_info:
            decode_token(bad_token)
        assert exc_info.value.status_code == 401


class TestRateLimiter:
    """Tests for SlidingWindowRateLimiter"""

    def test_rate_limit_allows_within_limit(self):
        """Within rate limit, requests are allowed - each call with a unique key"""
        from src.api.dependencies.auth import SlidingWindowRateLimiter
        limiter = SlidingWindowRateLimiter(max_requests=10, window_seconds=60)
        results = []
        for i in range(5):
            # Each call uses a different key (unique per call)
            allowed, info = limiter.is_allowed(f"test-key-unique-{i}")
            assert allowed is True
            results.append(info["remaining"])
        # Each unique key starts fresh, so remaining = max-1 = 9 for each
        assert results == [9, 9, 9, 9, 9]

    def test_rate_limit_same_key_decrements(self):
        """Repeated calls with SAME key decrement remaining count"""
        from src.api.dependencies.auth import SlidingWindowRateLimiter
        limiter = SlidingWindowRateLimiter(max_requests=10, window_seconds=60)
        results = []
        for i in range(5):
            allowed, info = limiter.is_allowed("test-key")
            assert allowed is True
            results.append(info["remaining"])
        # Same key accumulates: 9, 8, 7, 6, 5
        assert results == [9, 8, 7, 6, 5]

    def test_rate_limit_blocks_when_exceeded(self):
        """When limit exceeded, returns False"""
        from src.api.dependencies.auth import SlidingWindowRateLimiter
        limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            limiter.is_allowed("test-key")
        allowed, info = limiter.is_allowed("test-key")
        assert allowed is False
        assert info["remaining"] == 0
