# ORM 属性赋值到 commit 的完整执行过程

`user.email = "new@example.com"` 从属性赋值到最终生成 UPDATE SQL 的完整链路。

---

## 完整流程图

```
═══════════════════════════════════════════════════════════════
阶段 1：类定义 — __init_subclass__ 设置描述符
═══════════════════════════════════════════════════════════════

class User(Base):                        ← Python 开始创建 User 类
    __tablename__ = "users"
    email = mapped_column(String(255))   ← 此时 email 还是普通的 mapped_column 对象
    │
    │  Python 执行 type.__new__()，创建 User 类对象
    │
    ▼
DeclarativeBase.__init_subclass__(cls=User)
    │
    ├─ _as_declarative(registry, User, {"__tablename__": "users", "email": ...})
    │    │
    │    └─ _MapperConfig.setup_mapping(...)
    │         │
    │         ├─ 1. 扫描类属性，发现 email 是 mapped_column
    │         ├─ 2. 创建 ScalarAttributeImpl(class_=User, key="email", ...)
    │         ├─ 3. 创建 InstrumentedAttribute(impl=impl)
    │         ├─ 4. User.email = InstrumentedAttribute(impl=impl)  ← 替换原始属性
    │         ├─ 5. 创建 Mapper，关联 User 类和 users 表
    │         └─ 6. 注入 _sa_instance_state 的创建逻辑（__init__ 中）
    │
    └─ super().__init_subclass__()

User 类创建完成，此时：
  - User.email 已经是 InstrumentedAttribute 描述符（不是 mapped_column 了）
  - User.__mapper__ 已关联到 users 表
  - User() 创建实例时会自动注入 _sa_instance_state

═══════════════════════════════════════════════════════════════
阶段 2：实例创建 — 注入 _sa_instance_state
═══════════════════════════════════════════════════════════════

user = User()
    │
    ├─ user.__dict__ = {}                          ← 空的属性字典
    └─ user._sa_instance_state = InstanceState(user) ← 注入状态追踪对象
         ├── class_: <class 'User'>
         ├── modified: False
         ├── committed_state: {}
         ├── session_id: None
         └── key: None

═══════════════════════════════════════════════════════════════
阶段 3：属性赋值 — 描述符拦截 + 标记脏
═══════════════════════════════════════════════════════════════

user.email = "new@example.com"
  │
  │  Python 解释器发现 email 是描述符，自动调用 __set__
  │
  ▼
InstrumentedAttribute.__set__(user, "new@example.com")
  │
  │  从 user 对象上取出两个关键变量：
  │    state = user._sa_instance_state   ← InstanceState 状态追踪对象
  │    dict_ = user.__dict__             ← 实际属性值字典
  │
  ▼
ScalarAttributeImpl.set(state, dict_, "new@example.com")
  │
  │  self.key = "email"（类定义时由 __init_subclass__ 传入）
  │
  │  第 1 步：取旧值
  ├─ old = dict_.get(self.key)  →  "old@example.com"
  │
  │  第 2 步：触发事件（如果有监听器）
  ├─ fire_replace_event(...)
  │
  │  第 3 步：标记脏
  ├─ state._modified_event(dict_, self, old)
  │    │
  │    ├─ state.committed_state[self.key] = "old@example.com"  ← 备份旧值
  │    ├─ state.modified = True                                ← 对象标记为脏
  │    └─ session.identity_map._modified.add(state)            ← 加入 session 脏集合
  │
  │  第 4 步：写入新值
  └─ dict_[self.key] = "new@example.com"                       ← 写入 user.__dict__

赋值阶段结束，此时：
  - user.__dict__["email"] = "new@example.com"        （新值已写入）
  - state.committed_state["email"] = "old@example.com"（旧值已备份）
  - state.modified = True                              （对象已脏）
  - session.identity_map._modified = {state}           （session 已记录）

═══════════════════════════════════════════════════════════════
阶段 4：commit — 对比差异，生成 SQL
═══════════════════════════════════════════════════════════════

await db.commit()
  │
  │  第 1 步：session 查 identity_map._modified 集合，找到所有脏对象
  │
  │  第 2 步：对每个脏对象，对比 committed_state 和 dict_
  │    committed_state["email"] = "old@example.com"   ← 旧值
  │    dict_["email"] = "new@example.com"             ← 新值
  │    差异：email 字段变了
  │
  │  第 3 步：差异部分生成 UPDATE SQL 并执行
  └─ UPDATE users SET email = 'new@example.com' WHERE user_id = 'abc123'
```

---

## 涉及的五个对象

| 对象 | 类型 | 来源 | 职责 |
|---|---|---|---|
| `User.email` | `InstrumentedAttribute` | `__init_subclass__` 替换 `mapped_column` | 描述符入口，拦截 `__set__` |
| `impl` | `ScalarAttributeImpl` | `InstrumentedAttribute.impl` | 实际读写逻辑，`self.key` 存属性名 |
| `state` | `InstanceState` | `user._sa_instance_state` | 追踪脏状态（旧值备份、脏标记） |
| `dict_` | `dict` | `user.__dict__` | 存储实际属性值 |
| `instance_dict` | `IdentityMap` | `session.identity_map` | session 的对象注册表（脏集合、新增集合） |

---

## `dict_` vs `instance_dict`

| 变量 | 来源 | 内容 |
|---|---|---|
| `dict_` | `user.__dict__` | `{"email": "new@...", "name": "张三"}` |
| `instance_dict` | `session.identity_map` | `{"_modified": {state1, ...}, "_new": {state4}}` |

`dict_` 改对象的属性值，`instance_dict` 通知 session "这个对象脏了"。

---

## `self.key` 的来源

`ScalarAttributeImpl.set` 中的 `self.key` 不是硬编码的 `"email"`，是类定义时由 `__init_subclass__` 传入的：

```
__init_subclass__ 扫描类属性
  → 发现 email 是 mapped_column
  → 创建 ScalarAttributeImpl(class_=User, key="email", ...)
  → self.key = "email"
```

---

## `state`（`_sa_instance_state`）内存结构

```
user._sa_instance_state: InstanceState
  ├── class_: <class 'User'>                    ← ORM 类
  ├── modified: True                            ← 脏标记
  ├── committed_state:                          ← 旧值备份
  │     "email": "old@example.com"
  │     "name": "旧名字"
  ├── session_id: 42                            ← 所属 session
  ├── key: (User, "abc123")                     ← 主键标识
  ├── expired: False                            ← 过期标记
  └── expired_attributes: set()                 ← 过期字段集合
```

---

## 类比 Git

```
类定义阶段：
  __init_subclass__    → 初始化仓库（设置描述符、关联表）

实例创建阶段：
  User()               → git init（注入 _sa_instance_state）

赋值阶段：
  user.email = "new"   → 改了工作区的文件
  state._modified_event → git 自动检测到文件变更
  committed_state      → 记录了改之前的版本

commit 阶段：
  db.commit()          → git commit
    对比 committed_state 和 dict_  → 对比暂存区和工作区
    生成 UPDATE SQL                → 生成 commit 记录
```
