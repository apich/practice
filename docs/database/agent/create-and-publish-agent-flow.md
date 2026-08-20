# 创建与发布智能体流程

智能体从创建到发布的完整数据流。

---

## 核心流程

```
┌─────────────────────────────────────────────────────────────┐
│ ① 创建智能体                                                │
│    POST /agent/                                             │
│    → storage.upsert_agent(user_id, record)                  │
│    → 写入 agents 表                                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ ② 发布智能体                                                │
│    POST /publish/agent/{agent_id}                           │
│    → _fetch_agent_snapshot() 从 agents 表读取               │
│    → 写入 agent_publications 表                             │
│    → 写入 agent_versions 表                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## ① 创建智能体

**路由：** `POST /agent/`（AgentScope 提供）

**源码：** [_agent.py:171-213](../../../../../agentScope/src/agentscope/app/_router/_agent.py#L171-L213)

```python
async def create_agent(body, user_id, storage):
    # ... 构建 AgentRecord
    agent_id = await storage.upsert_agent(user_id, record)  # 写入 agents 表
    return CreateAgentResponse(agent_id=agent_id)
```

**写入数据：** `agents` 表

| 字段 | 说明 |
|------|------|
| `id` | 智能体 ID |
| `user_id` | 创建者 ID |
| `source` | 来源 |
| `payload` | 智能体配置 JSON（名称、提示词、模型等） |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

---

## ② 发布智能体

**路由：** `POST /publish/agent/{agent_id}`

**入口：** [router.py:43-60](../../../backend/app/publish/router.py#L43-L60)

```python
@router.post("/agent/{agent_id}")
async def publish_agent(
    agent_id: str,
    body: PublishRequest,
    user: User = Depends(require_role(Role.DEVELOPER)),
):
    return await service.publish_agent(
        db=db, app=request.app, agent_id=agent_id, user_id=user.user_id, ...
    )
```

**业务逻辑：** [service.py:78-192](../../../backend/app/publish/service.py#L78-L192)

```python
async def publish_agent(db, app, agent_id, user_id, ...):
    # 1. 从 agents 表读取智能体配置
    agent_data = await _fetch_agent_snapshot(app, agent_id, user_id)
    
    # 2. 生成版本号
    version = generate_version(agent_id, release_notes, now)
    
    # 3. 写入 agent_publications 表
    publication = AgentPublication(...)
    db.add(publication)
    
    # 4. 写入 agent_versions 表
    version_record = AgentVersion(...)
    db.add(version_record)
    
    # 5. 提交事务
    await db.commit()
```

---

## 数据表关系

### agents 表（创建时写入）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | VARCHAR(255) | 主键，智能体 ID |
| `user_id` | VARCHAR(255) | 创建者 ID |
| `source` | VARCHAR(16) | 来源 |
| `payload` | JSON | 智能体配置 |
| `created_at` | DATETIME | 创建时间 |
| `updated_at` | DATETIME | 更新时间 |

### agent_publications 表（发布时写入）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | VARCHAR(36) | 主键 |
| `agent_id` | VARCHAR(100) | 智能体 ID（关联 agents.id） |
| `agent_name` | VARCHAR(255) | 智能体名称 |
| `published` | BOOLEAN | 是否发布 |
| `current_version` | VARCHAR(20) | 当前版本号 |
| `execution_mode` | VARCHAR(10) | 执行模式（chat/task） |
| `input_schema` | JSON | 任务模式输入 schema |
| `published_by` | VARCHAR(36) | 发布者 ID |
| `published_at` | DATETIME | 发布时间 |

### agent_versions 表（发布时写入）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | VARCHAR(36) | 主键 |
| `publication_id` | VARCHAR(36) | 关联 agent_publications.id |
| `agent_id` | VARCHAR(100) | 智能体 ID |
| `version` | VARCHAR(20) | 版本号（SHA256 前 7 位） |
| `release_notes` | TEXT | 发布说明 |
| `agent_snapshot` | JSON | 智能体配置快照（用于回滚） |
| `published_by` | VARCHAR(36) | 发布者 ID |
| `is_current` | BOOLEAN | 是否为当前版本 |

---

## 版本号生成算法

**文件：** [service.py:27-38](../../../backend/app/publish/service.py#L27-L38)

```python
def generate_version(agent_id: str, release_notes: str, timestamp: datetime) -> str:
    content = f"{agent_id}:{release_notes}:{timestamp.isoformat()}"
    return hashlib.sha256(content.encode()).hexdigest()[:7]
```

**示例：** `a3f2c8d`（7 位十六进制字符串）

---

## 数据流向图

```
创建智能体                          发布智能体
    ↓                                   ↓
┌─────────┐                      ┌─────────────────┐
│  agents │ ──── 读取配置 ────→ │ agent_publications│
│  表     │                      │       表         │
└─────────┘                      └─────────────────┘
                                         ↓
                                 ┌─────────────────┐
                                 │ agent_versions   │
                                 │       表         │
                                 └─────────────────┘
```

---

## 相关文档

| 文档 | 说明 |
|------|------|
| [fetch-agent-snapshot-flow.md](fetch-agent-snapshot-flow.md) | 获取智能体快照函数详解 |
| [get-published-agent-query-flow.md](get-published-agent-query-flow.md) | 查询已发布智能体流程 |
