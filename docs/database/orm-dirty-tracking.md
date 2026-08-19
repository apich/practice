# SQLAlchemy ORM 变更追踪机制（Dirty Tracking）

ORM 对象修改属性时，SQLAlchemy 如何知道哪些字段被改了？答案是**描述符协议**，不是 `__setattr__`。

---

## 一、完整链路

```
你写：
  user.email = "new@example.com"

Python 解释器发现 email 是一个描述符对象（InstrumentedAttribute），
自动调用描述符的 __set__ 方法：

  InstrumentedAttribute.__set__(user, "new@example.com")
    │
    └─ self.impl.set(state, dict_, value)
         │
         ├─ state._modified_event(dict_, self, old)   ← 标记为已修改
         │    │
         │    ├─ state.committed_state["email"] = "old@example.com"  ← 备份旧值
         │    ├─ state.modified = True                               ← 标记对象为脏
         │    └─ instance_dict._modified.add(state)                  ← 加入脏对象集合
         │
         └─ dict_["email"] = "new@example.com"        ← 实际写入值
```

---

## 二、为什么不是 `__setattr__`

```python
# __setattr__ 方式 — 拦截所有属性赋值
class User:
    def __setattr__(self, key, value):
        # 每次赋值都走这里，需要自己判断 key 是不是 ORM 字段
        ...

# 描述符方式 — 每个字段自己拦截自己
class User(Base):
    email = InstrumentedAttribute(...)   # ← 这是一个描述符对象
    username = InstrumentedAttribute(...)

# user.email = "new" 时，Python 自动调用 email 描述符的 __set__
# 不经过 __setattr__
```

描述符方式更精确——每个 ORM 字段有自己的描述符对象，赋值时只拦截对应的字段，不需要判断 key 是否为 ORM 字段。

---

## 三、Python 描述符协议

```python
user.email              → 调用 email.__get__(user)        → 读取值
user.email = "new"      → 调用 email.__set__(user, "new") → 写入值 + 标记脏
del user.email          → 调用 email.__delete__(user)     → 删除值 + 标记脏
```

每个 `mapped_column` 在类定义时被元类替换为 `InstrumentedAttribute` 描述符对象。赋值时 Python 自动调用描述符的 `__set__` 方法，SQLAlchemy 在这个方法里完成了值的写入和脏标记。

---

## 四、`_sa_instance_state` 从哪来

每个 ORM 对象在创建时（`__new__` / `__init__`），SQLAlchemy 通过元类注入了 `_sa_instance_state`：

```python
# 对象创建时，SQLAlchemy 在背后做了：
user = User.__new__(User)
user._sa_instance_state = InstanceState(user)  # ← 注入状态追踪对象
```

`InstanceState` 记录了：

| 属性 | 作用 |
|---|---|
| `session` | 这个对象属于哪个 session |
| `committed_state` | 哪些字段被改了（存旧值，用于 commit 时生成 UPDATE） |
| `modified` | 对象是否为脏 |

---

## 五、总结

```
DeclarativeBase
  │
  ├─ 元类把 mapped_column 替换为 InstrumentedAttribute（描述符）
  ├─ 对象创建时注入 _sa_instance_state（InstanceState）
  │
  └─ 赋值时：
      user.email = "new"
        → InstrumentedAttribute.__set__()      ← 描述符拦截
          → ScalarAttributeImpl.set()
            → state._modified_event()           ← 标记脏
            → dict_["email"] = "new"            ← 写值
```

所以准确来说，不是 `__setattr__`，是**描述符协议**。每个 ORM 字段都是一个描述符，赋值时自动触发它的 `__set__` 方法来标记变更。
