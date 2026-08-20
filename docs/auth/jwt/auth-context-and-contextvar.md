# AuthContext 与 ContextVar 请求上下文

`AuthMiddleware` 解析 JWT 后，把 token 里的信息组装成结构化对象，存入请求上下文，方便后续代码使用。

---

## 一、JWT payload → 结构化对象

JWT payload 是一个扁平字典：

```json
{
    "sub": "user_001",
    "username": "zhangsan",
    "exp": 1724000000,
    "type": "access",
    "role": "developer",
    "roles": ["developer"],
    "permissions": ["agent:read", "agent:write"]
}
```

中间件将其拆分成三个对象：

### 1. TokenInfo — 令牌本身的信息

```python
token_info = TokenInfo(
    active=True,                          # token 有效
    user_id="user_001",                   # 从 sub 取
    username="zhangsan",                  # 从 username 取
    expires_at=1724000000,                # 从 exp 取
    extra={"type": "access"},             # token 类型
)
```

### 2. PermissionInfo — 权限信息

```python
perm_info = PermissionInfo(
    user_id="user_001",
    roles=["developer"],                  # 用户角色
    permissions=["agent:read", ...],      # 具体权限列表
)
```

### 3. AuthContext — 打包成一个上下文对象

```python
ctx = AuthContext(
    token="eyJhbG...",                    # 原始 token 字符串
    token_info=token_info,                # 令牌信息
    permissions=perm_info,                # 权限信息
)
```

### 4. 存入 ContextVar

```python
ctx_token = set_auth_context(ctx)
```

后续代码就可以直接：

```python
ctx = get_auth_context()
ctx.user_id          # "user_001"
ctx.role             # "developer"
ctx.has_permission("agent:write")  # True
```

本质就是把 JWT 的扁平字典转成了有方法、有类型的结构化对象，方便后续使用。

---

## 二、请求生命周期

指浏览器向后端发起请求到后端回复返回体这个期间。

```
浏览器发起请求
  │
  ├─ AuthMiddleware.dispatch()     ← set_auth_context(ctx) 存入
  │    │
  │    ├─ 路由处理函数             ← get_auth_context() 随时可取
  │    ├─ 依赖注入函数             ← get_auth_context() 随时可取
  │    ├─ service 层               ← get_auth_context() 随时可取
  │    │
  │    └─ 返回响应
  │
  └─ finally: auth_context.reset() ← 请求结束，清除上下文

  ↓
浏览器收到响应
```

中间任何一层代码调用 `get_auth_context()` 都能拿到当前请求的用户信息，不需要层层传参。这就是 `ContextVar` 的作用——按请求隔离的全局变量。

---

## 三、当前项目使用情况

`get_auth_context()` 定义了但整个项目没有一处调用它。

实际的用户信息获取方式是：

```python
# get_current_user — 直接读 request.state.user，没用 get_auth_context
user_payload = getattr(request.state, "user", None)
if user_payload:
    user_id = user_payload.get("sub")

# _platform_get_user_id — 同样直接读 request.state.user
user_payload = getattr(request.state, "user", None)
if user_payload:
    return user_payload.get("sub", "")
```

### 汇总

| 机制 | 状态 |
|---|---|
| `set_auth_context(ctx)` | ✅ 中间件里调用了，存入了 ContextVar |
| `get_auth_context()` | ❌ 没有任何地方调用 |
| 实际读取用户信息 | 直接从 `request.state.user` 读原始字典 |

`AuthContext`、`TokenInfo`、`PermissionInfo` 这套结构化对象组装好了，但没人用。所有代码都在直接读 `request.state.user` 字典。相当于精心打包了一个工具箱，但大家都在用旁边的散装零件。
