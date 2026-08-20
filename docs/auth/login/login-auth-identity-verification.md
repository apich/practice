# 登录路由身份验证机制

本文档详细说明后端登录路由如何确定开发者（developer）和终端用户（end_user）的身份。

## 概述

系统通过用户角色（role）区分开发者和终端用户，角色信息在登录时确定，编码到JWT中，并通过中间件和依赖注入进行验证。

## 1. 用户角色定义

在 [models.py:13-18](../../backend/app/auth/models.py#L13-L18) 中定义了两种角色：
- `Role.DEVELOPER` = "developer"
- `Role.END_USER` = "end_user"

用户表（User）的 `role` 字段存储此角色。

## 2. 登录时的角色判定

### 本地密码登录

在 [router.py:206-224](../../backend/app/auth/router.py#L206-L224) 中，直接从数据库读取用户的 `role` 字段：

```python
user = result.scalar_one_or_none()
token_data = {
    "access_token": create_access_token(user.user_id, user.username, user.role),
    # ...
    "role": user.role,
}
```

### OAuth2.0 登录

在 [service.py:80-103](../../backend/app/auth/service.py#L80-L103) 的 `_resolve_oauth_role()` 方法中，根据外部认证系统的 `roleMap` 和环境变量配置决定角色：

```python
def _resolve_oauth_role(self, info: dict[str, Any]) -> str:
    role_map = info.get("roleMap", {})
    user_role_ids = set(role_map.keys()) if role_map else set()
    
    developer_ids = {s.strip() for s in settings.role_developer_ids.split(",") if s.strip()}
    end_user_ids = {s.strip() for s in settings.role_end_user_ids.split(",") if s.strip()}
    
    if developer_ids and user_role_ids & developer_ids:
        return Role.DEVELOPER
    if end_user_ids and user_role_ids & end_user_ids:
        return Role.END_USER
    return Role.END_USER  # 默认终端用户
```

## 3. 角色信息的传递

登录成功后，角色信息被编码到 JWT token 中：

- [service.py:115-126](../../backend/app/auth/service.py#L115-L126)：JWT payload 包含 `role` 和 `roles` 字段
- [middleware.py:86-108](../../backend/app/auth/middleware.py#L86-L108)：中间件解码 JWT 并设置 `AuthContext`

## 4. 角色验证机制

### 路由级别验证

使用 `require_role()` 依赖注入，如 [router.py:322-327](../../backend/app/auth/router.py#L322-L327)：

```python
@router.post("/register", response_model=UserInfoResponse)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    _current: User = Depends(require_role(Role.DEVELOPER)),  # 仅开发者可注册
) -> UserInfoResponse:
```

### 中间件级别验证

[middleware.py:120-152](../../backend/app/auth/middleware.py#L120-L152) 的 `AccessControlMiddleware` 自动阻止终端用户访问开发者专用端点：

```python
DEVELOPER_ONLY_PREFIXES = (
    "/agent", "/credential", "/mcp", "/skill", "/knowledge",
    "/publish/my", "/publish/agent",  # 等
)

# 终端用户访问这些路径时返回 403
if role == Role.END_USER:
    for prefix in DEVELOPER_ONLY_PREFIXES:
        if path.startswith(prefix):
            return JSONResponse(status_code=403, ...)
```

## 5. 权限验证（补充）

除了角色，还有基于 Cookie 的权限验证机制（[deps.py:220-297](../../backend/app/auth/deps.py#L220-L297)），支持更细粒度的权限控制。

## 总结

身份确定流程：
1. **登录时**：根据用户来源（本地数据库或 OAuth）确定角色
2. **JWT 中**：角色信息编码在 token 中
3. **请求时**：中间件解码 JWT 并设置上下文
4. **验证时**：路由依赖或中间件检查角色权限

这样实现了开发者和终端用户的区分访问控制。