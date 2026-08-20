# _fetch_agent_snapshot 函数讲解

**文件：** [service.py:43-73](../../../backend/app/publish/service.py#L43-L73)

```python
async def _fetch_agent_snapshot(app: Any, agent_id: str, user_id: str) -> dict:
```

---

## 1️⃣ 函数签名

| 参数 | 类型 | 说明 |
|------|------|------|
| `app` | Any | FastAPI 应用实例，用于访问 `app.state.storage` |
| `agent_id` | str | 智能体 ID |
| `user_id` | str | 当前用户 ID |

**返回值：** `dict` — 智能体配置快照

---

## 2️⃣ 获取 storage 实例

```python
storage = getattr(app.state, "storage", None)
if storage is None:
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Storage service not available",
    )
```

- `app.state.storage` 是 AgentScope 的 `AsyncSQLAlchemyStorage` 实例
- 在 [main.py:112](../../backend/app/main.py#L112) 创建并注入
- 如果未初始化 → 返回 503

---

## 3️⃣ 查询智能体

```python
record = await storage.get_agent(user_id, agent_id)

if record is None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Agent {agent_id} not found",
    )
```

- 调用 AgentScope 的 `get_agent` 方法
- 从 `agents` 表查询
- 不存在 → 返回 404

---

## 4️⃣ 转换返回格式

```python
data = record.data
return {
    "name": data.name,
    "system_prompt": data.system_prompt,
    "context_config": data.context_config.model_dump() if data.context_config else None,
    "react_config": data.react_config.model_dump() if data.react_config else None,
    "invite_config": data.invite_config.model_dump() if data.invite_config else None,
    "owner_user_id": record.user_id,
}
```

| 字段 | 来源 | 说明 |
|------|------|------|
| `name` | `data.name` | 智能体名称 |
| `system_prompt` | `data.system_prompt` | 系统提示词 |
| `context_config` | `data.context_config.model_dump()` | 上下文配置 |
| `react_config` | `data.react_config.model_dump()` | ReAct 配置 |
| `invite_config` | `data.invite_config.model_dump()` | 邀请配置 |
| `owner_user_id` | `record.user_id` | 智能体所有者 ID |

---

## 5️⃣ 数据流向

```
agents 表
    ↓
storage.get_agent(user_id, agent_id)
    ↓
AgentRecord 对象
    ↓
record.data (AgentConfig)
    ↓
model_dump() 转换
    ↓
返回 dict
```

---

## 6️⃣ 调用关系

```python
# publish_agent 函数中调用
agent_data = await _fetch_agent_snapshot(app, agent_id, user_id)
agent_name = agent_data.get("name", agent_id)
agent_description = agent_data.get("system_prompt", "")[:500]
```

---

## storage.get_agent 执行流程

**文件：** [_storage.py:1015-1025](../../../agentScope/src/agentscope/app/storage/_sql/_storage.py#L1015-L1025)

```python
async def get_agent(
    self,
    user_id: str,
    agent_id: str,
) -> AgentRecord | None:
    """Fetch one agent record; owner-scoped."""
    async with self._session() as sess:
        row = await sess.get(AgentRow, agent_id)  # ① 按主键查询
    if row is None or row.user_id != user_id:      # ② 验证所有者
        return None
    return _to_record(row, AgentRecord)            # ③ 转换格式
```

### ① 按主键查询

```python
row = await sess.get(AgentRow, agent_id)
```

**生成 SQL：**
```sql
SELECT user_id, source, id, created_at, updated_at, payload
FROM agents
WHERE id = '8a2fb85bd0e549459956990f0c17ac06';
```

**对应模型：** [AgentRow](../../../agentScope/src/agentscope/app/storage/_sql/_tables.py#L115-L133)

```python
class AgentRow(_JsonRecordMixin):
    __tablename__ = "agents"
    
    user_id: Mapped[str] = mapped_column(String(_ID_LEN), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
```

### ② 验证所有者

```python
if row is None or row.user_id != user_id:
    return None
```

**关键安全检查：**
- 如果记录不存在 → 返回 `None`
- 如果 `row.user_id != user_id` → 返回 `None`（越权保护）

### ③ 转换格式

```python
return _to_record(row, AgentRecord)
```

将 `AgentRow`（SQLAlchemy 模型）转换为 `AgentRecord`（Pydantic 模型）

---

## 安全性分析

**`storage.get_agent(user_id, agent_id)` 已经过滤了 `user_id`！**

```python
if row is None or row.user_id != user_id:
    return None
```

所以 `publish_agent` 调用 `_fetch_agent_snapshot` 时：
- 如果智能体不属于当前用户 → `record` 为 `None`
- → 返回 404 错误

**结论：** AgentScope 的实现是安全的，已经做了所有者校验。

---

## 相关文件

| 文件 | 作用 |
|------|------|
| [service.py](../../backend/app/publish/service.py) | 平台业务逻辑 |
| [main.py](../../backend/app/main.py) | storage 实例创建 |
| [_storage.py](../../../agentScope/src/agentscope/app/storage/_sql/_storage.py) | AgentScope 存储实现 |
| [_tables.py](../../../agentScope/src/agentscope/app/storage/_sql/_tables.py) | AgentRow 表定义 |
| [_mappers.py](../../../agentScope/src/agentscope/app/storage/_sql/_mappers.py) | ORM 转换 |
