# OAuth2.0 Userinfo → 本地 JWT 数据流

本文档详细记录认证系统返回的 userinfo 响应中，各字段如何经过后端处理最终写入本地 JWT。

---

## 1. 认证系统返回的 Userinfo 响应

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

共 11 个字段，其中 **仅 3 个** 最终影响本地 JWT。

---

## 2. 数据流总览

```
userinfo 响应
    │
    ▼
_sync_oauth_user() 解包 data 层
    │
    ├─ userId         → oauth_user_id → user.user_id → JWT "sub"
    ├─ username       → user.username                 → JWT "username"
    ├─ email          → user.email                    → ❌ 不进 JWT
    ├─ userAlias      → user.name                     → ❌ 不进 JWT
    ├─ avatar         → ❌ 未使用
    ├─ phone          → ❌ 未使用
    ├─ gender         → ❌ 未使用
    ├─ lastLoginTime  → ❌ 未使用
    ├─ roleNames      → ❌ 未使用
    ├─ roleMap        → _resolve_oauth_role() → user.role → JWT "role"
    ├─ organizationMap → ❌ 未使用
    └─ clientUserInfo  → ❌ 未使用
```

---

## 3. 进入 JWT 的字段汇总

| userinfo 字段 | 进入 JWT 的字段 | 转换方式 |
|---|---|---|
| `data.userId` | `sub` | 直接取值 |
| `data.username` | `username` | 直接取值 |
| `data.roleMap` | `role` | key 与 `.env` 比对后判定为 `end_user` 或 `developer` |

其余字段（`phone`、`email`、`userAlias`、`avatar`、`gender`、`lastLoginTime`、`roleNames`、`organizationMap`、`clientUserInfo`）**只写入本地数据库 User 表**，不进入 JWT。

---

## 4. 源码调用链

### 第一步：`_sync_oauth_user`（[service.py:288-354](../../backend/app/auth/service.py#L288-L354)）

从 userinfo 中提取字段，写入本地 User 模型：

```python
# ① 解包嵌套结构，userinfo 是 {"status":200, "data":{...}}
if "data" in oauth_info and isinstance(oauth_info["data"], dict):
    info = oauth_info["data"]          # info = data 层

# ② 取 userId → oauth_user_id
oauth_user_id = str(
    info.get("user_id")
    or info.get("userId")              # ← 命中这个，值为 43801463732
    or info.get("sub")
    or info.get("id")
    or ""
)

# ③ 取 username
username = (
    info.get("username")               # ← 命中这个，值为 "lizijian999"
    or info.get("preferred_username")
    or f"oauth_{oauth_user_id}"
)

# ④ 取 roleMap → 判定角色
role = self._resolve_oauth_role(info)  # info 中含 roleMap

# ⑤ 写入 User 模型
user = User(
    username=username,                  # ← "lizijian999"
    role=role,                          # ← "end_user"
    oauth_user_id=oauth_user_id,        # ← "43801463732"
    auth_type="oauth",
    ...
)
```

### 第二步：`_resolve_oauth_role`（[service.py:86-103](../../backend/app/auth/service.py#L86-L103)）

根据 `roleMap` 的 key 与 `.env` 配置比对，判定本地角色：

```python
role_map = info.get("roleMap", {})     # {"8": "学生", "315": "开发者"}
user_role_ids = set(role_map.keys())   # {"8", "315"}

# 与 .env 比对
developer_ids = {"1", "25", "301"}     # ROLE_DEVELOPER_IDS
end_user_ids = {"8"}                   # ROLE_END_USER_IDS

# {"315"} ∩ {"1","25","301"} = ∅ → 不匹配 developer
# {"8","315"} ∩ {"8"} = {"8"} → 命中 end_user
return Role.END_USER                   # "end_user"
```

本例判定过程：

| roleMap Key | 匹配 ROLE_DEVELOPER_IDS (1,25,301) | 匹配 ROLE_END_USER_IDS (8) | 结果 |
|---|---|---|---|
| 315 | ❌ 不匹配 | — | — |
| 8 | — | ✅ 命中 | **end_user** |

### 第三步：`_generate_jwt_token`（[service.py:115-126](../../backend/app/auth/service.py#L115-L126)）

从 User 模型读取字段，签发本地 JWT：

```python
access_payload = {
    "sub": user.user_id,       # ← 来自 oauth_user_id ← userinfo.userId
    "username": user.username,  # ← 来自 userinfo.username
    "role": user.role,          # ← 来自 roleMap 判定结果
    "roles": [user.role],
    "permissions": DEFAULT_PERMISSIONS,  # 固定值，不来自认证系统
    "auth_type": "oauth",
    ...
}
```

---

## 5. 字段提取路径明细

| userinfo 字段 | 提取代码行 | 存入 User 字段 | 最终 JWT 字段 |
|---|---|---|---|
| `data.userId` | [L295-301](../../backend/app/auth/service.py#L295-L301) `info.get("userId")` | `user.oauth_user_id` → `user.user_id` | `sub` |
| `data.username` | [L306-310](../../backend/app/auth/service.py#L306-L310) `info.get("username")` | `user.username` | `username` |
| `data.roleMap` | [L326](../../backend/app/auth/service.py#L326) `self._resolve_oauth_role(info)` | `user.role` | `role` |

---

## 6. 关键结论

整个链路是 **userinfo → `_sync_oauth_user` 写入 User 模型 → `_generate_jwt_token` 从 User 模型读取**，不是直接从 userinfo 取值。User 模型是中间桥梁。
