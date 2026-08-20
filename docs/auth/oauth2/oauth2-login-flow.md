# OAuth2.0 登录认证完整流程

## 流程总览

```
前端发送登录请求 (username + password)
    ↓
后端向认证系统请求 token
    ↓
用认证系统的 token 请求用户信息
    ↓
用认证系统的 token 请求权限信息
    ↓
同步本地用户（角色映射 + 数据库写入）
    ↓
签发本地 JWT（access_token + refresh_token）
    ↓
权限数据 gzip 压缩 + base64 编码 + 分片写入 Cookie
    ↓
响应回前端（token 在 body，权限在 Cookie）
```

---

## 第一步：前端发送登录请求

```
POST /auth/login
Content-Type: application/json

{"username": "admin", "password": "***"}
```

---

## 第二步：后端向认证系统请求 token

```
POST http://192.168.1.96:9623/oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=password&username=admin&password=***&client_id=619aa32b-...&client_secret=ZSMwfsJRQ9WkEcAv_Z__OQ
```

响应体：

```json
{
  "access_token": "***",
  "token_type": "bearer",
  "refresh_token": "***",
  "expires_in": 3599,
  "scope": "all"
}
```

---

## 第三步：用认证系统的 token 请求用户信息

```
GET http://192.168.1.96:9623/api/user/info
Authorization: Bearer <认证系统的 access_token>
```

响应体：

```json
{
  "status": 200,
  "message": "操作成功",
  "data": {
    "userId": 1,
    "username": "admin",
    "userAlias": "admin测试别名",
    "email": null,
    "phone": null,
    "gender": 1,
    "avatar": "http://192.168.1.96:9620/files?path=avatar/xxx.jpg",
    "lastLoginTime": "2026-08-14T08:35:46.703+00:00",
    "roleNames": ["管理员", "SuperRole", "教师", "学生", ...],
    "roleMap": {
      "1": "SuperRole",
      "7": "教师",
      "8": "学生",
      "25": "管理员",
      ...
    }
  }
}
```

---

## 第四步：用认证系统的 token 请求权限信息

```
GET http://192.168.1.96:9623/api/user/permissions
Authorization: Bearer <认证系统的 access_token>
```

响应体：

```json
{
  "status": 200,
  "message": "操作成功",
  "data": [
    "user:create",
    "user:view",
    "user:update",
    "user:delete",
    "role:create",
    "knowledge:save",
    ...
  ]
}
```

---

## 第五步：同步本地用户

从认证系统返回的用户信息中取字段，写入本地数据库：

| 认证系统字段 | 本地字段 | 说明 |
|---|---|---|
| `data.userId` → 转 str | `user_id` | 统一认证系统的用户 ID |
| `data.username` + `_oauth` | `username` | 加 `_oauth` 后缀避免冲突 |
| `data.email` | `email` | 可能为 null |
| `data.userAlias` 或 `data.username` | `name` | 显示名称 |
| `data.roleMap` 的 key 与 `.env` 配置比对 | `role` | developer / end_user |

### 角色映射逻辑

```
roleMap 的 key: {1, 7, 8, 25, ...}
.env ROLE_DEVELOPER_IDS=1,25,315
.env ROLE_END_USER_IDS=8

比对流程：
  1. roleMap 的 key 与 ROLE_DEVELOPER_IDS 取交集 → 有交集 → developer
  2. roleMap 的 key 与 ROLE_END_USER_IDS 取交集 → 有交集 → end_user
  3. 都没有 → 默认 end_user
```

### 数据库查重

- 按 `oauth_provider` + `oauth_uid` 查 → 已有则更新基本信息和角色
- 按 `username` 查 → 被占用则返回 409
- 都没有 → 创建新用户

---

## 第六步：签发本地 JWT

### access_token 载荷

```python
{
    "sub": user_id,           # 本地数据库用户 ID
    "username": "admin",
    "role": "developer",
    "roles": ["developer"],
    "permissions": [],
    "exp": now + 30分钟,
    "iat": now,
    "iss": "agent-platform",
    "type": "access"
}
```

### refresh_token 载荷

```python
{
    "sub": user_id,
    "username": "admin",
    "role": "developer",
    "roles": ["developer"],
    "permissions": [],
    "exp": now + 7天,
    "iat": now,
    "iss": "agent-platform",
    "type": "refresh"
}
```

### 签证

```python
# access_token
jwt.encode(access_payload, secret_key, algorithm="HS256")

# refresh_token
jwt.encode(refresh_payload, secret_key, algorithm="HS256")
```

---

## 第七步：权限数据压缩写入 Cookie

```python
permissions = ["user:create", "role:update", ...]  # 可能 1000+ 条

# 1. JSON 序列化
json_str = json.dumps(permissions)

# 2. gzip 压缩
compressed = gzip.compress(json_str.encode())

# 3. base64 编码
encoded = base64.b64encode(compressed).decode()

# 4. 分片（每片最大 3800 字节，cookie 有 4KB 限制）
chunks = [encoded[i:i+3800] for i in range(0, len(encoded), 3800)]
```

### Cookie 设置

| Cookie 名 | 值 | 属性 |
|---|---|---|
| `user_permissions_0` | 分片 0 的 base64 数据 | `HttpOnly=true; SameSite=strict` |
| `user_permissions_1` | 分片 1（如有） | `HttpOnly=true; SameSite=strict` |
| `user_permissions_count` | 分片总数（如 "3"） | `HttpOnly=true; SameSite=strict` |

安全属性：
- `HttpOnly=true`：JavaScript 无法读取，防 XSS 攻击
- `SameSite=strict`：跨站请求不携带，防 CSRF 攻击
- `Secure`：生产环境启用 HTTPS 时设置

---

## 第八步：响应回前端

```
HTTP/1.1 200 OK
Content-Type: application/json
Set-Cookie: user_permissions_0="H4sIA..."; HttpOnly; Max-Age=1800; SameSite=strict
Set-Cookie: user_permissions_1="H4sIA..."; HttpOnly; Max-Age=1800; SameSite=strict
Set-Cookie: user_permissions_count=2; HttpOnly; Max-Age=1800; SameSite=strict
```

响应体：

```json
{
  "access_token": "***",
  "refresh_token": "***",
  "token_type": "bearer",
  "user_id": "xxx",
  "username": "admin",
  "role": "developer"
}
```

### 前端处理

1. 从响应体取出 `access_token` 和 `refresh_token`，存入 `localStorage`
2. 浏览器自动存储响应头中的 Cookie（权限数据）
3. 之后每次请求：`Authorization: Bearer <access_token>`
4. access_token 过期（30分钟）→ 用 refresh_token 换新 token

---

## 两套 token 的区别

| | 认证系统的 token | 本地签发的 JWT |
|---|---|---|
| 签发方 | 公司统一认证系统 | agent-platform 后端 |
| 用途 | 向认证系统请求用户信息和权限 | 本地 API 身份验证 |
| 存储 | 后端临时使用，不存 | 前端 localStorage |
| 有效期 | 3599 秒 | access 30分钟 / refresh 7天 |
| 携带方式 | 后端内部请求认证系统时带上 | 前端每次请求放 Authorization 头 |
