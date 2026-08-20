# OAuth2.0 密码模式完整认证流程记录

本文档记录后端向外部认证系统（TipDM 统一认证平台）发起 OAuth2.0 密码模式认证的完整请求/响应流程，包括 Token 获取和用户信息获取两个阶段。

## 环境信息

| 项目 | 值 |
|---|---|
| 认证系统地址 | `http://192.168.1.96:9623` |
| Token 端点 | `/oauth/token` |
| Client ID | `619aa32b-60b5-4f99-8664-5bbd963bbda7` |
| Client Secret | `ZSMwfsJRQ9WkEcAv_Z__OQ` |
| 认证服务器 | nginx/1.20.1 |
| 记录时间 | 2026-08-20 |

---

## 1. 请求（Request）

### 请求行

```
POST http://192.168.1.96:9623/oauth/token HTTP/1.1
```

### 请求头（Request Headers）

| Header | Value |
|---|---|
| Content-Type | `application/x-www-form-urlencoded` |

### 请求体（Request Body）

格式：`application/x-www-form-urlencoded`

| 参数 | 值 | 说明 |
|---|---|---|
| grant_type | `password` | OAuth2 密码模式 |
| username | `lizijian999` | 用户名 |
| password | `abcd1234` | 密码 |
| client_id | `619aa32b-60b5-4f99-8664-5bbd963bbda7` | 客户端 ID |
| client_secret | `ZSMwfsJRQ9WkEcAv_Z__OQ` | 客户端密钥 |
| scope | `openid profile email` | 请求的权限范围 |

原始请求体：

```
grant_type=password&username=lizijian999&password=abcd1234&client_id=619aa32b-60b5-4f99-8664-5bbd963bbda7&client_secret=ZSMwfsJRQ9WkEcAv_Z__OQ&scope=openid+profile+email
```

### 完整请求命令

**PowerShell：**

```powershell
$body = @{
    grant_type    = "password"
    username      = "lizijian999"
    password      = "abcd1234"
    client_id     = "619aa32b-60b5-4f99-8664-5bbd963bbda7"
    client_secret = "ZSMwfsJRQ9WkEcAv_Z__OQ"
    scope         = "openid profile email"
}

$resp = Invoke-WebRequest -Uri "http://192.168.1.96:9623/oauth/token" `
    -Method Post `
    -Body $body `
    -ContentType "application/x-www-form-urlencoded" `
    -UseBasicParsing `
    -TimeoutSec 10

$resp.Content
```

**cURL：**

```bash
curl -X POST "http://192.168.1.96:9623/oauth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "username=lizijian999" \
  -d "password=abcd1234" \
  -d "client_id=619aa32b-60b5-4f99-8664-5bbd963bbda7" \
  -d "client_secret=ZSMwfsJRQ9WkEcAv_Z__OQ" \
  -d "scope=openid profile email"
```

---

## 2. 成功响应（Response — 200 OK）

### 状态行

```
HTTP/1.1 200 OK
```

### 响应头（Response Headers）

| Header | Value |
|---|---|
| Content-Type | `application/json;charset=ISO-8859-1` |
| Transfer-Encoding | `chunked` |
| Connection | `keep-alive` |
| Server | `nginx/1.20.1` |
| Date | `Thu, 20 Aug 2026 03:16:55 GMT` |
| Access-Control-Allow-Origin | `*` |
| Vary | `Origin, Access-Control-Request-Method, Access-Control-Request-Headers` |
| Set-Cookie | `rememberMe=deleteMe; Path=/; Max-Age=0; SameSite=lax` |

### 响应体（Response Body）

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJUaXBETSIsInN1YiI6IlRpcERNLVN1YmplY3QiLCJleHAiOjE3ODcyMjQ2MTUsIlRpcERNLUp3dC1QYXlsb2FkIjoie1widXNlcklkXCI6NDM4MDE0NjM3MzIsXCJ1dWlkXCI6XCI3NTQ3ZDdiYS0xYjUzLTRiNzktODM0MS02N2UyM2U0NmUyNTdcIixcInVzZXJuYW1lXCI6XCJsaXppamlhbjk5OVwiLFwidXNlckFsaWFzXCI6XCJsaXppamlhbjk5OVwifSJ9.lVw--3rvvF6phuDwocrjY_Hud13MKj69DMPcqCfJQre4H1-mV9york4T-3oi2Jik9MftirnfHokCUMA9NNcnherq68bkYKkAsu7MHklMqg6oCx26d4ENY3_Qa8wmO6hlF5VWY4vIiiVYKxgcYiNGgXlOEN8Sx_OARgSagZIj8Eg",
  "token_type": "PASSWORD",
  "expires_in": 28800
}
```

### 响应字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| access_token | string | JWT（RS256 签名），用于后续请求用户信息 |
| token_type | string | 固定值 `PASSWORD` |
| expires_in | number | Token 有效期，单位秒（28800 = 8小时） |

### JWT Payload 解码

`access_token` 的中间段 Base64 解码结果：

```json
{
  "iss": "TipDM",
  "sub": "TipDM-Subject",
  "exp": 1787224615,
  "TipDM-Jwt-Payload": "{\"userId\":43801463732,\"uuid\":\"ec52e844-c940-46e5-ad67-1db3e84b85ad\",\"username\":\"lizijian999\",\"userAlias\":\"lizijian999\"}"
}
```

| JWT 字段 | 值 | 说明 |
|---|---|---|
| iss | `TipDM` | 签发者 |
| sub | `TipDM-Subject` | 主题标识 |
| exp | 1787224615 | 过期时间戳（Unix） |
| TipDM-Jwt-Payload.userId | `43801463732` | 用户 ID |
| TipDM-Jwt-Payload.uuid | `ec52e844-c940-46e5-ad67-1db3e84b85ad` | 用户 UUID |
| TipDM-Jwt-Payload.username | `lizijian999` | 用户名 |
| TipDM-Jwt-Payload.userAlias | `lizijian999` | 用户别名 |

---

## 3. 失败响应（Response — 400 Bad Request）

当账号密码错误时，认证系统返回：

### 状态行

```
HTTP/1.1 400 Bad Request
```

### 响应头

同成功响应。

### 响应体

```json
{
  "error": "invalid_grant",
  "error_description": "账号/密码错误"
}
```

| 字段 | 说明 |
|---|---|
| error | 错误码，`invalid_grant` 表示授权凭证无效 |
| error_description | 错误描述（URL 编码：`%E8%B4%A6%E5%8F%B7/%E5%AF%86%E7%A0%81%E9%94%99%E8%AF%AF`） |

---

## 4. 认证成功后的流程

Token 获取成功后，后端依次执行以下步骤：

1. **获取用户信息** — [service.py:209-243](../../backend/app/auth/service.py#L209-L243)：用 `access_token` 请求 userinfo 端点
2. **获取权限** — [service.py:245-270](../../backend/app/auth/service.py#L245-L270)：用同一个 `access_token` 请求 permissions 端点（`.env` 中未配置 `OAUTH_PERMISSIONS_URL`，返回空列表）
3. **同步本地用户** — [service.py:272-354](../../backend/app/auth/service.py#L272-L354)：根据 `oauth_user_id` + `oauth_provider` 查找或创建本地用户
4. **签发本地 JWT** — [service.py:105-157](../../backend/app/auth/service.py#L105-L157)：为用户生成本地 access_token + refresh_token

---

## 5. 获取用户信息（Userinfo）

### 请求行

```
GET http://192.168.1.96:9623/api/user/info HTTP/1.1
```

### 请求头（Request Headers）

| Header | Value |
|---|---|
| Authorization | `Bearer {access_token}` |

其中 `{access_token}` 为上一步 Token 端点返回的 JWT。

### 完整请求命令

**PowerShell：**

```powershell
# 假设 $accessToken 已从 Token 端点获取
Add-Type -AssemblyName System.Net.Http
$httpClient = [System.Net.Http.HttpClient]::new()
$httpClient.DefaultRequestHeaders.Authorization = `
    [System.Net.Http.Headers.AuthenticationHeaderValue]::new("Bearer", $accessToken)

$resp = $httpClient.GetStringAsync("http://192.168.1.96:9623/api/user/info").Result
$resp
```

**cURL：**

```bash
curl -X GET "http://192.168.1.96:9623/api/user/info" \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9..."
```

---

### 成功响应（Response — 200 OK）

#### 状态行

```
HTTP/1.1 200 OK
```

#### 响应头（Response Headers）

| Header | Value |
|---|---|
| Content-Type | `application/json` |
| Transfer-Encoding | `chunked` |
| Connection | `keep-alive` |
| Server | `nginx/1.20.1` |
| Date | `Thu, 20 Aug 2026 03:29:58 GMT` |
| Vary | `Origin, Access-Control-Request-Method, Access-Control-Request-Headers` |

#### 响应体（Response Body）

```json
{
  "status": 200,
  "message": "操作成功",
  "data": {
    "userId": 43801463732,
    "username": "lizijian999",
    "phone": null,
    "email": null,
    "userAlias": "lizijian999",
    "avatar": "http://192.168.1.96:9620/files?path=avatar/default.png",
    "gender": null,
    "lastLoginTime": "2026-08-20T03:30:15.170+00:00",
    "roleNames": ["开发者", "学生"],
    "roleMap": {
      "8": "学生",
      "315": "开发者"
    },
    "organizationMap": null,
    "clientUserInfo": null
  }
}
```

#### 响应字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| status | number | 业务状态码，200 表示成功 |
| message | string | 提示信息 |
| data.userId | number | 用户唯一标识（与 JWT 中的 userId 一致） |
| data.username | string | 登录名 |
| data.userAlias | string | 用户显示别名 |
| data.phone | string\|null | 手机号 |
| data.email | string\|null | 邮箱 |
| data.avatar | string | 头像 URL |
| data.gender | string\|null | 性别 |
| data.lastLoginTime | string | 最后登录时间（ISO 8601） |
| data.roleNames | string[] | 角色名称列表 |
| data.roleMap | object | 角色 ID → 角色名映射 |
| data.organizationMap | object\|null | 组织信息 |
| data.clientUserInfo | object\|null | 客户端用户信息 |

---

### 后端角色判定逻辑

后端 [service.py:86-103](../../backend/app/auth/service.py#L86-L103) 中的 `_resolve_oauth_role` 方法根据 `roleMap` 判定本地角色：

```python
# 取 roleMap 的所有 key（角色 ID）
user_role_ids = set(roleMap.keys())  # {"8", "315"}

# 与 .env 配置比对
ROLE_DEVELOPER_IDS = {1, 25, 301}
ROLE_END_USER_IDS = {8}

# 匹配结果：
# "315" 不在 developer_ids → 不匹配
# "8" 在 end_user_ids → 命中 end_user
```

本例中 `roleMap` 为 `{"8": "学生", "315": "开发者"}`：

| roleMap Key | 匹配 ROLE_DEVELOPER_IDS (1,25,301) | 匹配 ROLE_END_USER_IDS (8) | 结果 |
|---|---|---|---|
| 315 | ❌ 不匹配 | — | — |
| 8 | — | ✅ 命中 | **end_user** |

最终用户 `lizijian999` 被同步为本地 **end_user** 角色。

> **注意：** 虽然认证系统中该用户拥有"开发者"角色（roleMap key=315），但 `.env` 中 `ROLE_DEVELOPER_IDS=1,25,301` 不包含 315，因此本地不会判定为 developer。如需映射为 developer，需将 `315` 加入 `ROLE_DEVELOPER_IDS`。

---

## 6. 完整流程时序图

```
┌──────────┐     ┌──────────┐     ┌──────────────────┐
│  前端     │     │  后端     │     │  认证系统(9623)   │
└────┬─────┘     └────┬─────┘     └────────┬─────────┘
     │  POST /auth/login                    │
     │  {username, password}                │
     ├──────────────►│                      │
     │               │  POST /oauth/token   │
     │               │  grant_type=password │
     │               │  client_id + secret  │
     │               ├─────────────────────►│
     │               │                      │
     │               │  200 {access_token}  │
     │               │◄─────────────────────┤
     │               │                      │
     │               │  GET /api/user/info  │
     │               │  Bearer {token}      │
     │               ├─────────────────────►│
     │               │                      │
     │               │  200 {userId, roles} │
     │               │◄─────────────────────┤
     │               │                      │
     │               │  [同步本地用户]        │
     │               │  [签发本地 JWT]       │
     │               │                      │
     │  200 {local JWT, cookies}            │
     │◄──────────────┤                      │
```

---

## 7. 注意事项

1. **错误消息匹配问题：** 认证系统返回 400 时错误描述为 `账号/密码错误`，但后端 [router.py:191](../../backend/app/auth/router.py#L191) 判断条件是 `"用户名或密码错误" in msg`，两者不一致，会导致错误地 fallback 到本地验证而非直接返回 401。

2. **角色映射缺口：** 认证系统中 roleMap key=315 对应"开发者"，但 `.env` 的 `ROLE_DEVELOPER_IDS` 中未包含 315，导致该用户在本地被判定为 end_user。

3. **编码问题：** Token 端点响应头 `Content-Type` 为 `application/json;charset=ISO-8859-1`，中文会乱码；UserInfo 端点为 `application/json`（默认 UTF-8），中文正常。
