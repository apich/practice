# Agent Platform 认证流程

本文档详细说明了 Agent Platform 的认证和授权机制。

## 概述

平台采用多层认证架构，确保安全性：

```
请求进入
  ↓
AuthMiddleware (解码 JWT)
  ↓
AccessControlMiddleware (角色检查)
  ↓
路由处理器
  - get_current_user → 验证认证状态
  - require_role → 验证角色权限
```

## 1. AuthMiddleware — JWT 解码

**文件位置**: `backend/app/auth/middleware.py`

### 功能
- 从 `Authorization: Bearer <token>` 头提取 JWT
- 解码 JWT 并验证有效性
- 将用户信息存储到 `request.state.user`
- 设置 `AuthContext` ContextVar 供依赖注入使用

### 处理流程

```python
# 1. 提取 Bearer Token
auth_header = request.headers.get("Authorization", "")
token = extract_bearer_token(auth_header)

# 2. 解码 JWT
payload = decode_token(token)

# 3. 存储到 request.state
request.state.user = payload  # 或 None（无 token 时）
```

### JWT Payload 结构

```json
{
    "sub": "user_id_123",
    "username": "test_user",
    "role": "developer",
    "roles": ["developer"],
    "permissions": [],
    "exp": 1719234567,
    "iat": 1719148167,
    "iss": "agent-platform",
    "type": "access"
}
```

## 2. AccessControlMiddleware — 角色检查

**文件位置**: `backend/app/auth/middleware.py`

### 功能
- 拦截 `end_user` 角色访问开发者专用 API
- 返回 403 Forbidden 响应

### 开发者专用 API 前缀

```python
DEVELOPER_ONLY_PREFIXES = (
    "/agent",          # create / update / delete agents
    "/credential",     # credential management
    "/mcp",            # MCP management
    "/skill",          # skill management
    "/knowledge",      # knowledge base management
    "/knowledge_bases",
    "/schedule",       # schedule management
    "/channel",        # channel management
    "/hub",            # resource hubs
    "/embedding-model",
    "/model",          # model listing / config
    "/tts-model",
    "/auth/register",  # user registration
    "/publish/my",     # developer's own publications
    "/publish/agent",  # POST publish
    "/unpublish",      # unpublish
)
```

### 处理流程

`AccessControlMiddleware` 的职责**不是认证**，而是**角色鉴权**——它只关心一件事：`end_user` 角色不能访问开发者的接口。

```
请求进入 AccessControlMiddleware
  │
  ├─ 公开路径（/health, /docs 等）？→ 直接放行
  │
  ├─ request.state.user 为空？→ 直接放行（不管，让后面的路由层去 401）
  │
  ├─ 角色不是 end_user？→ 直接放行（developer/admin 什么都能访问）
  │
  └─ 角色是 end_user？
       ├─ 访问 /agent, /credential 等开发者接口？→ 403 拒绝
       └─ 其他路径？→ 放行
```

```python
# 1. 公开路径直接放行
if path in PUBLIC_PATHS:
    return await call_next(request)

# 2. 未认证用户放行（交给路由处理）
user_payload = getattr(request.state, "user", None)
if not user_payload:
    return await call_next(request)

# 3. 非 end_user 角色放行
role = user_payload.get("role", "")
if role != Role.END_USER:
    return await call_next(request)

# 4. end_user 访问开发者 API → 403
for prefix in DEVELOPER_ONLY_PREFIXES:
    if path.startswith(prefix):
        return JSONResponse(status_code=403)
```

### 认证与鉴权分离

| 中间件 | 职责 | 没 JWT 时 |
|---|---|---|
| `AuthMiddleware` | 解析 JWT，设置上下文 | 放行（不拦截） |
| `AccessControlMiddleware` | 角色权限控制 | 放行（不管） |
| 路由层依赖（`get_current_user`等） | **真正拒绝未认证请求** | 抛 401 |

前两个都是"能过就过"，真正把未认证请求拦下来的是路由层的依赖函数。

## 3. 路由级依赖 — 认证验证

**文件位置**: `backend/app/auth/deps.py`

### get_current_user

验证用户是否已认证（不检查角色）。生产模式禁用 `X-User-ID` 回退。

```python
async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    # 1. JWT path
    user_payload = getattr(request.state, "user", None)
    if user_payload:
        # 从数据库查询用户
        return user

    # 2. 生产模式 → 直接拒绝，禁止 X-User-ID 回退
    if settings.is_production:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # 3. X-User-ID fallback (仅开发模式)
    x_user_id = request.headers.get("X-User-ID", "")
    if x_user_id:
        # 开发模式回退逻辑
        return user

    # 4. 都没有 → 401
    raise HTTPException(status_code=401, detail="Not authenticated")
```

### require_role — 依赖工厂

验证用户角色是否允许访问。项目真实路由示例：

```python
# backend/app/publish/router.py:43
@router.post("/agent/{agent_id}")
async def publish_agent(
    agent_id: str,
    body: PublishRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(Role.DEVELOPER)),  # ← 依赖工厂
) -> dict:
    """Publish or update an agent (developer only)."""
    ...
```

`require_role` 是依赖工厂——外层接收角色要求，内层执行验证：

```python
def require_role(*allowed_roles: str):
    async def _checker(
        user: User = Depends(get_current_user),  # 先认证
    ) -> User:
        if user.role not in allowed_roles:        # 再授权
            raise HTTPException(status_code=403)
        return user
    return _checker
```

FastAPI 处理请求时的执行顺序：

```
第 1 步：require_role(Role.DEVELOPER)  ← 外层函数先执行，传入角色
         │
         └─ 返回 _checker 函数（闭包，捕获了 allowed_roles = ["developer"]）

第 2 步：Depends(_checker)             ← 把返回的 _checker 当作依赖
         │
         └─ FastAPI 解析 _checker 的参数签名：
              user: User = Depends(get_current_user)
              └─ 先执行 get_current_user() → 拿到 user 对象

第 3 步：_checker(user=user)           ← 内层函数执行
         │
         ├─ user.role == "developer" → 通过，返回 user
         └─ user.role == "end_user"  → 抛 403
```

外层管"要什么"，内层管"怎么验"。`Depends` 拿到的是内层函数，FastAPI 只看内层的参数签名来注入依赖。这就是依赖工厂模式——用外层函数的参数来"定制"内层函数的行为。

## 4. 认证 vs 授权

| 函数 | 职责 | 检查内容 | 失败响应 |
|------|------|----------|----------|
| `get_current_user` | **认证** | 用户是否存在、token 是否有效 | 401 Unauthorized |
| `require_role` | **授权** | 用户角色是否允许 | 403 Forbidden |

## 5. 中间件注册顺序

**文件位置**: `backend/app/main.py`

```python
# Starlette 的 add_middleware 是反向包装的
# 最后添加的是最外层，最先执行
app.add_middleware(AccessControlMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(CORSMiddleware)
```

实际执行顺序：
1. CORSMiddleware（最外层）
2. AuthMiddleware（中间层，解码 JWT）
3. AccessControlMiddleware（最内层，角色检查）

## 6. 安全注意事项

### X-User-ID 回退机制

~~**问题**: 当前代码在任何环境都允许 X-User-ID 回退，存在安全风险。~~

**已修复**: 生产模式下已禁用 `X-User-ID` 回退，未认证请求直接返回 401。

```python
# 已实现：deps.py — get_current_user
if settings.is_production:
    raise HTTPException(status_code=401, detail="Not authenticated")

# 已实现：main.py — _platform_get_user_id
if settings.app_env == "production":
    raise HTTPException(status_code=401, detail="Authentication required")
```

| 函数 | 文件 | 生产模式处理 |
|---|---|---|
| `get_current_user` | `auth/deps.py` | ✅ 抛 401 |
| `_platform_get_user_id` | `main.py` | ✅ 抛 401 |

### 配置文件

**文件位置**: `backend/.env`

```env
APP_ENV=production  # 改为生产模式
```

## 7. 使用示例

### 前端请求

```typescript
// 有 JWT 时
headers['Authorization'] = `Bearer ${token}`;

// 无 JWT 时（开发模式）
headers['X-User-ID'] = userId;
```

### 路由使用

```python
# 只需要认证
@router.get("/profile")
async def get_profile(user: User = Depends(get_current_user)): ...

# 需要认证 + 授权
@router.post("/agent/create", dependencies=[Depends(require_role(Role.DEVELOPER))])
async def create_agent(): ...
```

## 8. 相关文件

- `backend/app/auth/middleware.py` — 中间件实现
- `backend/app/auth/deps.py` — 依赖注入函数
- `backend/app/auth/security.py` — JWT 工具函数
- `backend/app/auth/router.py` — 认证路由
- `backend/app/core/config.py` — 配置管理
