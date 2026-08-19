# 发布智能体完整流程

从前端点击"发布智能体"按钮到数据存储到数据库的完整流程。

---

## 1️⃣ 前端：用户点击"发布"按钮

**文件：** [PublishAgentDialog.tsx](../frontend/src/components/dialog/PublishAgentDialog.tsx#L103-L134)

```typescript
const handleSubmit = async () => {
    // 1. 校验：releaseNotes 不能为空
    // 2. 如果是 task 模式，校验 input_schema
    // 3. 调用 API
    const result = await publishApi.publish(agentId, {
        release_notes: releaseNotes,
        execution_mode: executionMode,
        input_schema: inputSchema,
    });
}
```

---

## 2️⃣ 前端 API：发送 HTTP 请求

**文件：** [publish.ts](../frontend/src/api/publish.ts#L19-L20)

```typescript
publish: (agentId: string, body: PublishRequest) =>
    client.post<PublishResponse>(`/publish/agent/${agentId}`, body)
```

**请求格式：**
```
POST /publish/agent/{agent_id}
Body: { release_notes, execution_mode, input_schema }
```

---

## 3️⃣ 后端路由：接收请求

**文件：** [router.py](../backend/app/publish/router.py#L43-L60)

```python
@router.post("/agent/{agent_id}")
async def publish_agent(
    agent_id: str,
    body: PublishRequest,          # Pydantic 校验
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(Role.DEVELOPER)),  # 权限校验
):
    return await service.publish_agent(
        db=db, app=request.app, agent_id=agent_id,
        user_id=user.user_id,
        release_notes=body.release_notes,
        execution_mode=body.execution_mode,
        input_schema=body.input_schema,
    )
```

**做了什么：**
- Pydantic 校验请求体（`release_notes` 最少 1 字符）
- JWT 认证 + 角色校验（必须是 `DEVELOPER`）
- 注入数据库会话
- 调用 service 层

---

## 4️⃣ 后端服务：业务逻辑

**文件：** [service.py](../backend/app/publish/service.py#L78-L192)

```python
async def publish_agent(db, app, agent_id, user_id, release_notes, execution_mode, input_schema):
    
    # ① 参数校验
    if not release_notes.strip(): raise 422
    if execution_mode not in ("chat", "task"): raise 422
    if execution_mode == "task" and not input_schema: raise 422
    
    # ② 从 AgentScope 获取智能体配置快照
    agent_data = await _fetch_agent_snapshot(app, agent_id, user_id)
    
    # ③ 生成版本号（SHA256 前 7 位）
    version = generate_version(agent_id, release_notes, now)
    
    # ④ 查询是否已发布
    publication = db.execute(select(AgentPublication).where(...))
    
    # ⑤ 如果已存在 → 更新；不存在 → 新建
    if publication:
        # 更新 agent_publications 表
        publication.agent_name = agent_name
        publication.current_version = version
        ...
        # 标记旧版本为非当前
        update(AgentVersion).where(...).values(is_current=False)
    else:
        # 插入 agent_publications 表
        publication = AgentPublication(...)
        db.add(publication)
    
    # ⑥ 插入 agent_versions 表（版本记录）
    version_record = AgentVersion(...)
    db.add(version_record)
    
    # ⑦ 提交事务
    await db.commit()
    
    return { version, agent_id, published_at }
```

---

## 5️⃣ 获取智能体快照（关键步骤）

**文件：** [service.py](../backend/app/publish/service.py#L43-L73)

```python
async def _fetch_agent_snapshot(app, agent_id, user_id):
    # 从 app.state.storage（AgentScope 的 AsyncSQLAlchemyStorage）获取
    storage = app.state.storage
    record = await storage.get_agent(user_id, agent_id)
    
    # 转换为发布所需的格式
    return {
        "name": record.data.name,
        "system_prompt": record.data.system_prompt,
        "context_config": record.data.context_config.model_dump(),
        "react_config": record.data.react_config.model_dump(),
        "invite_config": record.data.invite_config.model_dump(),
        "owner_user_id": record.user_id,
    }
```

**数据来源：** `agents` 表的 `payload` JSON 字段

---

## 6️⃣ 数据库存储

最终写入两张表：

### [agent_publications](../backend/app/publish/models.py#L18-L58)（发布状态）

| 字段 | 说明 |
|------|------|
| agent_id | 智能体 ID |
| agent_name | 智能体名称 |
| published | True |
| current_version | 版本号 |
| execution_mode | chat/task |
| input_schema | JSON Schema (task 模式) |
| published_by | 发布者 user_id |
| published_at | 发布时间 |

### [agent_versions](../backend/app/publish/models.py#L61-L96)（版本历史）

| 字段 | 说明 |
|------|------|
| publication_id | 关联 agent_publications.id |
| version | 版本号（SHA256 前 7 位） |
| release_notes | 发布说明 |
| execution_mode | chat/task |
| input_schema | JSON Schema |
| agent_snapshot | 智能体配置快照（用于回滚） |
| published_by | 发布者 user_id |
| is_current | 是否为当前版本 |

---

## 流程图

```
┌─────────────────────────────────────────────────────────────────────┐
│  前端 PublishAgentDialog                                            │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 1. 校验 releaseNotes / input_schema                         │   │
│  │ 2. POST /publish/agent/{agent_id}                           │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────┐
│  后端 router.py                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 1. Pydantic 校验请求体                                       │   │
│  │ 2. JWT 认证 + require_role(DEVELOPER)                       │   │
│  │ 3. 注入 DB session                                          │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────┐
│  后端 service.py                                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 1. 参数校验 (release_notes, execution_mode)                 │   │
│  │ 2. _fetch_agent_snapshot()                                  │   │
│  │    └→ agents 表 → record.data (name, system_prompt, ...)    │   │
│  │ 3. generate_version() → SHA256 前 7 位                      │   │
│  │ 4. 查询 agent_publications 是否存在                         │   │
│  │    ├─ 存在 → 更新 + 旧版本 is_current=False                │   │
│  │    └─ 不存在 → 新建                                         │   │
│  │ 5. 插入 agent_versions                                      │   │
│  │ 6. db.commit()                                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────┐
│  SQLite: backend/app/core/agent_platform.db                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ agent_publications  ← 发布状态（1 行/agent）                │   │
│  │ agent_versions      ← 版本历史（1 行/次发布）               │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## ⚠️ 可能出错的地方

| 环节 | 可能的错误 | 错误码 |
|------|-----------|--------|
| 前端校验 | releaseNotes 为空 | 前端提示 |
| 前端校验 | task 模式无 input_schema | 前端提示 |
| Pydantic 校验 | release_notes 长度 < 1 | 422 |
| JWT 认证 | token 无效或过期 | 401 |
| 角色校验 | 用户不是 DEVELOPER | 403 |
| `_fetch_agent_snapshot` | 智能体不存在 | 404 |
| `_fetch_agent_snapshot` | storage 未初始化 | 503 |
| `_fetch_agent_snapshot` | record.data 属性缺失 | 500 (INTERNAL_ERROR) |
| 参数校验 | execution_mode 无效 | 422 |
| 数据库 | 表不存在 | 500 |
| 数据库 | commit 失败 | 500 |

---

## 版本号生成算法

**文件：** [service.py](../backend/app/publish/service.py#L27-L38)

```python
def generate_version(agent_id: str, release_notes: str, timestamp: datetime) -> str:
    content = f"{agent_id}:{release_notes}:{timestamp.isoformat()}"
    return hashlib.sha256(content.encode()).hexdigest()[:7]
```

**示例：** `a3f2c8d`（7 位十六进制字符串）

---

## 相关文件索引

| 文件 | 作用 |
|------|------|
| [PublishAgentDialog.tsx](../frontend/src/components/dialog/PublishAgentDialog.tsx) | 发布对话框 UI |
| [publish.ts](../frontend/src/api/publish.ts) | 前端 API 封装 |
| [types.ts](../frontend/src/api/types.ts) | TypeScript 类型定义 |
| [router.py](../backend/app/publish/router.py) | 后端路由 |
| [service.py](../backend/app/publish/service.py) | 业务逻辑 |
| [models.py](../backend/app/publish/models.py) | SQLAlchemy 模型 |
| [exceptions.py](../backend/app/core/exceptions.py) | 异常处理 |
| [database.py](../backend/app/core/database.py) | 数据库初始化 |
| [main.py](../backend/app/main.py) | 应用入口 |
