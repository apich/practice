# 智能体列表 API

获取智能体列表的路由汇总。

---

## 1️⃣ 获取当前用户的智能体列表

由 AgentScope 框架提供，返回当前用户创建的所有智能体。

**前端 API：** [agent.ts](../frontend/src/api/agent.ts#L12)

```typescript
list: () => client.get<AgentListResponse>('/agent/')
```

**路由：** `GET /agent/`

**数据来源：** `agents` 表

**返回字段：**
```typescript
interface AgentListResponse {
    agents: AgentView[];
    total: number;
}
```

---

## 2️⃣ 获取所有已发布的智能体

返回所有已发布的智能体，终端用户可见。

**前端 API：** [publish.ts](../frontend/src/api/publish.ts#L28-L30)

```typescript
listPublished: () => client.get<PublishedAgentDetail[]>('/publish/list')
```

**后端路由：** [router.py](../backend/app/publish/router.py#L73-L78)

```python
@router.get("/list")
async def list_published(db: AsyncSession = Depends(get_db)) -> list[dict]:
    """List all published agents (visible to end users)."""
    return await service.list_published(db)
```

**数据来源：** `agent_publications` 表（`published = True`）

**返回字段：**
```typescript
interface PublishedAgentDetail {
    id: string;
    agent_id: string;
    agent_name: string;
    agent_description: string;
    published: boolean;
    current_version: string;
    execution_mode: 'chat' | 'task';
    input_schema: JSONSchema | null;
    published_at: string;
    unpublished_at: string | null;
    published_by: string;
}
```

---

## 3️⃣ 获取当前开发者发布的智能体

返回当前登录的开发者发布的智能体。

**前端 API：** [publish.ts](../frontend/src/api/publish.ts#L32-L34)

```typescript
listMyPublished: () => client.get<PublishedAgentDetail[]>('/publish/my')
```

**后端路由：** [router.py](../backend/app/publish/router.py#L81-L87)

```python
@router.get("/my")
async def list_my_published(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(Role.DEVELOPER)),
) -> list[dict]:
    """List agents published by the current developer."""
    return await service.list_my_published(db, user.user_id)
```

**数据来源：** `agent_publications` 表（`published_by = user_id`）

**权限：** 需要 `DEVELOPER` 角色

---

## 4️⃣ 获取单个已发布的智能体详情

**前端 API：** [publish.ts](../frontend/src/api/publish.ts#L36-L38)

```typescript
getPublished: (agentId: string) =>
    client.get<PublishedAgentDetail>(`/publish/${agentId}`)
```

**后端路由：** [router.py](../backend/app/publish/router.py#L90-L96)

```python
@router.get("/{agent_id}")
async def get_published(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get a single published agent's details (including input_schema)."""
    return await service.get_published(db, agent_id)
```

**数据来源：** `agent_publications` 表

---

## 5️⃣ 获取智能体版本历史

**前端 API：** [publish.ts](../frontend/src/api/publish.ts#L40-L42)

```typescript
getVersions: (agentId: string) =>
    client.get<AgentVersion[]>(`/publish/${agentId}/versions`)
```

**后端路由：** [router.py](../backend/app/publish/router.py#L99-L106)

```python
@router.get("/{agent_id}/versions")
async def get_versions(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """Get version history for an agent."""
    return await service.get_versions(db, agent_id)
```

**数据来源：** `agent_versions` 表

**权限：** 需要登录

---

## 路由汇总

| 路由 | 方法 | 用途 | 数据来源 | 权限 |
|------|------|------|----------|------|
| `/agent/` | GET | 用户自己创建的智能体 | `agents` 表 | 登录 |
| `/publish/list` | GET | 所有已发布的智能体 | `agent_publications` 表 | 无 |
| `/publish/my` | GET | 当前开发者发布的智能体 | `agent_publications` 表 | DEVELOPER |
| `/publish/{agent_id}` | GET | 单个已发布智能体详情 | `agent_publications` 表 | 无 |
| `/publish/{agent_id}/versions` | GET | 版本历史 | `agent_versions` 表 | 登录 |

---

## 相关文件

| 文件 | 作用 |
|------|------|
| [agent.ts](../frontend/src/api/agent.ts) | 智能体 CRUD API |
| [publish.ts](../frontend/src/api/publish.ts) | 发布相关 API |
| [router.py](../backend/app/publish/router.py) | 后端路由定义 |
| [service.py](../backend/app/publish/service.py) | 业务逻辑 |
| [models.py](../backend/app/publish/models.py) | 数据库模型 |
