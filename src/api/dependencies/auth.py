"""
API Key Authentication & Rate Limiting & JWT
敏感端点的API Key认证、JWT验证和速率限制
"""
import os
import time
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from collections import defaultdict
from fastapi import HTTPException, Security, status, Depends
from fastapi.security import APIKeyHeader

try:
    import jwt
except ImportError:
    jwt = None

from src.core.config import (
    API_KEYS,
    RATE_LIMIT_ENABLED,
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW_SECONDS,
    RATE_LIMIT_STORAGE,
    REDIS_URL,
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
)


# API Key header定义
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
BEARER_HEADER = APIKeyHeader(name="Authorization", auto_error=False)


# === 速率限制器 (滑动窗口实现) ===
class SlidingWindowRateLimiter:
    """
    基于滑动窗口的速率限制器
    """

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = __import__("threading").Lock()

    def _cleanup_window(self, key: str, current_time: float) -> None:
        cutoff = current_time - self.window_seconds
        self._requests[key] = [ts for ts in self._requests[key] if ts > cutoff]

    def is_allowed(self, key: str) -> tuple[bool, dict]:
        current_time = time.time()
        with self._lock:
            self._cleanup_window(key, current_time)
            current_count = len(self._requests[key])
            if current_count >= self.max_requests:
                oldest_ts = min(self._requests[key]) if self._requests[key] else current_time
                reset_in = int(oldest_ts + self.window_seconds - current_time)
                return False, {
                    "remaining": 0,
                    "reset_in": max(1, reset_in),
                    "limit": self.max_requests,
                    "window_seconds": self.window_seconds,
                }
            self._requests[key].append(current_time)
            return True, {
                "remaining": self.max_requests - current_count - 1,
                "reset_in": self.window_seconds,
                "limit": self.max_requests,
                "window_seconds": self.window_seconds,
            }

    def get_status(self, key: str) -> dict:
        current_time = time.time()
        with self._lock:
            self._cleanup_window(key, current_time)
            current_count = len(self._requests[key])
            return {
                "remaining": max(0, self.max_requests - current_count),
                "used": current_count,
                "limit": self.max_requests,
                "window_seconds": self.window_seconds,
            }


# === Redis 分布式速率限制器（滑动窗口，sorted set 实现）===
class RedisRateLimiter:
    """
    基于 Redis sorted set 的滑动窗口分布式速率限制器。
    兼容 SlidingWindowRateLimiter 接口，支持跨进程/跨实例共享。
    """

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._client = None
        self._connect()

    def _connect(self) -> None:
        try:
            import redis as redis_lib
            self._client = redis_lib.from_url(
                REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
            self._client.ping()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "Redis rate limiter unavailable (%s), falling back to in-memory.", exc
            )
            self._client = None

    def is_allowed(self, key: str) -> tuple[bool, dict]:
        if not self._client:
            # Redis 不可用时拒绝（强制使用配置了 Redis 的实例）
            return False, {
                "remaining": 0,
                "reset_in": self.window_seconds,
                "limit": self.max_requests,
                "window_seconds": self.window_seconds,
            }

        now = time.time()
        window_start = now - self.window_seconds
        redis_key = f"ratelimit:{key}"

        pipe = self._client.pipeline()
        pipe.zremrangebyscore(redis_key, 0, window_start)  # 清理过期
        pipe.zcard(redis_key)  # 当前窗口内请求数
        pipe.zadd(redis_key, {str(now): now})  # 添加当前请求
        pipe.expire(redis_key, self.window_seconds + 1)
        results = pipe.execute()
        current_count = results[1]  # zcard result

        if current_count >= self.max_requests:
            # 获取最旧请求的时间以计算 reset_in
            oldest = self._client.zrange(redis_key, 0, 0, withscores=True)
            reset_in = self.window_seconds
            if oldest:
                reset_in = int(oldest[0][1] + self.window_seconds - now)
            return False, {
                "remaining": 0,
                "reset_in": max(1, reset_in),
                "limit": self.max_requests,
                "window_seconds": self.window_seconds,
            }

        return True, {
            "remaining": self.max_requests - current_count - 1,
            "reset_in": self.window_seconds,
            "limit": self.max_requests,
            "window_seconds": self.window_seconds,
        }

    def get_status(self, key: str) -> dict:
        if not self._client:
            return {
                "remaining": 0,
                "used": self.max_requests,
                "limit": self.max_requests,
                "window_seconds": self.window_seconds,
            }

        now = time.time()
        window_start = now - self.window_seconds
        redis_key = f"ratelimit:{key}"

        self._client.zremrangebyscore(redis_key, 0, window_start)
        current_count = self._client.zcard(redis_key)

        return {
            "remaining": max(0, self.max_requests - current_count),
            "used": current_count,
            "limit": self.max_requests,
            "window_seconds": self.window_seconds,
        }


# 全局限速率限制器实例（根据配置选择 Redis 或内存）
if RATE_LIMIT_STORAGE == "redis":
    rate_limiter = RedisRateLimiter(
        max_requests=RATE_LIMIT_REQUESTS,
        window_seconds=RATE_LIMIT_WINDOW_SECONDS,
    )
else:
    rate_limiter = SlidingWindowRateLimiter(
        max_requests=RATE_LIMIT_REQUESTS,
        window_seconds=RATE_LIMIT_WINDOW_SECONDS,
    )


# === JWT Token 生成 ===
def create_access_token(api_key: str, expires_delta: Optional[timedelta] = None) -> str:
    """为API Key创建JWT访问令牌"""
    if jwt is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "JWT support is unavailable on this server", "code": "jwt_unavailable", "details": None},
        )
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": api_key,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """解码并验证JWT Token"""
    if jwt is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "JWT support is unavailable on this server", "code": "jwt_unavailable", "details": None},
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Token has expired", "code": "token_expired", "details": None},
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Invalid token", "code": "invalid_token", "details": None},
            headers={"WWW-Authenticate": "Bearer"},
        )


# === Token获取端点 ===
async def verify_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """验证API Key（仅用于Token换取，不做速率限制）"""
    if not API_KEYS:
        return "no-auth-mode"
    if api_key and api_key in API_KEYS:
        return api_key
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": "Invalid or missing API Key", "code": "invalid_api_key", "details": None},
        headers={"WWW-Authenticate": "ApiKey"},
    )


def _check_any_auth(auth_value: Optional[str]) -> str:
    """
    核心验证逻辑：支持JWT Bearer token 或 API Key
    Returns: api_key identifier
    """
    # 空值
    if not auth_value:
        if not API_KEYS:
            return "no-auth-mode"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Missing authentication token", "code": "missing_auth", "details": None},
            headers={"WWW-Authenticate": "Bearer realm='api', ApiKey"},
        )

    # Bearer JWT token
    if auth_value.lower().startswith("bearer "):
        token = auth_value[7:]
        # 允许特殊的 no-auth-token 在未配置 API Key 时通过
        if token == "no-auth-token-provided" and not API_KEYS:
            return "no-auth-mode"
            
        payload = decode_token(token)
        api_key = payload.get("sub", "")
        if api_key not in API_KEYS and API_KEYS:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "Token references unknown API key", "code": "invalid_token", "details": None},
                headers={"WWW-Authenticate": "Bearer"},
            )
        # 速率限制（基于原始api_key标识）
        if RATE_LIMIT_ENABLED:
            allowed, rate_info = rate_limiter.is_allowed(api_key)
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={"error": f"速率限制超出，请在 {rate_info['reset_in']} 秒后重试", "code": "rate_limit_exceeded", "details": {"retry_after": rate_info["reset_in"], "limit": rate_info["limit"]}},
                    headers={
                        "Retry-After": str(rate_info["reset_in"]),
                        "X-RateLimit-Limit": str(rate_info["limit"]),
                        "X-RateLimit-Remaining": str(rate_info["remaining"]),
                    },
                )
        return api_key

    # API Key直接使用
    if auth_value in API_KEYS:
        if RATE_LIMIT_ENABLED:
            allowed, rate_info = rate_limiter.is_allowed(auth_value)
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={"error": f"速率限制超出，请在 {rate_info['reset_in']} 秒后重试", "code": "rate_limit_exceeded", "details": {"retry_after": rate_info["reset_in"], "limit": rate_info["limit"]}},
                    headers={
                        "Retry-After": str(rate_info["reset_in"]),
                        "X-RateLimit-Limit": str(rate_info["limit"]),
                        "X-RateLimit-Remaining": str(rate_info["remaining"]),
                    },
                )
        return auth_value

    if not API_KEYS:
        return "no-auth-mode"
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": "Invalid or missing API Key", "code": "invalid_api_key", "details": None},
        headers={"WWW-Authenticate": "ApiKey"},
    )


# 需要认证的端点依赖
async def require_auth(auth_header: Optional[str] = Security(BEARER_HEADER)) -> str:
    """
    需要认证的依赖：支持JWT Bearer token 或 API Key
    """
    return _check_any_auth(auth_header)


# 异步版本
async def async_require_auth(auth_header: Optional[str] = Security(BEARER_HEADER)) -> str:
    return _check_any_auth(auth_header)


# 可选的认证
async def optional_auth(auth_header: Optional[str] = Security(BEARER_HEADER)) -> str:
    if not auth_header:
        if not API_KEYS:
            return "no-auth-mode"
        return "anonymous"
    try:
        return _check_any_auth(auth_header)
    except HTTPException:
        if not API_KEYS:
            return "no-auth-mode"
        return "anonymous"
