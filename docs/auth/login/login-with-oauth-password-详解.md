# `login_with_oauth_password` 函数源码详解

本文档逐行分析 OAuth2.0 密码模式登录的完整执行流程。

---

## 1. 函数签名

```python
# service.py:356-393
async def login_with_oauth_password(
    self,
    username: str,       # 用户名
    password: str,       # 密码
    db: AsyncSession,    # 数据库会话
) -> dict[str, Any] | None:
```

- 返回 `dict`：包含 JWT token 信息 + 权限列表
- 返回 `None`：OAuth 未启用时
- 抛出 `ValueError`：认证失败时

---

## 2. 调用入口

由 [router.py:136-185](../../backend/app/auth/router.py#L136-L185) 的 `/auth/login` 端点调用：

```
前端 POST /auth/login {username, password}
    │
    ▼
router.login()
    │
    ├─ settings.is_oauth_enabled ?
    │   ├─ True  → auth_service.login_with_oauth_password(username, password, db)
    │   └─ False → 走本地 bcrypt 校验
    │
    ├─ 返回 result（dict）→ 提取 permissions 写入 Cookie → 返回 JWT
    └─ 抛出 ValueError → 根据错误消息决定是否 fallback 到本地验证
```

---

## 3. 五步执行流程

### 第 1 步：检查 OAuth 是否启用（[L375-376](../../backend/app/auth/service.py#L375-L376)）

```python
if not self._settings.is_oauth_enabled:
    return None
```

检查 `.env` 中 `OAUTH_AUTH_SERVER_URL` 是否非空。为空则返回 `None`，router 收到 `None` 后走本地密码校验。

本例中 `OAUTH_AUTH_SERVER_URL=http://192.168.1.96:9623`，OAuth 已启用。

---

### 第 2 步：换取 OAuth access_token（[L378-379](../../backend/app/auth/service.py#L378-L379)）

```python
oauth_token = await self._exchange_password_token(username, password)
```

调用 [_exchange_password_token](../../backend/app/auth/service.py#L161-L207)，向认证系统发送：

```
POST http://192.168.1.96:9623/oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=password
&username=lizijian999
&password=abcd1234
&client_id=619aa32b-60b5-4f99-8664-5bbd963bbda7
&client_secret=ZSMwfsJRQ9WkEcAv_Z__OQ
&scope=openid profile email
```

成功响应：

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9...",
  "token_type": "PASSWORD",
  "expires_in": 28800
}
```

失败时抛出 `ValueError`：
- 401 → `"用户名或密码错误"`
- 400 → `"Authentication failed: 400"`
- 连接失败 → `"Unable to reach auth server"`

---

### 第 3 步：获取用户信息（[L381-382](../../backend/app/auth/service.py#L381-L382)）

```python
oauth_user_info = await self._fetch_oauth_userinfo(oauth_token["access_token"])
```

调用 [_fetch_oauth_userinfo](../../backend/app/auth/service.py#L209-L243)，用上一步的 `access_token` 请求：

```
GET http://192.168.1.96:9623/api/user/info
Authorization: Bearer {access_token}
```

成功响应：

```json
{
  "status": 200,
  "message": "操作成功",
  "data": {
    "userId": 43801463732,
    "username": "lizijian999",
    "userAlias": "lizijian999",
    "email": null,
    "roleMap": {"8": "学生", "315": "开发者"},
    ...
  }
}
```

---

### 第 4 步：同步用户到本地（[L384-385](../../backend/app/auth/service.py#L384-L385)）

```python
user = await self._sync_oauth_user(oauth_user_info, db)
```

调用 [_sync_oauth_user](../../backend/app/auth/service.py#L272-L354)，以下是逐段源码精讲：

#### 4.1 解包嵌套响应（[L288-292](../../backend/app/auth/service.py#L288-L292)）

```python
# 兼容两种 userinfo 响应格式：
# - 嵌套结构：{ "status": 200, "data": { "userId": ..., ... } }  ← 本例
# - 扁平结构：{ "user_id"/"sub": ..., "username": ..., ... }
if "data" in oauth_info and isinstance(oauth_info["data"], dict):
    info = oauth_info["data"]          # info = {"userId": 43801463732, "username": "lizijian999", ...}
else:
    info = oauth_info
```

本例认证系统返回 `{"status": 200, "data": {...}}` 嵌套结构，命中 `if` 分支，`info` 指向 `data` 层。

#### 4.2 提取用户唯一标识（[L294-303](../../backend/app/auth/service.py#L294-L303)）

```python
oauth_user_id = str(
    info.get("user_id")       # None（字段名不匹配）
    or info.get("userId")      # ← 命中，值为 43801463732
    or info.get("sub")         # 跳过
    or info.get("id")          # 跳过
    or ""
)
if not oauth_user_id:
    raise ValueError("OAuth userinfo missing user_id")  # 兜底：四个字段全空则报错
```

使用 `or` 短路求值，兼容四种常见字段名（`user_id` / `userId` / `sub` / `id`），取第一个非空值。本例命中 `userId`，得到 `"43801463732"`。

#### 4.3 提取其他字段（[L305-312](../../backend/app/auth/service.py#L305-L312)）

```python
# provider：认证系统未返回此字段，默认 "default"
oauth_provider = info.get("provider", "default")    # "default"

# username：优先取 username，其次 preferred_username，兜底用 oauth_{userId}
username = (
    info.get("username")               # ← 命中，值为 "lizijian999"
    or info.get("preferred_username")
    or f"oauth_{oauth_user_id}"        # 兜底：如 "oauth_43801463732"
)

# email：直接取，可能为 null
email = info.get("email")             # null

# name：优先取 name，其次 userAlias / alias，兜底用 username
name = (
    info.get("name")                   # None
    or info.get("userAlias")           # ← 命中，值为 "lizijian999"
    or info.get("alias")
    or username
)
```

本例提取结果：

| 变量 | 值 | 来源字段 |
|---|---|---|
| `oauth_user_id` | `"43801463732"` | `data.userId` |
| `oauth_provider` | `"default"` | 未返回，取默认值 |
| `username` | `"lizijian999"` | `data.username` |
| `email` | `null` | `data.email` |
| `name` | `"lizijian999"` | `data.userAlias` |

#### 4.4 按 oauth_user_id + provider 查找本地用户（[L314-320](../../backend/app/auth/service.py#L314-L320)）

```python
stmt = select(User).where(
    User.oauth_user_id == oauth_user_id,   # "43801463732"
    User.oauth_provider == oauth_provider, # "default"
)
result = await db.execute(stmt)
user = result.scalar_one_or_none()
```

查询条件：`oauth_user_id = "43801463732" AND oauth_provider = "default"`。

- 首次登录：查不到 → `user = None`，走新建分支
- 非首次：查到已有记录 → 走更新分支

#### 4.5 分支 A：用户已存在 → 更新（[L322-329](../../backend/app/auth/service.py#L322-L329)）

```python
if user is not None:
    user.email = email                           # 更新邮箱
    user.name = name                             # 更新显示名
    user.role = self._resolve_oauth_role(info)   # 重新判定角色（roleMap 可能变了）
    await db.commit()
    await db.refresh(user)
    return user
```

每次登录都同步最新信息，包括重新判定角色。如果认证系统中该用户的角色变了，本地会跟着更新。

#### 4.6 分支 B：用户不存在 → 新建（[L331-354](../../backend/app/auth/service.py#L331-L354)）

```python
# ① 判定角色
role = self._resolve_oauth_role(info)    # "end_user"（详见下方精讲）

# ② 检查 username 是否被本地密码登录用户占用
stmt_username = select(User).where(User.username == username)
result_username = await db.execute(stmt_username)
if result_username.scalar_one_or_none() is not None:
    # 被占用 → 在 username 后追加 userId 前8位避免冲突
    username = f"{username}_{oauth_user_id[:8]}"   # 如 "lizijian999_43801463"

# ③ 创建新用户
user = User(
    username=username,           # "lizijian999"
    password_hash="",            # OAuth 用户无本地密码
    role=role,                   # "end_user"
    auth_type="oauth",           # 标记为 OAuth 用户
    oauth_user_id=oauth_user_id, # "43801463732"
    oauth_provider=oauth_provider, # "default"
    email=email,                 # null
    name=name,                   # "lizijian999"
)
db.add(user)
await db.commit()
await db.refresh(user)
return user
```

**username 冲突处理逻辑**：如果本地已有一个 `lizijian999` 的密码登录用户，OAuth 用户会改名为 `lizijian999_43801463`（取 userId 前 8 位），避免两个用户 username 撞车。

---

#### 附：`_resolve_oauth_role` 精讲（[L80-103](../../backend/app/auth/service.py#L80-L103)）

此函数将认证系统的 `roleMap` 映射为本地角色（`developer` / `end_user`）。

```python
def _resolve_oauth_role(self, info: dict[str, Any]) -> str:
    settings = self._settings

    # ① 取 roleMap 的所有 key（角色 ID）
    role_map = info.get("roleMap", {})       # {"8": "学生", "315": "开发者"}
    user_role_ids = set(role_map.keys())     # {"8", "315"}

    # ② 读取 .env 中的角色 ID 映射配置
    developer_ids = {
        s.strip() for s in settings.role_developer_ids.split(",") if s.strip()
        # "1,25,301" → {"1", "25", "301"}
    }
    end_user_ids = {
        s.strip() for s in settings.role_end_user_ids.split(",") if s.strip()
        # "8" → {"8"}
    }

    # ③ 优先判断 developer（优先级高于 end_user）
    if developer_ids and user_role_ids & developer_ids:     # {"8","315"} ∩ {"1","25","301"} = ∅
        return Role.DEVELOPER                                # 不命中，跳过

    # ④ 再判断 end_user
    if end_user_ids and user_role_ids & end_user_ids:       # {"8","315"} ∩ {"8"} = {"8"}
        return Role.END_USER                                 # ✅ 命中，返回 "end_user"

    # ⑤ 都未命中，默认 end_user
    return Role.END_USER
```

**判定规则：**

| 优先级 | 判断 | 条件 | 本例结果 |
|---|---|---|---|
| 1 | developer | roleMap key ∩ ROLE_DEVELOPER_IDS ≠ ∅ | ❌ `{"8","315"} ∩ {"1","25","301"} = ∅` |
| 2 | end_user | roleMap key ∩ ROLE_END_USER_IDS ≠ ∅ | ✅ `{"8","315"} ∩ {"8"} = {"8"}` |
| 3 | 默认 | 都未命中 | — |

**关键设计点：**

1. **只看 roleMap 的 key，不看 value**：`{"8": "学生"}` 中的 `"学生"` 被忽略，只用 `"8"` 做匹配。
2. **优先判断 developer**：如果一个用户同时命中 developer 和 end_user（roleMap key 既有 1 又有 8），结果是 developer。
3. **默认 end_user**：如果 `.env` 中未配置 `ROLE_DEVELOPER_IDS` 和 `ROLE_END_USER_IDS`，或者用户的 roleMap key 与两者都无交集，一律返回 `end_user`。
4. **空 roleMap 处理**：`info.get("roleMap", {})` 返回空 dict，`user_role_ids` 为空集，任何交集都为空，最终返回默认的 `end_user`。

---

### 第 5 步：获取权限并签发本地 JWT（[L387-393](../../backend/app/auth/service.py#L387-L393)）

```python
# 获取权限
permissions = await self._fetch_oauth_permissions(oauth_token["access_token"])

# 签发本地 JWT
token_data = self._generate_jwt_token(user)
token_data["permissions"] = permissions
return token_data
```

**获取权限**：调用 [_fetch_oauth_permissions](../../backend/app/auth/service.py#L245-L270)，请求 `OAUTH_PERMISSIONS_URL`。本例中 `.env` 未配置该地址，返回空列表 `[]`。

**签发 JWT**：调用 [_generate_jwt_token](../../backend/app/auth/service.py#L105-L157)，生成 access_token + refresh_token。

最终返回：

```python
{
    "access_token": "eyJ...",     # 本地 JWT（HS256）
    "refresh_token": "eyJ...",    # 刷新 token
    "token_type": "bearer",
    "user_id": "43801463732",     # ← 来自 userinfo.userId
    "username": "lizijian999",    # ← 来自 userinfo.username
    "role": "end_user",           # ← 来自 roleMap 判定
    "permissions": []             # ← 来自 permissions 端点（本例为空）
}
```

---

## 4. 返回值在 Router 中的处理

[router.py:159-185](../../backend/app/auth/router.py#L159-L185) 收到返回值后：

```python
result = await auth_service.login_with_oauth_password(...)

# 1. 提取 permissions（不返回给前端 body）
permissions = result.pop("permissions", [])

# 2. 创建 JSONResponse（body 包含 access_token, refresh_token 等）
resp = JSONResponse(content=result)

# 3. 将 permissions 压缩后写入 Cookie（分片存储）
if permissions:
    compressed = gzip.compress(json.dumps(permissions).encode())
    encoded = base64.b64encode(compressed).decode()
    # 按 3800 字节分片
    chunks = [encoded[i:i+3800] for i in range(0, len(encoded), 3800)]
    for idx, chunk in enumerate(chunks):
        resp.set_cookie(key=f"user_permissions_{idx}", value=chunk, ...)
    resp.set_cookie(key="user_permissions_count", value=str(len(chunks)), ...)
```

---

## 5. 完整时序图

```
┌──────────┐     ┌──────────────┐     ┌──────────────────┐
│  前端     │     │  后端 Router  │     │  认证系统(9623)   │
└────┬─────┘     └──────┬───────┘     └────────┬─────────┘
     │                  │                       │
     │ POST /auth/login │                       │
     │ {user, password} │                       │
     ├─────────────────►│                       │
     │                  │                       │
     │                  │  ① POST /oauth/token  │
     │                  │  grant_type=password  │
     │                  ├──────────────────────►│
     │                  │     {access_token}    │
     │                  │◄──────────────────────┤
     │                  │                       │
     │                  │  ② GET /api/user/info │
     │                  │  Bearer {token}       │
     │                  ├──────────────────────►│
     │                  │     {userId, roleMap} │
     │                  │◄──────────────────────┤
     │                  │                       │
     │                  │  ③ _sync_oauth_user   │
     │                  │  (写入本地 DB)          │
     │                  │                       │
     │                  │  ④ _generate_jwt_token│
     │                  │  (签发本地 JWT)         │
     │                  │                       │
     │  200 OK          │                       │
     │  {access_token,  │                       │
     │   refresh_token, │                       │
     │   user_id, ...}  │                       │
     │  + Set-Cookie    │                       │
     │◄─────────────────┤                       │
```

---

## 6. 错误处理链路

```
login_with_oauth_password()
    │
    ├─ _exchange_password_token()
    │   ├─ 401 → ValueError("用户名或密码错误")
    │   ├─ 400 → ValueError("Authentication failed: 400")
    │   └─ 连接失败 → ValueError("Unable to reach auth server")
    │
    ├─ _fetch_oauth_userinfo()
    │   ├─ HTTP 错误 → ValueError("Fetch userinfo failed: {status}")
    │   └─ 连接失败 → ValueError("Unable to reach auth server")
    │
    ├─ _sync_oauth_user()
    │   └─ userId 缺失 → ValueError("OAuth userinfo missing user_id")
    │
    └─ _fetch_oauth_permissions()
        └─ 任何失败 → 返回空列表 []（不抛异常）
```

Router 中的 catch 逻辑（[router.py:187-199](../../backend/app/auth/router.py#L187-L199)）：

```python
except ValueError as e:
    msg = str(e)
    if "用户名或密码错误" in msg or "Invalid credentials" in msg:
        # 认证系统明确拒绝 → 直接返回 401，不 fallback
        raise HTTPException(status_code=401, detail=msg)
    # 其他错误（如认证服务不可达）→ fallback 到本地验证
```

> **注意：** 认证系统返回 400 时错误描述为 `账号/密码错误`，与判断条件 `"用户名或密码错误" in msg` 不匹配，会导致错误地 fallback 到本地验证。
