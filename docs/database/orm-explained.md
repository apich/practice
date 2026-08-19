# ORM（Object Relational Mapping）讲解

ORM = **O**bject **R**elational **M**apping（对象关系映射）

把"对象"和"关系型数据库"做映射，让两边能互相翻译。

---

## 一、映射关系

```
Python 世界（面向对象）          数据库世界（关系型）

对象 Object                     表 Table
  ↓ 映射                          ↓ 映射
类 Class         ←──────────→    表结构 Schema
实例 Instance    ←──────────→    行 Row
属性 Attribute   ←──────────→    列 Column
```

---

## 二、ORM 的作用

没有 ORM 之前，操作数据库要写 SQL：

```python
# 纯 SQL — 数据库的语言
await db.execute(text("INSERT INTO users (user_id, username) VALUES ('abc', 'zhangsan')"))
await db.execute(text("SELECT * FROM users WHERE user_id = 'abc'"))
```

有了 ORM，可以用 Python 的方式操作：

```python
# Python — 对象的语言
user = User(user_id="abc", username="zhangsan")   # 创建对象
db.add(user)                                        # 存入数据库

user = await db.get(User, "abc")                    # 从数据库取出对象
print(user.username)                                # 像用普通对象一样
```

本质就是一个翻译器：

```
你写 Python 代码         ORM 翻译            数据库执行
user.email = "new"  →  UPDATE users   →  数据库改了
                      SET email='new'
                      WHERE id='abc'
```

---

## 三、ORM 模型类

就是 Python 类和数据库表的映射。一个类对应一张表，类的属性对应表的列。

```python
# ORM 模型类 — Python 代码
class User(Base):
    __tablename__ = "users"              # 对应数据库的 users 表

    user_id = mapped_column(String(36), primary_key=True)   # 对应 user_id 列
    username = mapped_column(String(100))                    # 对应 username 列
    email = mapped_column(String(255))                       # 对应 email 列
```

```
Python 类                              数据库表
┌─────────────────┐                   ┌─────────────────────────┐
│ User             │      映射         │ users                   │
│                  │   ←──────────→    │                         │
│ user_id: str     │                   │ user_id VARCHAR(36) PK  │
│ username: str    │                   │ username VARCHAR(100)   │
│ email: str       │                   │ email VARCHAR(255)      │
└─────────────────┘                   └─────────────────────────┘
```

不是所有 Python 类都是 ORM 模型类，只有继承了 `DeclarativeBase`（通过 `mapped_column` 声明列）的才是。

---

## 四、继承与抽象基类

中间可以有抽象基类不建表。

```python
class Base(DeclarativeBase):
    pass

# 抽象基类 — 不建表，只提供公共字段
class _JsonRecordMixin(Base):
    __abstract__ = True                          # ← 标记为抽象，不创建表
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime())
    updated_at: Mapped[datetime] = mapped_column(DateTime())

# 具体模型 — 继承抽象基类，会建表
class SessionRow(_JsonRecordMixin):              # 间接继承 Base
    __tablename__ = "sessions"                   # ← 有表名，创建 sessions 表
    user_id: Mapped[str] = mapped_column(String(255))

class MessageRow(Base):                          # 直接继承 Base
    __tablename__ = "messages"                   # ← 有表名，创建 messages 表
    session_id: Mapped[str] = mapped_column(String(255))
```

### 继承链

```
Base (DeclarativeBase)
  │
  ├─ _JsonRecordMixin (__abstract__ = True)  ← 不建表，只提供公共字段
  │     │
  │     ├─ SessionRow  (__tablename__ = "sessions")   ← 建表
  │     ├─ AgentRow    (__tablename__ = "agents")     ← 建表
  │     └─ ...
  │
  └─ MessageRow (__tablename__ = "messages")          ← 建表
```

### 判断标准

| 条件 | 是 ORM 模型类？ | 会建表？ |
|---|---|---|
| 继承 Base + 有 `__tablename__` | ✅ | ✅ |
| 继承 Base + 有 `__abstract__ = True` | ✅（抽象基类） | ❌ |
| 继承 Base + 既没表名也没 abstract | ✅（但 SQLAlchemy 会报错） | ❌ |
| 没继承 Base | ❌ | ❌ |

只要继承链上有 `DeclarativeBase`，有 `mapped_column`，就是 ORM 模型类。`__abstract__ = True` 只是告诉 SQLAlchemy "不要给我建表"，但它仍然是 ORM 模型体系的一部分，子类会继承它的字段。
