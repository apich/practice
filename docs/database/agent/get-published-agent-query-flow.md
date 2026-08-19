# GET /publish/{agent_id} 查询调用链

从路由到 SQL 执行的完整流程。

---

## 调用链总览

```
GET /publish/{agent_id}
        ↓
┌─────────────────────────────────────────────────────────────────┐
│  router.py:90-96 — 路由层                                       │
│  @router.get("/{agent_id}")                                     │
│  async def get_published(agent_id, db):                         │
│      return await service.get_published(db, agent_id)           │
└─────────────────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────────┐
│  service.py:242-256 — 业务层                                    │
│  async def get_published(db, agent_id):                         │
│      result = await db.execute(                                 │
│          select(AgentPublication).where(...)                    │
│      )                                                          │
│      pub = result.scalar_one_or_none()                          │
│      return _publication_to_dict(pub)                           │
└─────────────────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────────┐
│  SQLAlchemy — 构建 SQL                                          │
│  select(AgentPublication)                                       │
│      .where(                                                    │
│          AgentPublication.agent_id == agent_id,                 │
│          AgentPublication.published == True                     │
│      )                                                          │
└─────────────────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────────┐
│  SQLite — 执行 SQL                                              │
│  SELECT id, agent_id, agent_name, agent_description,            │
│         published, current_version, execution_mode,             │
│         input_schema, published_at, unpublished_at,             │
│         published_by, created_at, updated_at                    │
│  FROM agent_publications                                        │
│  WHERE agent_id = 'xxx' AND published = 1;                      │
└─────────────────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────────┐
│  返回结果                                                       │
│  AgentPublication 对象 → _publication_to_dict() → dict          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 详细步骤

### 1️⃣ 路由层

**文件：** [router.py:90-96](../../backend/app/publish/router.py#L90-L96)

```python
@router.get("/{agent_id}")
async def get_published(
    agent_id: str,                        # 路径参数
    db: AsyncSession = Depends(get_db),   # 注入数据库会话
) -> dict:
    return await service.get_published(db, agent_id)
```

**职责：**
- 接收 HTTP 请求
- 提取路径参数 `agent_id`
- 注入数据库会话 `db`
- 调用 service 层

---

### 2️⃣ 业务层

**文件：** [service.py:242-256](../../backend/app/publish/service.py#L242-L256)

```python
async def get_published(db: AsyncSession, agent_id: str) -> dict:
    # 构建查询
    result = await db.execute(
        select(AgentPublication).where(
            AgentPublication.agent_id == agent_id,    # 条件1: agent_id 匹配
            AgentPublication.published == True,       # 条件2: 已发布
        ),
    )
    # 获取单条记录（没有则返回 None）
    pub = result.scalar_one_or_none()
    
    if not pub:
        raise HTTPException(status_code=404, detail=...)
    
    # 序列化为 dict
    return _publication_to_dict(pub)
```

**职责：**
- 构建 SQLAlchemy 查询语句
- 执行查询并获取结果
- 处理不存在的情况（404）
- 序列化返回数据

---

### 3️⃣ 模型层

**文件：** [models.py:18-58](../../backend/app/publish/models.py#L18-L58)

```python
class AgentPublication(Base):
    __tablename__ = "agent_publications"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    agent_name: Mapped[str] = mapped_column(String(255))
    agent_description: Mapped[str] = mapped_column(Text, default="")
    published: Mapped[bool] = mapped_column(Boolean, default=True)
    current_version: Mapped[str] = mapped_column(String(20), default="")
    execution_mode: Mapped[str] = mapped_column(String(10), default="chat")
    input_schema: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    unpublished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    published_by: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
```

**作用：**
- 定义表结构
- 映射 Python 属性到数据库列
- 提供类型提示

---

### 4️⃣ 序列化

**文件：** [service.py:536-549](../../backend/app/publish/service.py#L536-L549)

```python
def _publication_to_dict(pub: AgentPublication) -> dict:
    return {
        "id": pub.id,
        "agent_id": pub.agent_id,
        "agent_name": pub.agent_name,
        "agent_description": pub.agent_description,
        "published": pub.published,
        "current_version": pub.current_version,
        "execution_mode": pub.execution_mode,
        "input_schema": pub.input_schema,
        "published_at": pub.published_at.isoformat() if pub.published_at else None,
        "unpublished_at": pub.unpublished_at.isoformat() if pub.unpublished_at else None,
        "published_by": pub.published_by,
    }
```

**作用：**
- 将 ORM 对象转换为字典
- 处理 datetime 到 ISO 格式字符串的转换
- 处理可空字段

---

## 最终 SQL

```sql
SELECT 
    id, 
    agent_id, 
    agent_name, 
    agent_description,
    published, 
    current_version, 
    execution_mode,
    input_schema, 
    published_at, 
    unpublished_at,
    published_by, 
    created_at, 
    updated_at
FROM agent_publications
WHERE agent_id = '8a2fb85bd0e549459956990f0c17ac06' 
  AND published = 1;
```

---

## 返回示例

```json
{
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "agent_id": "8a2fb85bd0e549459956990f0c17ac06",
    "agent_name": "mimo",
    "agent_description": "一个智能助手",
    "published": true,
    "current_version": "5840705",
    "execution_mode": "chat",
    "input_schema": null,
    "published_at": "2026-08-19T10:30:00",
    "unpublished_at": null,
    "published_by": "user-123"
}
```

---

## 相关文件

| 文件 | 作用 |
|------|------|
| [router.py](../../backend/app/publish/router.py) | 路由定义 |
| [service.py](../../backend/app/publish/service.py) | 业务逻辑 |
| [models.py](../../backend/app/publish/models.py) | ORM 模型 |
| [database.py](../../backend/app/core/database.py) | 数据库初始化 |
