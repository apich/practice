# user_id 认证链路：从 JWT 到 Storage 层

agentscope 框架的 `get_current_user_id` 默认从 `X-User-ID` 请求头读取用户身份（开发模式）。
项目通过 FastAPI `dependency_overrides` 覆盖为优先从 JWT 解析，确保生产环境安全。

---

## 1. AuthMiddleware — 解析 JWT，写入 request.state

`backend/app/auth/middleware.py:79`：

```python
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        token = extract_bearer_token(request.headers.get("Authorization", ""))
        user_payload = None

        if token:
            payload = decode_token(token)
            if payload and payload.get("type") == "access":
                user_payload = payload                      # JWT 解析成功

        request.state.user = user_payload                   # 写入 request.state
        return await call_next(request)
```

---

## 2. 依赖覆盖 — 优先 JWT，回退 header

`backend/app/main.py:237`：

```python
from agentscope.app.deps import get_current_user_id as _default_get_user_id

async def _platform_get_user_id(request: FastAPIRequest) -> str:
    user_payload = getattr(request.state, "user", None)
    if user_payload:
        return user_payload.get("sub", "")       # ← JWT 的 sub 字段（生产）
    return request.headers.get("X-User-ID", "")  # ← header 回退（开发）

app.dependency_overrides[_default_get_user_id] = _platform_get_user_id
```

---

## 3. agentscope 路由 — 使用被覆盖后的依赖

```python
# _session.py:295 — 这里的 get_current_user_id 实际执行的是 _platform_get_user_id
async def create_session(
    body: CreateSessionRequest,
    user_id: str = Depends(get_current_user_id),  # ← 已被覆盖
    ...
):
```

---

## 时序

```
请求进入
  → AuthMiddleware.dispatch()
    → 有 JWT？解码写入 request.state.user = {"sub": "user123", "role": "developer", ...}
    → 没 JWT？request.state.user = None
  → agentscope 路由触发 Depends(get_current_user_id)
    → 实际执行 _platform_get_user_id()
      → request.state.user 存在？返回 sub = "user123"（生产）
      → 不存在？返回 X-User-ID header 值（开发回退）
  → user_id 传入 storage 层
```
