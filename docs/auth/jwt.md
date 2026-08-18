# JWT（JSON Web Token）

## 结构

JWT 就三部分，用 `.` 连接：

```
base64(头部).base64(载荷).签名
```

| 部分 | 内容 | 作用 |
|---|---|---|
| 头部 | `{"alg": "HS256", "typ": "JWT"}` | 声明算法 |
| 载荷 | `{"sub": "用户ID", "role": "developer", "exp": ...}` | 存放数据 |
| 签名 | `HMAC-SHA256(头部+载荷, 密钥)` | 防篡改 |

## 特性

- **可读**：任何人拿到 JWT 都能 base64 解码看载荷内容
- **不可改**：改了数据签名就对不上，后端会拒绝
- **密钥唯一**：密钥只有后端有，所以只有后端能签发和验证

## 生成过程

登录成功后，后端签发 JWT。以 `access_token` 为例：

### 第一步：构造载荷（Payload）

**access_token 载荷：**

```python
{
    "sub": user_id,           # 用户唯一标识
    "username": "admin",      # 用户名
    "role": "developer",      # 角色（developer / end_user）
    "roles": ["developer"],   # 角色列表
    "permissions": [],        # 权限列表（预留字段）
    "exp": 1723700000,        # 过期时间（当前时间 + 30分钟）
    "iat": 1723698200,        # 签发时间
    "iss": "agent-platform",  # 签发者
    "type": "access",         # token 类型
}
```

**refresh_token 载荷：**

```python
{
    "sub": user_id,           # 用户唯一标识
    "username": "admin",      # 用户名
    "role": "developer",      # 角色（developer / end_user）
    "roles": ["developer"],   # 角色列表
    "permissions": [],        # 权限列表（预留字段）
    "exp": 1724303000,        # 过期时间（当前时间 + 7天）
    "iat": 1723698200,        # 签发时间
    "iss": "agent-platform",  # 签发者
    "type": "refresh",        # token 类型
}
```

两者区别仅在 `type` 和 `exp`：

### 第二步：编码 + 签名

```python
jwt.encode(payload, secret_key, algorithm="HS256")
```

内部执行：
1. 把头部 `{"alg": "HS256", "typ": "JWT"}` 转 JSON → base64 编码
2. 把 payload 转 JSON → base64 编码
3. 用密钥对 `base64(头部).base64(载荷)` 做 HMAC-SHA256 签名
4. 三部分用 `.` 拼接

最终输出类似：`eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.XXXXX`

### 第三步：返回给前端

登录响应包含返回头和返回体两部分：

```
HTTP/1.1 200 OK                          ← 返回头
Content-Type: application/json            ← 返回头
Set-Cookie: user_permissions_0=...        ← 返回头（Cookie）

{"access_token": "eyJhbG...xxx",         ← 返回体（JSON）
 "refresh_token": "eyJhbG...yyy",
 "token_type": "bearer",
 "user_id": "xxx",
 "username": "admin",
 "role": "developer"}
```

前端 JS 从返回体中取出两个 token，存入 `localStorage`。

## 携带 token 请求

前端每次请求在请求头中携带 token：

```
Authorization: Bearer eyJhbG...xxx
```

后端 `AuthMiddleware` 中间件自动执行：

### 第一步：提取 token

```python
auth_header = request.headers.get("Authorization", "")
token = "Bearer eyJhbG..." → 提取出 "eyJhbG..."
```

### 第二步：解码 + 验证

```python
jwt.decode(token, secret_key, algorithms=["HS256"], issuer="agent-platform")
```

内部执行：
1. 按 `.` 拆分成三部分
2. 对头部和载荷部分用同样的密钥重新计算签名
3. 对比签名是否一致 → 不一致则拒绝（被篡改）
4. 检查 `exp` 是否过期 → 过期则拒绝
5. 检查 `iss` 是否为 `agent-platform` → 不匹配则拒绝
6. 全部通过，返回 payload 字典

### 第三步：存入请求上下文

```python
request.state.user = payload  # {"sub": "用户ID", "username": "admin", "role": "developer", ...}
```

后续所有依赖函数从 `request.state.user` 提取 user_id，完成身份识别。

## 完整流程图

```
登录请求 (username + password)
    ↓
后端验证密码
    ↓
构造 payload (sub, role, exp, ...)
    ↓
jwt.encode(payload, 密钥) → 生成 JWT 字符串
    ↓
返回给前端 {access_token, refresh_token}
    ↓
前端存储 token
    ↓
后续每个请求: Authorization: Bearer <token>
    ↓
AuthMiddleware 解码 + 验证签名 + 检查过期
    ↓
存入 request.state.user
    ↓
接口从 request.state.user 提取 user_id 进行业务逻辑
```

## Token 刷新机制

只有 **access_token** 放到请求头里，refresh_token 存在 localStorage 里不动，只在 access_token 过期时才用：

```
正常请求: Authorization: Bearer <access_token>

access_token 过期（返回 401）
    ↓
前端自动请求: POST /auth/refresh
Body: {"refresh_token": "eyJhbG...yyy"}
    ↓
后端验证 refresh_token，返回新的 {access_token, refresh_token}
    ↓
前端更新 localStorage，用新 token 继续请求
```

两个 token 各有各的用途，不混用：
- **access_token**：每次请求携带，短期有效（30分钟），用于身份验证
- **refresh_token**：仅用于换新 token，长期有效（7天），不参与业务请求

## 配置

| 变量 | 默认值 | 说明 |
|---|---|---|
| `JWT_SECRET_KEY` | `agent-platform-dev-secret-...` | 签名密钥（生产环境务必修改） |
| `JWT_ALGORITHM` | `HS256` | 签名算法 |
| `JWT_ACCESS_EXPIRE_MINUTES` | `30` | access_token 有效期（分钟） |
| `JWT_REFRESH_EXPIRE_DAYS` | `7` | refresh_token 有效期（天） |
