"""自定义异常类与全局异常处理器.

参考 agent-archetype 的异常体系设计：
- AppError: 应用异常基类，携带 error_code / status_code / details
- AuthenticationError: 401 认证失败
- AuthorizationError: 403 权限不足
- NotFoundError: 404 资源不存在

提供 register_exception_handlers() 注册到 FastAPI 应用。
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class AppError(Exception):
    """应用异常基类."""

    def __init__(
        self,
        message: str,
        error_code: str = "APP_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}


class AuthenticationError(AppError):
    """认证失败 (401)."""

    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(
            message=message,
            error_code="AUTH_ERROR",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class AuthorizationError(AppError):
    """权限不足 (403)."""

    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(
            message=message,
            error_code="AUTHZ_ERROR",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class NotFoundError(AppError):
    """资源不存在 (404)."""

    def __init__(self, resource: str, resource_id: str) -> None:
        super().__init__(
            message=f"{resource} '{resource_id}' not found",
            error_code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器到 FastAPI 应用."""

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        """处理应用异常，返回统一格式的错误响应."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        """处理未预期的异常，隐藏内部细节."""
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                }
            },
        )
