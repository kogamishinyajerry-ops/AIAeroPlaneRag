"""
Authentication Routes - Token Exchange
提供 API Key 换取 JWT Bearer Token 的端点
"""
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field

from src.api.dependencies.auth import verify_api_key, create_access_token


router = APIRouter(prefix="/api/v1/auth", tags=["认证"])


class TokenRequest(BaseModel):
    """API Key 换取 Token 请求"""
    api_key: str = Field(..., min_length=1, description="API Key")


class TokenResponse(BaseModel):
    """Token 响应"""
    access_token: str = Field(..., description="JWT Bearer Token")
    token_type: str = Field(default="bearer", description="Token 类型")
    expires_in: int = Field(..., description="有效期（秒）")


@router.post("/token", response_model=TokenResponse)
async def get_token(req: TokenRequest) -> TokenResponse:
    """
    使用 API Key 换取 JWT Bearer Token

    换取后请在请求头中使用:
    Authorization: Bearer <access_token>
    """
    # 验证 api_key 是否有效（不走速率限制）
    key = await verify_api_key(req.api_key)
    if key == "no-auth-mode":
        # 如果服务器未配置 API Key，返回一个虚拟 Token 允许 UI 继续初始化
        from src.core.config import JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        return TokenResponse(
            access_token="no-auth-token-provided",
            token_type="bearer",
            expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    # 生成 JWT token
    token = create_access_token(req.api_key)
    from src.core.config import JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
