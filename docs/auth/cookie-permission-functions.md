# Cookie 权限校验函数（未启用）

以下三个函数实现了基于 Cookie 的权限校验机制，但**目前项目中未被使用**，处于待定状态。

项目当前实际使用的权限校验方式是 `require_role`（从 JWT 中读取角色）和 `require_permission`（从 JWT 中读取权限），而非从 Cookie 读取。

---

## 1. _read_permissions_from_cookies — 从 Cookie 读取权限

从 Cookie 中读取用户权限集合，采用 gzip 压缩 + base64 编码 + 分片存储方案。

```python
def _read_permissions_from_cookies(request: Request) -> list[str]:
    """从 Cookie 中读取用户权限集合（gzip 压缩 + base64 编码 + 分片存储）."""
    import base64
    import gzip
    import json

    count_str = request.cookies.get("user_permissions_count", "0")
    try:
        count = int(count_str)
    except ValueError:
        return []

    if count <= 0:
        return []

    chunks = []
    for i in range(count):
        chunk = request.cookies.get(f"user_permissions_{i}", "")
        if not chunk:
            return []
        chunks.append(chunk)

    try:
        encoded = "".join(chunks)
        compressed = base64.b64decode(encoded)
        data = gzip.decompress(compressed)
        return json.loads(data)
    except Exception:
        return []
```

### 存储方案

Cookie 有大小限制（约 4KB），权限数据经过压缩和分片后存储在多个 Cookie 中：

```
Cookie: user_permissions_count = 3          ← 分片数量
Cookie: user_permissions_0 = "H4sIAAAA..."  ← 第 1 片 base64
Cookie: user_permissions_1 = "AAAA..."      ← 第 2 片 base64
Cookie: user_permissions_2 = "zzzz..."      ← 第 3 片 base64

读取流程：
  拼接所有分片 → base64 解码 → gzip 解压 → JSON 反序列化 → list[str]
```

---

## 2. require_permissions — 权限验证依赖工厂

与 `require_role` 同为依赖工厂模式，但从 Cookie 读取权限而非从 JWT。

```python
def require_permissions(
    permissions: list[str],
    logic: str = "OR",
):
    """权限验证依赖工厂，支持 AND/OR 逻辑.

    Args:
        permissions: 所需权限码列表，如 ["agent:publish", "agent:config:create"]
        logic: 多权限逻辑，"OR"（满足其一）或 "AND"（全部满足）
    """

    async def _checker(request: Request) -> None:
        user_permissions = _read_permissions_from_cookies(request)
        if not user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No permissions found. Please login first.",
            )

        user_perm_set = set(user_permissions)

        if logic == "AND":
            missing = set(permissions) - user_perm_set
            if missing:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing required permissions: {', '.join(missing)}",
                )
        else:  # OR
            if not (user_perm_set & set(permissions)):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Requires at least one of: {', '.join(permissions)}",
                )

    return _checker
```

### 使用方式（未启用）

```python
# OR 逻辑：满足其一即可
@router.post("/agent/publish", dependencies=[Depends(require_permissions(["agent:publish"]))])
async def publish_agent(): ...

# AND 逻辑：必须同时满足
@router.post("/agent/config", dependencies=[Depends(require_permissions(["agent:create", "agent:update"], logic="AND"))])
async def create_config(): ...
```

---

## 3. check_permissions — 权限验证装饰器

与 `require_permissions` 功能相同，但使用装饰器语法而非依赖注入。

```python
def check_permissions(
    permissions: list[str],
    logic: str = "OR",
):
    """权限验证装饰器，支持 AND/OR 逻辑.

    Args:
        permissions: 所需权限码列表
        logic: "OR"（满足其一）或 "AND"（全部满足）
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            request: Request | None = kwargs.get("request") or next(
                (a for a in args if isinstance(a, Request)), None,
            )
            if request is None:
                raise RuntimeError(
                    "check_permissions 装饰器要求被装饰的函数必须包含 request: Request 参数",
                )

            user_permissions = _read_permissions_from_cookies(request)
            # ... 同 require_permissions 的校验逻辑 ...

            return await func(*args, **kwargs)
        return wrapper
    return decorator
```

### 使用方式（未启用）

```python
# OR 逻辑
@router.post("/agent/publish")
@check_permissions(["agent:publish"])
async def publish_agent(request: Request): ...

# AND 逻辑
@router.post("/agent/config")
@check_permissions(["agent:create", "agent:update"], logic="AND")
async def create_config(request: Request): ...
```

### 装饰器 vs 依赖工厂

| 维度 | `require_permissions`（依赖工厂） | `check_permissions`（装饰器） |
|---|---|---|
| 语法 | `dependencies=[Depends(...)]` | `@check_permissions(...)` |
| 函数签名要求 | 不需要 `request` 参数 | 必须有 `request: Request` 参数 |
| 灵活性 | 可组合多个依赖 | 只能装饰一个函数 |
| 项目惯例 | ✅ 项目主流用法 | 非主流 |

---

## 与当前项目的对比

项目当前实际使用的权限校验：

| 函数 | 权限来源 | 状态 |
|---|---|---|
| `require_role` | JWT payload 中的 `role` 字段 | ✅ 使用中 |
| `require_permission` | JWT payload 中的 `permissions` 字段 | ✅ 使用中 |
| `require_permissions` | Cookie 中的分片数据 | ❌ 未使用 |
| `check_permissions` | Cookie 中的分片数据 | ❌ 未使用 |

Cookie 方案的问题：
- 权限数据存储在客户端，可以被篡改（虽然有压缩编码但没有签名）
- 分片存储方案复杂，维护成本高
- JWT 本身就携带了权限信息，没必要再从 Cookie 读取
