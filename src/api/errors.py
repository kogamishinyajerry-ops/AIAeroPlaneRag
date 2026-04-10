"""
统一错误响应模型
所有 API 错误响应遵循统一格式: {"error": "...", "code": "...", "details": {...}}
"""
from fastapi import HTTPException, status
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional


class APIErrorResponse(BaseModel):
    """统一错误响应格式"""
    error: str = Field(..., description="人类可读的错误描述")
    code: str = Field(..., description="机器可读的错误代码（snake_case）")
    details: Optional[Dict[str, Any]] = Field(default=None, description="附加错误详情")

    class Config:
        json_schema_extra = {
            "example": {
                "error": "请求的参数无效",
                "code": "invalid_parameter",
                "details": {"field": "query", "reason": "exceeds max_length"}
            }
        }


class APIError:
    """错误工厂类 - 产生标准化的 HTTPException"""

    # 4xx Client Errors
    @staticmethod
    def bad_request(message: str, code: str = "bad_request", details: Dict = None) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": message, "code": code, "details": details}
        )

    @staticmethod
    def unauthorized(message: str = "认证失败", code: str = "unauthorized", details: Dict = None) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": message, "code": code, "details": details},
            headers={"WWW-Authenticate": "Bearer"},
        )

    @staticmethod
    def forbidden(message: str = "权限不足", code: str = "forbidden", details: Dict = None) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": message, "code": code, "details": details}
        )

    @staticmethod
    def not_found(resource: str, identifier: str = "", code: str = "not_found", details: Dict = None) -> HTTPException:
        msg = f"{resource} not found"
        if identifier:
            msg = f"{resource} '{identifier}' not found"
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": msg, "code": code, "details": details or {"resource": resource, "identifier": identifier}}
        )

    @staticmethod
    def rate_limit_exceeded(retry_after: int = 60, code: str = "rate_limit_exceeded", details: Dict = None) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": f"速率限制超出，请在 {retry_after} 秒后重试", "code": code, "details": details},
            headers={"Retry-After": str(retry_after)},
        )

    # 5xx Server Errors
    @staticmethod
    def internal(message: str = "服务器内部错误", code: str = "internal_error", details: Dict = None) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": message, "code": code, "details": details}
        )

    @staticmethod
    def service_unavailable(service: str, code: str = "service_unavailable", details: Dict = None) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": f"服务 {service} 暂不可用", "code": code, "details": details}
        )


def http_exception_to_dict(exc: HTTPException) -> Dict[str, Any]:
    """将 HTTPException.detail 转为标准错误响应（兼容旧式 detail 字符串）"""
    detail = exc.detail
    if isinstance(detail, dict):
        if "error" in detail and "code" in detail:
            return detail
        # 其他 dict 格式包装为标准响应
        return {
            "error": detail.get("message", str(detail)),
            "code": "error",
            "details": detail,
        }
    return {"error": str(detail), "code": "error", "details": None}
