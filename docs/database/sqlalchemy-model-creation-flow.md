# SQLAlchemy 模型类定义到表注册 —— 完整流程图

> 以 `AgentPublication(Base)` 为例，从 Python 执行 `class` 语句开始，
> 沿 MRO 链扫描 `__init_subclass__`，到表对象注册进 `Base.metadata`。

---

## 总览流程

```mermaid
flowchart TD
    A["Python 执行<br/>class AgentPublication(Base)"] --> B["创建类对象<br/>type.__new__()"]
    B --> C["沿 MRO 链查找 __init_subclass__<br/>MRO: AgentPublication →<br/>Base → DeclarativeBase → object"]
    C --> D{"找到第一个<br/>__init_subclass__？"}
    D -- 未找到 --> E["跳过，类创建完成"]
    D -- 找到 --> F["执行 DeclarativeBase<br/>.__init_subclass__()"]

    F --> G["阶段一<br/>_setup_declarative_base"]
    G --> H["阶段二<br/>_as_declarative"]
    H --> I["阶段三<br/>super().__init_subclass__"]
    I --> J["类创建完成<br/>表已注册到 Base.metadata"]

    style A fill:#4A90D9,color:#fff
    style F fill:#E8A838,color:#fff
    style G fill:#7B68EE,color:#fff
    style H fill:#7B68EE,color:#fff
    style I fill:#7B68EE,color:#fff
    style J fill:#2ECC71,color:#fff
```

---

## 阶段一：`_setup_declarative_base` —— 建立"基地"

```mermaid
flowchart TD
    G1["进入 _setup_declarative_base(cls)"] --> G2{"cls 是否直接继承<br/>DeclarativeBase？"}
    G2 -- 是（如 Base） --> G3["创建全新 registry 对象"]
    G3 --> G4["registry 内部创建<br/>MetaData 实例"]
    G4 --> G5["cls.registry = registry<br/>cls.metadata = registry.metadata"]
    G5 --> G7["返回"]

    G2 -- 否（如 AgentPublication） --> G6["跳过<br/>继承 Base 已有的 registry / metadata"]
    G6 --> G7

    style G1 fill:#7B68EE,color:#fff
    style G3 fill:#3498DB,color:#fff
    style G5 fill:#3498DB,color:#fff
    style G6 fill:#95A5A6,color:#fff
    style G7 fill:#7B68EE,color:#fff
```

**核心要点**：

- `Base` 是"根"基类 → 为其创建独立的 `registry` + `metadata`
- `AgentPublication` 是子类 → 跳过，**共享** `Base` 的那套组件
- 这就是所有模型共享同一个 `metadata` 的根本原因

---

## 阶段二：`_ORMClassConfigurator._as_declarative` —— 执行"映射"

```mermaid
flowchart TD
    H1["进入 _as_declarative"] --> H2["扫描类属性<br/>读取所有 Mapped 属性"]
    H2 --> H3["解析列类型<br/>String / Boolean / JSON 等"]
    H3 --> H4["读取 __tablename__"]
    H4 --> H5["构建 Table 对象"]
    H5 --> H6["注册到 metadata.tables"]
    H6 --> H7["创建 Mapper 对象<br/>Mapper(cls, table)"]
    H7 --> H8["ORM 映射完成<br/>Python 类 ←→ 数据库表"]

    style H1 fill:#7B68EE,color:#fff
    style H2 fill:#E67E22,color:#fff
    style H5 fill:#E67E22,color:#fff
    style H6 fill:#E74C3C,color:#fff
    style H7 fill:#E67E22,color:#fff
    style H8 fill:#2ECC71,color:#fff
```

**核心要点**：

- `Mapped[str]` + `mapped_column(String(36))` → 被解析为列定义
- `__tablename__` 决定物理表名
- `Table` 对象被添加到 `metadata.tables` 字典 → 后续 `create_all` 靠这个字典知道要建哪些表
- `Mapper` 是 SQLAlchemy 内部的"映射登记簿"，连接 Python 类与 Table

---

## 阶段三：`super().__init_subclass__(**kw)` —— 保持"链式反应"

```mermaid
flowchart TD
    I1["执行<br/>super().__init_subclass__(**kw)"] --> I2{"继承链中还有<br/>其他 __init_subclass__？"}
    I2 -- 有（Mixin） --> I3["执行上层的<br/>__init_subclass__"]
    I3 --> I4["确保 Mixin 初始化<br/>逻辑也被执行"]
    I2 -- 没有 --> I5["链式反应结束"]
    I4 --> I5

    style I1 fill:#7B68EE,color:#fff
    style I3 fill:#9B59B6,color:#fff
    style I5 fill:#2ECC71,color:#fff
```

**核心要点**：

- 保证兼容性：如果使用了其他定义 `__init_subclass__` 的混入类（Mixin），它们的逻辑也会被执行
- Python 最佳实践：任何自定义 `__init_subclass__` 中都应调用 `super()`

---

## 完整调用链（代码级）

```
Python 解释器执行: class AgentPublication(Base):
    │
    ├─ 1. type.__new__(mcs, name, bases, namespace)
    │     创建类对象 AgentPublication
    │
    ├─ 2. 沿 MRO 查找 __init_subclass__
    │     MRO: AgentPublication → Base → DeclarativeBase → object
    │     发现 DeclarativeBase 定义了 __init_subclass__ ✓
    │
    └─ 3. DeclarativeBase.__init_subclass__(cls=AgentPublication, **kw)
          │
          ├─ _setup_declarative_base(cls)
          │   └─ cls 不是根基类 → 跳过，继承 Base 的 registry/metadata
          │
          ├─ _ORMClassConfigurator._as_declarative(cls, registry, metadata)
          │   ├─ 扫描 Mapped 属性 → 构建列
          │   ├─ 创建 Table("agent_publications", metadata, ...)
          │   ├─ metadata.tables["agent_publications"] = table  ← 注册！
          │   └─ Mapper(AgentPublication, table)                 ← 映射！
          │
          └─ super().__init_subclass__(**kw)
              └─ 链式传递，确保 Mixin 逻辑执行
```

---

## 从注册到建表：`create_tables()` 的角色

```mermaid
flowchart LR
    A["应用启动<br/>_platform_lifespan"] --> B["create_tables()"]
    B --> C["导入 publish.models<br/>触发 class 定义执行"]
    C --> D["__init_subclass__ 完成<br/>表注册到 metadata"]
    D --> E["Base.metadata.create_all"]
    E --> F["执行<br/>CREATE TABLE IF NOT EXISTS"]
    F --> G["数据库中出现表"]

    style A fill:#4A90D9,color:#fff
    style C fill:#E8A838,color:#fff
    style D fill:#7B68EE,color:#fff
    style E fill:#E74C3C,color:#fff
    style G fill:#2ECC71,color:#fff
```

> `create_all` 只能**建表**，不能改表（`ALTER TABLE`）。
> 生产环境应使用 Alembic 迁移管理表结构变更。
