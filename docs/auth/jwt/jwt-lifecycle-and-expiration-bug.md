# JWT 生命周期与过期导致 user_id 为空的 Bug 分析

## 目录

- [1. JWT 怎么来的](#1-jwt-怎么来的)
- [2. 怎么确定 JWT 过期了](#2-怎么确定-jwt-过期了)
- [3. 重新登录会复用旧 JWT 吗](#3-重新登录会复用旧-jwt-吗)
- [4. Bug 触发场景复现](#4-bug-触发场景复现)
- [5. 过期后 decode_token 返回 None 的处理链路](#5-过期后-decode_token-返回-none-的处理链路)
- [6. 后端 raise 401 如何触发前端跳转登录页](#6-后端-raise-401-如何触发前端跳转登录页)
- [7. 如果1分钟内就触发了 Bug](#7-如果1分钟内就触发了-bug)

---

## 1. JWT 怎么来的

当用户通过 OAuth 登录时，完整流程如下：

```
用户输入账号密码
    ↓
POST /auth/login  (前端 → 后端)
    ↓
login_with_oauth_password()  (后端 → 公司认证服务器)
    ↓
_exchange_password_token()   ← 向公司 OAuth 服务器换取 access_token
    ↓
_fetch_oauth_userinfo()      ← 用 access_token 获取用户信息
    ↓
_sync_oauth_user()           ← 同步用户到本地 DB（首次创建 or 更新）
    ↓
_generate_jwt_token(user)    ← 签发本地 JWT
    ↓
返回 { access_token, refresh_token, user_id, username, role }
    ↓
前端 localStorage.setItem('access_token', tokens.access_token)
```

### 签发代码

[backend/app/auth/service.py:105-157](../../backend/app/auth/service.py#L105-L157)：

```python
def _generate_jwt_token(self, user: User) -> dict:
    now = int(time.time())
    access_expire = self._settings.jwt_access_expire_minutes  # 默认 30 分钟

    access_payload = {
        "sub": user.user_id,    # ← 用户 UUID
        "exp": now + access_expire * 60,  # ← 过期时间戳
        "type": "access",
        ...
    }
    access_token = jwt.encode(access_payload, settings.jwt_secret_key, algorithm="HS256")
```

### 前端存储

[frontend/src/api/auth.ts:39-64](../../frontend/src/api/auth.ts#L39-L64)：

```typescript
login: async (username, password) => {
    const tokens = await client.post('/auth/login', { username, password });
    localStorage.setItem('access_token', tokens.access_token);
    localStorage.setItem('refresh_token', tokens.refresh_token);
    localStorage.setItem('user_id', tokens.user_id);
    localStorage.setItem('username', tokens.username);
    return tokens;
}
```

## 2. 怎么确定 JWT 过期了

JWT 里内嵌了 `exp`（过期时间戳），验证时**直接本地检查，不需要网络请求**：

[backend/app/auth/security.py:126-140](../../backend/app/auth/security.py#L126-L140)：

```python
def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"], issuer="agent-platform")
    except jwt.PyJWTError:   # ← 包括 ExpiredSignatureError
        return None           # ← 过期 or 无效都返回 None
```

### 浏览器控制台验证

在浏览器控制台执行以下代码可以查看当前 JWT 的状态：

```javascript
const token = localStorage.getItem('access_token');
if (token) {
    const payload = JSON.parse(atob(token.split('.')[1]));
    console.log('签发时间:', new Date(payload.iat * 1000));
    console.log('过期时间:', new Date(payload.exp * 1000));
    console.log('当前时间:', new Date());
    console.log('是否过期:', Date.now() > payload.exp * 1000);
} else {
    console.log('access_token 不存在');
}
```

## 3. 重新登录会复用旧 JWT 吗？

**不会。** 每次登录都签发全新的 JWT。

后端 `_generate_jwt_token` 每次都用 `now = int(time.time())` 重新计算 `exp`，
前端 `login()` 也会覆盖写入 localStorage，所以第二次登录的 JWT 和第一次完全不同，
过期时间也重新计算。

## 4. Bug 触发场景复现

### 用户操作路径

```
1. 连接公司 WiFi
2. OAuth 登录 agent-platform（成功，获得 JWT，有效期 30 分钟）
3. 重定向到 admin/chat 页面
4. 切换到非公司网络
5. 创建智能体
6. agents 表中 user_id 为空字符串 ""
```

### 时间线分析

```
T+0min   连接公司WiFi → OAuth登录成功 → 获得JWT（exp = T+30min）
T+0min   重定向到 admin/chat
T+?min   切换网络（此时 JWT 仍在有效期内）
T+30min  JWT 过期 → decode_token() 返回 None → request.state.user = None
         → _platform_get_user_id() 返回 "" → 写入 agents 表的 user_id 为空
```

### 执行链路（JWT 过期时）

```
前端发送请求:
  buildHeaders() → getAccessToken() → 从 localStorage 读取 JWT（已过期）
  → 设置 Authorization: Bearer <expired_jwt>

后端处理:
  AuthMiddleware.dispatch()
    → extract_bearer_token() → 提取 token
    → decode_token(token) → jwt.PyJWTError → 返回 None
    → request.state.user = None

  agentscope 路由 (POST /agent/):
    → get_current_user_id 依赖被 override 为 _platform_get_user_id
    → _platform_get_user_id():
        request.state.user = None → 跳过 JWT 分支
        settings.is_production = False → 跳过生产模式检查
        request.headers.get("X-User-ID", "") → 前端未发送 X-User-ID → 返回 ""
    → user_id = ""
    → AgentRecord(user_id="", ...) → 写入数据库
```

### 根本原因

[backend/app/main.py:237-248](../../backend/app/main.py#L237-L248) 中 `_platform_get_user_id` 的覆盖逻辑：

```python
async def _platform_get_user_id(request: FastAPIRequest) -> str:
    user_payload = getattr(request.state, "user", None)
    if user_payload:
        return user_payload.get("sub", "")
    if settings.is_production:
        raise HTTPException(status_code=401, ...)  # 生产模式会报错
    return request.headers.get("X-User-ID", "")    # 开发模式返回空字符串
```

对比 agentscope 原版（会抛出 401）：

```python
async def get_current_user_id(x_user_id: str = Header(...)) -> str:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-ID header is required.")
    return x_user_id
```

| 层级 | 问题 |
|---|---|
| **后端覆盖** | `_platform_get_user_id` 在开发模式下允许空字符串通过，而非报错 |
| **前端** | 不检查 JWT 是否过期就发送；没有自动刷新 token 机制 |
| **数据库约束** | `nullable=False` 只防 NULL，不防空字符串 `""` |

## 5. 过期后 decode_token 返回 None 的处理链路

JWT 过期后，`decode_token` 返回 `None`，之后的处理流程如下：

### Step 1 — AuthMiddleware（[middleware.py:79-117](../../backend/app/auth/middleware.py#L79-L117)）

```python
async def dispatch(self, request: Request, call_next):
    auth_header = request.headers.get("Authorization", "")
    token = extract_bearer_token(auth_header)        # 提取出过期 JWT

    user_payload: Optional[dict] = None

    if token:
        payload = decode_token(token)                 # 过期 → 返回 None
        if payload and payload.get("type") == "access":
            user_payload = payload                    # 不执行，user_payload 仍为 None

    request.state.user = user_payload                 # ← 设为 None
    return await call_next(request)                   # ← 继续处理请求，不拦截
```

**关键点：中间件不会返回 401，请求继续往下走。**

### Step 2 — 路由依赖注入（[main.py:237-248](../../backend/app/main.py#L237-L248)）

```python
async def _platform_get_user_id(request: FastAPIRequest) -> str:
    user_payload = getattr(request.state, "user", None)  # None
    if user_payload:                                       # False，跳过
        return user_payload.get("sub", "")
    if settings.is_production:                             # 开发模式，跳过
        raise HTTPException(status_code=401, ...)
    return request.headers.get("X-User-ID", "")           # 返回 ""
```

### Step 3 — agentscope 路由

```python
# _agent.py create_agent()
user_id = Depends(get_current_user_id)   # user_id = ""
record = AgentRecord(user_id=user_id, data=data)  # user_id="" 写入数据库
```

### 完整链路总结

```
JWT 过期
  → decode_token() 返回 None
  → AuthMiddleware 静默放行（request.state.user = None）
  → _platform_get_user_id() 发现无 JWT payload
  → 开发模式下返回 ""（生产模式会报 401）
  → agents/sessions 表写入 user_id = ""
```

中间件和路由依赖**都不拦截**，直接把空字符串当作合法的 `user_id` 写入了数据库。

### user_payload 有效时 sub 一定存在

`user_payload` 有值意味着以下两个条件都满足：

1. `decode_token(token)` 成功返回（签名有效 + 未过期）
2. `payload.get("type") == "access"`（是 access token）

而这个 payload 一定是 `_generate_jwt_token` 生成的，签发时 `sub` 是必填字段：

```python
# service.py:115-126
access_payload = {
    "sub": user.user_id,    # ← 必填，来自数据库 UUID，不可能为空
    "username": user.username,
    "role": user.role,
    "roles": [user.role],
    "permissions": DEFAULT_PERMISSIONS,
    "auth_type": getattr(user, "auth_type", "password"),
    "iat": now,
    "exp": now + access_expire * 60,
    "iss": "agent-platform",
    "type": "access",
}
```

`user.user_id` 是数据库自动生成的 UUID（`default=lambda: str(uuid.uuid4())`），不可能为空。

所以：**`user_payload` 有值 → `sub` 一定存在且非空 → `return user_payload.get("sub", "")` 一定能拿到有效的 user_id。**

## 6. 后端 raise 401 如何触发前端跳转登录页

当后端 `raise HTTPException(status_code=401)` 时，前端会自动清除登录态并跳转到登录页。

### 完整链路

**后端抛出 401：**

```python
raise HTTPException(status_code=401, detail="Authentication required", ...)
```

**前端 `client.ts` 捕获**（[client.ts:158-170](../../frontend/src/api/client.ts#L158-L170)）：

```typescript
if (!res.ok) {
    const detail = await extractErrorDetail(res);
    const error = new ApiError(res.status, detail);

    // 401 → 清除登录状态 + 跳转 /login
    if (res.status === 401 && !path.startsWith('/auth/')) {
        clearAuthAndRedirect();   // ← 这里触发
    }

    if (!silent) toast.error(detail);  // ← 弹出错误提示
    throw error;
}
```

**`clearAuthAndRedirect` 执行**（[client.ts:34-41](../../frontend/src/api/client.ts#L34-L41)）：

```typescript
export function clearAuthAndRedirect() {
    localStorage.removeItem('access_token');   // 清除 JWT
    localStorage.removeItem('refresh_token');  // 清除 refresh token
    localStorage.removeItem('user_info');      // 清除用户信息
    localStorage.removeItem('user_id');
    localStorage.removeItem('username');
    if (window.location.pathname !== '/login') {
        window.location.href = '/login';       // 跳转登录页
    }
}
```

### 总结

```
后端 raise 401
  → 前端收到 HTTP 401 响应
  → clearAuthAndRedirect()
  → 清除 localStorage 全部登录态（access_token / refresh_token / user_info / user_id / username）
  → window.location.href = '/login'
  → 用户需要重新登录
```

## 7. 如果1分钟内就触发了 Bug

如果从登录到创建智能体不超过 1 分钟，JWT 不应该过期（有效期 30 分钟）。
此时问题可能是 **JWT 根本没被存储到 localStorage**。

### 排查方法

在浏览器控制台执行：

```javascript
console.log('access_token:', localStorage.getItem('access_token') ? '存在' : '不存在');
console.log('user_id:', localStorage.getItem('user_id'));
console.log('username:', localStorage.getItem('username'));
```

如果 `access_token` 为空，说明 OAuth 回调过程中 token 没有被正确保存。
可能原因：切换网络导致 OAuth 回调请求（`POST /auth/callback`）失败，
前端没有收到 token 响应，自然无法写入 localStorage。

### OAuth 回调失败的场景

```
T+0s    在公司WiFi上发起 OAuth 登录
T+1s    被重定向到公司认证服务器（仍在公司WiFi）
T+5s    认证成功，认证服务器重定向回前端（redirect_uri 带 code+state）
T+6s    此时切换网络！
T+7s    前端发起 POST /auth/callback {code, state}
        → 后端收到请求
        → 后端调用 _exchange_oauth_token(code, code_verifier)
        → 后端向公司认证服务器发 HTTP 请求 ← 此时已不在公司网络！
        → httpx.RequestError: Unable to reach auth server
        → 后端返回错误给前端
        → 前端没有收到 token → localStorage 为空
T+8s    用户手动导航到 /admin/chat（页面已缓存或有残留状态）
T+9s    创建智能体 → 前端没有 JWT → 不发送 Authorization header
        → 后端 _platform_get_user_id() 返回 "" → user_id 为空
```

这种情况下用户通常会看到错误提示（如 "Unable to reach auth server"），
但可能忽略了错误信息，直接在浏览器地址栏输入 `/admin/chat` 访问了页面。
