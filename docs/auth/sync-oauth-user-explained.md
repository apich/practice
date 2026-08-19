# _sync_oauth_user 函数精讲

OAuth 登录时将用户信息同步到本地 `users` 表的核心函数。有则更新，无则创建。

---

## 一、参数从哪来

```python
async def _sync_oauth_user(
    self,                    # AuthService 实例（自动传入）
    oauth_info: dict,        # ← 来自第 2 步 _fetch_oauth_userinfo() 的返回值
    db: AsyncSession,        # ← 来自 login 的参数，由 FastAPI 依赖注入提供
) -> User:
```

调用链路：

```python
# login_with_oauth_password 中：
oauth_user_info = await self._fetch_oauth_userinfo(oauth_token["access_token"])
#                   ↓ 这就是 oauth_info 参数
user = await self._sync_oauth_user(oauth_user_info, db)
```

`oauth_info` 就是 OAuth 服务器返回的用户信息字典，类似：

```json
{
    "user_id": "abc123",
    "username": "zhangsan",
    "email": "zhangsan@example.com",
    "name": "张三",
    "provider": "auth-server"
}
```

---

## 二、逐行精讲

### 第一部分：解包嵌套响应（line 289）

```python
if "data" in oauth_info and isinstance(oauth_info["data"], dict):
    info = oauth_info["data"]
else:
    info = oauth_info
```

兼容两种返回格式：

```json
// 格式 1：扁平结构（直接用）
{ "user_id": "abc123", "username": "zhangsan" }

// 格式 2：嵌套结构（取 data 字段）
{ "status": 200, "data": { "userId": "abc123", "username": "zhangsan" } }
```

`isinstance(oauth_info["data"], dict)` 检查 `data` 是不是字典类型，防止 `data` 是其他类型（比如字符串）时误取。

### 第二部分：提取字段（line 294）

```python
oauth_user_id = str(
    info.get("user_id")      # 尝试取 user_id 字段
    or info.get("userId")    # 取不到？试 userId
    or info.get("sub")       # 还取不到？试 sub（JWT 标准字段）
    or info.get("id")        # 最后试 id
    or ""                    # 都没有？给空字符串
)
```

`dict.get("key")` 取字典的值，取不到返回 `None`（不报错）。
`or` 运算符：左边是 `None` 或空串时，返回右边的值。

```python
info.get("user_id") or info.get("userId")
# 等价于：
if info.get("user_id") is not None and info.get("user_id") != "":
    return info.get("user_id")
else:
    return info.get("userId")
```

`oauth_provider`、`username`、`email`、`name` 同理，都是容错取值。

### 第三部分：查询本地数据库（line 314）

```python
stmt = select(User).where(
    User.oauth_user_id == oauth_user_id,   # 条件 1
    User.oauth_provider == oauth_provider,  # 条件 2
)
result = await db.execute(stmt)
user = result.scalar_one_or_none()
```

这三行做了什么：

```
第 1 行：构造 SQL 语句
  select(User) → SELECT * FROM users
  .where(...)  → WHERE oauth_user_id = 'abc123' AND oauth_provider = 'auth-server'

  等价于：
  SELECT * FROM users
  WHERE oauth_user_id = 'abc123' AND oauth_provider = 'auth-server'
```

```
第 2 行：执行 SQL（await 因为是异步 IO）
  result = await db.execute(stmt)
  → 发送 SQL 到数据库，拿到结果集
```

```
第 3 行：从结果集中取数据
  result.scalar_one_or_none()
  → 取一行中的一列值（这里取整个 User 对象）
  → 没找到返回 None
  → 找到多条会报错（所以用 one）
```

### 第四部分：已存在 → 更新（line 322）

```python
if user is not None:
    user.email = email          # 直接改 Python 对象的属性
    user.name = name
    user.role = self._resolve_oauth_role(info)
    await db.commit()           # 提交事务，写入数据库
    await db.refresh(user)      # 从数据库重新加载最新数据
    return user
```

`db.commit()` 之前的操作（`user.email = email` 等）都只改了 Python 内存中的对象，没有写入数据库。`commit()` 时才真正执行 `UPDATE users SET email=..., name=..., role=... WHERE user_id=...`。

`db.refresh(user)` 从数据库重新读取这条记录，确保 `user` 对象和数据库一致（比如数据库有默认值、触发器等可能改了数据）。

**为什么不用手动构造 UPDATE SQL？**

这是 SQLAlchemy 的**变更追踪**（Dirty Tracking）机制。通过 `db.execute()` 查出来的对象被 session 托管，修改属性时 SQLAlchemy 静默记录了"哪些字段变了"，`commit()` 时自动生成 UPDATE SQL。

```
user.email = "new@example.com"   # ← session 内部标记：email 脏了
user.name = "新名字"              # ← session 内部标记：name 脏了
await db.commit()
# 背后自动执行：UPDATE users SET email='new@example.com', name='新名字' WHERE user_id='abc123'
```

等价于手动构造 SQL：

```python
stmt = update(User).where(User.user_id == "abc123").values(email="new@example.com", name="新名字")
await db.execute(stmt)
await db.commit()
```

### 第五部分：不存在 → 创建（line 331）

```python
# 先检查 username 是否被占用
stmt_username = select(User).where(User.username == username)
result_username = await db.execute(stmt_username)
if result_username.scalar_one_or_none() is not None:
    username = f"{username}_{oauth_user_id[:8]}"   # 被占用？加后缀
```

`oauth_user_id[:8]` 截取前 8 个字符，`f"..."` 是字符串格式化：

```python
# 如果 zhangsan 已被占用
username = f"{'zhangsan'}_{'abc12345'}"
# 结果："zhangsan_abc12345"
```

```python
# 创建 User 对象（只在内存中，还没写数据库）
user = User(
    username=username,
    password_hash="",              # OAuth 用户无本地密码，给空串
    role=role,
    auth_type="oauth",             # 标记来源
    oauth_user_id=oauth_user_id,
    oauth_provider=oauth_provider,
    email=email,
    name=name,
)

db.add(user)        # 把对象加入 session 的"待写入"列表（还没写数据库）
await db.commit()   # 提交事务，执行 INSERT INTO users (...) VALUES (...)
await db.refresh(user)  # 从数据库重新加载（拿到自动生成的 user_id 等）
return user
```

`db.add()` 只是告诉 SQLAlchemy "这个对象需要保存"，`db.commit()` 才真正执行 SQL。

---

## 三、完整流程图

```
_sync_oauth_user(oauth_info, db)
  │
  ├─ 1. 解包嵌套响应 → info
  │
  ├─ 2. 提取字段 → oauth_user_id, username, email, name
  │
  ├─ 3. SELECT * FROM users
  │     WHERE oauth_user_id = ? AND oauth_provider = ?
  │     │
  │     ├─ 找到了？
  │     │   ├─ user.email = email     （改内存，session 追踪变更）
  │     │   ├─ user.name = name       （改内存，session 追踪变更）
  │     │   ├─ db.commit()            （UPDATE 写入数据库）
  │     │   ├─ db.refresh(user)       （重新加载）
  │     │   └─ return user
  │     │
  │     └─ 没找到？
  │         ├─ 检查 username 是否被占用
  │         │   └─ 被占用 → 加后缀
  │         ├─ User(username=..., auth_type="oauth", ...)  （创建对象）
  │         ├─ db.add(user)          （加入待写入列表）
  │         ├─ db.commit()           （INSERT 写入数据库）
  │         ├─ db.refresh(user)      （重新加载）
  │         └─ return user
```

---

## 四、关键方法总结

| 方法 | 作用 | 等价 SQL |
|---|---|---|
| `db.execute(stmt)` | 执行 SQL 语句 | 发送 SQL 到数据库 |
| `db.add(user)` | 标记对象待写入 | 暂无，只是内存操作 |
| `db.commit()` | 提交事务 | `INSERT` 或 `UPDATE` |
| `db.refresh(user)` | 重新加载对象 | `SELECT * FROM users WHERE id = ?` |

### 变更追踪类比 Git

```
db.add(user)         →  git add（标记要跟踪）
user.email = "..."   →  改了文件（git 自动知道哪些文件变了）
db.commit()          →  git commit（一次性提交所有变更）
```
