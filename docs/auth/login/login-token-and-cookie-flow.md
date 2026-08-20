# 登录接口：认证信息与权限 Cookie 处理流程

登录接口 `POST /auth/token` 完成两件事：返回 JWT token（在响应体中）和写入权限 Cookie（在响应头中）。

---

## 一、接口概览

```python
@router.post("/login")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
```

支持两种登录方式，按优先级依次尝试：

```
登录请求进入
  │
  ├─ OAuth 登录启用？→ 尝试 OAuth2.0 密码模式
  │     ├─ 成功 → 返回 token + 真实权限 Cookie
  │     └─ 失败（服务不可用）→ 回退到本地登录
  │
  └─ 本地密码登录启用？→ 验证本地数据库
        └─ 成功 → 返回 token + 模拟权限 Cookie
```

---

## 二、OAuth 登录路径

```python
if settings.is_oauth_enabled:
    auth_service = get_auth_service()
    result = await auth_service.login_with_oauth_password(
        body.username, body.password, db,
    )
```

### 响应体（JWT token）

OAuth 服务器返回的数据直接作为 JSON 响应体：

```json
{
    "access_token": "eyJhbG...",
    "refresh_token": "eyJhbG...",
    "user_id": "user_001",
    "username": "zhangsan",
    "role": "developer",
    "permissions": ["agent:publish", "agent:create", ...]
}
```

### 响应头（权限 Cookie）

从 OAuth 返回数据中提取 `permissions`，写入 Cookie：

```python
permissions = result.pop("permissions", [])
resp = JSONResponse(content=result)

if permissions:
    compressed = gzip.compress(json.dumps(permissions).encode())
    encoded = base64.b64encode(compressed).decode()
    chunk_size = 3800
    chunks = [encoded[i:i+chunk_size] for i in range(0, len(encoded), chunk_size)]

    for idx, chunk in enumerate(chunks):
        resp.set_cookie(
            key=f"user_permissions_{idx}",
            value=chunk,
            httponly=True,             # JS 不可读
            secure=settings.is_production,  # 生产环境仅 HTTPS
            samesite="strict",         # 防 CSRF
            max_age=settings.jwt_access_expire_minutes * 60,
        )
    resp.set_cookie(
        key="user_permissions_count",
        value=str(len(chunks)),
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
        max_age=settings.jwt_access_expire_minutes * 60,
    )
```

---

## 三、本地密码登录路径

```python
result = await db.execute(select(User).where(User.username == body.username))
user = result.scalar_one_or_none()

if not user or not verify_password(body.password, user.password_hash):
    raise HTTPException(status_code=401, detail="Incorrect username or password")
```

### 响应体（JWT token）

手动构造 token 数据：

```python
token_data = {
    "access_token": create_access_token(user.user_id, user.username, user.role),
    "refresh_token": create_refresh_token(user.user_id, user.username, user.role),
    "user_id": user.user_id,
    "username": user.username,
    "role": user.role,
}
```

### 响应头（模拟权限 Cookie）

本地登录写入硬编码的模拟权限，用于测试 Cookie 功能：

```python
mock_permissions = [
    "user:create", "user:view", "user:update", "user:delete",
    "role:create", "role:view", "role:update", "role:delete",
    "knowledge:save", "knowledge:update", "knowledge:delete",
    "agent:chat", "agent:config:create", "agent:config:update",
]
compressed = gzip.compress(json.dumps(mock_permissions).encode())
encoded = base64.b64encode(compressed).decode()

resp = JSONResponse(content=token_data)
resp.set_cookie(key="user_permissions_0", value=encoded, ...)
resp.set_cookie(key="user_permissions_count", value="1", ...)
```

---

## 四、响应结构对比

### 响应体（JSON）

两种登录方式返回的结构相同：

```json
{
    "access_token": "eyJhbG...",
    "refresh_token": "eyJhbG...",
    "user_id": "user_001",
    "username": "zhangsan",
    "role": "developer"
}
```

### 响应头（Set-Cookie）

```
HTTP/1.1 200 OK
Content-Type: application/json
Set-Cookie: user_permissions_count=3; HttpOnly; SameSite=Strict; Max-Age=3600
Set-Cookie: user_permissions_0=H4sI...; HttpOnly; SameSite=Strict; Max-Age=3600
Set-Cookie: user_permissions_1=AAAA...; HttpOnly; SameSite=Strict; Max-Age=3600
Set-Cookie: user_permissions_2=zzzz...; HttpOnly; SameSite=Strict; Max-Age=3600

{"access_token":"eyJhbG...","refresh_token":"eyJhbG...","user_id":"..."}
```

---

## 五、浏览器后续行为

### Authorization 头（前端手动设置）

```
登录响应 → 前端从响应体取出 access_token → 存入 localStorage
  → 后续每次请求前端手动加上：
      headers["Authorization"] = "Bearer eyJhbG..."
```

### 权限 Cookie（浏览器自动携带）

```
登录响应 → 浏览器从 Set-Cookie 响应头自动存储 Cookie
  → 后续每次请求浏览器自动带上：
      Cookie: user_permissions_count=3; user_permissions_0=H4sI...; ...
```

### 对比

| 信息 | 写入方 | 存储位置 | 携带方式 |
|---|---|---|---|
| `access_token` | 后端返回在响应体 | 前端存 localStorage | 前端手动加 `Authorization` 头 |
| 权限 Cookie | 后端 `set_cookie` 写入响应头 | 浏览器自动存储 | 浏览器自动携带 Cookie |

---

## 六、Cookie 安全属性说明

| 属性 | 值 | 作用 |
|---|---|---|
| `httponly=True` | JS 不可读 | 防止 XSS 攻击窃取 Cookie |
| `secure=True`（生产） | 仅 HTTPS 传输 | 防止明文传输泄露 |
| `samesite="strict"` | 同站请求才携带 | 防止 CSRF 攻击 |
| `max_age` | 与 JWT 过期时间一致 | Cookie 与 token 同步过期 |
