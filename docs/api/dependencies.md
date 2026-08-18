# 依赖函数与路由对照表

## 依赖函数分类

| 分类 | 依赖函数 | 代码里写的是 | 实际执行的是 | 返回值 |
|---|---|---|---|---|
| **AgentScope 框架路由** | `get_current_user_id` | `Depends(get_current_user_id)` | `_platform_get_user_id`（被覆盖） | `str`（user_id） |
| **平台项目路由** | `get_current_user` | `Depends(get_current_user)` | `get_current_user`（查数据库） | `User` 对象 |
| **平台项目路由** | `require_role` | `Depends(require_role(...))` | `require_role` 内部调用 `get_current_user` | `User` 对象（角色不对则 403） |
| **平台项目路由** | `require_permissions` | `Depends(require_permissions([...]))` | `require_permissions`（从 Cookie 读权限） | `None`（权限不对则 403） |

### 覆盖机制

AgentScope 的 `get_current_user_id` 在 `main.py` 中被覆盖：

```python
app.dependency_overrides[_default_get_user_id] = _platform_get_user_id
```

FastAPI 运行时查 `dependency_overrides` 字典，发现有覆盖就执行替代函数。AgentScope 代码不用改，一处覆盖全局生效。

---

## AgentScope 框架路由

所有路由都使用 `Depends(get_current_user_id)`，实际执行 `_platform_get_user_id`（从 JWT 提取 user_id）。

> 源码路径基于 agentscope 可编辑安装目录：`C:\Users\st\Desktop\agentScope\src\agentscope\app\_router\`

### 智能体管理 `/agent`

| 方法 | 路径 | 依赖函数 | 源文件 |
|---|---|---|---|
| GET | `/agent/` | `get_current_user_id` | [_agent.py](../../../agentScope/src/agentscope/app/_router/_agent.py) |
| POST | `/agent/` | `get_current_user_id` | [_agent.py](../../../agentScope/src/agentscope/app/_router/_agent.py) |
| GET | `/agent/{id}` | `get_current_user_id` | [_agent.py](../../../agentScope/src/agentscope/app/_router/_agent.py) |
| PUT | `/agent/{id}` | `get_current_user_id` | [_agent.py](../../../agentScope/src/agentscope/app/_router/_agent.py) |
| DELETE | `/agent/{id}` | `get_current_user_id` | [_agent.py](../../../agentScope/src/agentscope/app/_router/_agent.py) |

### 会话管理 `/sessions`

| 方法 | 路径 | 依赖函数 | 源文件 |
|---|---|---|---|
| GET | `/sessions/` | `get_current_user_id` | [_session.py](../../../agentScope/src/agentscope/app/_router/_session.py) |
| POST | `/sessions/` | `get_current_user_id` | [_session.py](../../../agentScope/src/agentscope/app/_router/_session.py) |
| DELETE | `/sessions/{id}` | `get_current_user_id` | [_session.py](../../../agentScope/src/agentscope/app/_router/_session.py) |
| PUT | `/sessions/{id}` | `get_current_user_id` | [_session.py](../../../agentScope/src/agentscope/app/_router/_session.py) |
| GET | `/sessions/{id}/status` | `get_current_user_id` | [_session.py](../../../agentScope/src/agentscope/app/_router/_session.py) |
| GET | `/sessions/{id}/events` | `get_current_user_id` | [_session.py](../../../agentScope/src/agentscope/app/_router/_session.py) |

### 聊天 `/chat`

| 方法 | 路径 | 依赖函数 | 源文件 |
|---|---|---|---|
| POST | `/chat` | `get_current_user_id` | [_chat.py](../../../agentScope/src/agentscope/app/_router/_chat.py) |

### 凭证管理 `/credential`

| 方法 | 路径 | 依赖函数 | 源文件 |
|---|---|---|---|
| GET | `/credential/` | `get_current_user_id` | [_credential.py](../../../agentScope/src/agentscope/app/_router/_credential.py) |
| POST | `/credential/` | `get_current_user_id` | [_credential.py](../../../agentScope/src/agentscope/app/_router/_credential.py) |
| PUT | `/credential/{id}` | `get_current_user_id` | [_credential.py](../../../agentScope/src/agentscope/app/_router/_credential.py) |
| DELETE | `/credential/{id}` | `get_current_user_id` | [_credential.py](../../../agentScope/src/agentscope/app/_router/_credential.py) |

### 知识库 `/knowledge_bases` `/knowledge`

| 方法 | 路径 | 依赖函数 | 源文件 |
|---|---|---|---|
| GET | `/knowledge_bases/` | `get_current_user_id` | [_knowledge_base.py](../../../agentScope/src/agentscope/app/_router/_knowledge_base.py) |
| POST | `/knowledge_bases/` | `get_current_user_id` | [_knowledge_base.py](../../../agentScope/src/agentscope/app/_router/_knowledge_base.py) |
| GET | `/knowledge_bases/{id}` | `get_current_user_id` | [_knowledge_base.py](../../../agentScope/src/agentscope/app/_router/_knowledge_base.py) |
| PUT | `/knowledge_bases/{id}` | `get_current_user_id` | [_knowledge_base.py](../../../agentScope/src/agentscope/app/_router/_knowledge_base.py) |
| DELETE | `/knowledge_bases/{id}` | `get_current_user_id` | [_knowledge_base.py](../../../agentScope/src/agentscope/app/_router/_knowledge_base.py) |
| POST | `/knowledge/{id}/upload` | `get_current_user_id` | [_knowledge_base.py](../../../agentScope/src/agentscope/app/_router/_knowledge_base.py) |

### MCP Hub `/mcp`

| 方法 | 路径 | 依赖函数 | 源文件 |
|---|---|---|---|
| GET | `/mcp/` | `get_current_user_id` | [_mcp.py](../../../agentScope/src/agentscope/app/_router/_mcp.py) |
| POST | `/mcp/` | `get_current_user_id` | [_mcp.py](../../../agentScope/src/agentscope/app/_router/_mcp.py) |
| DELETE | `/mcp/{id}` | `get_current_user_id` | [_mcp.py](../../../agentScope/src/agentscope/app/_router/_mcp.py) |

### Skill Hub `/skill`

| 方法 | 路径 | 依赖函数 | 源文件 |
|---|---|---|---|
| GET | `/skill/` | `get_current_user_id` | [_skill.py](../../../agentScope/src/agentscope/app/_router/_skill.py) |
| POST | `/skill/` | `get_current_user_id` | [_skill.py](../../../agentScope/src/agentscope/app/_router/_skill.py) |
| DELETE | `/skill/{id}` | `get_current_user_id` | [_skill.py](../../../agentScope/src/agentscope/app/_router/_skill.py) |

### 频道适配 `/channel`

| 方法 | 路径 | 依赖函数 | 源文件 |
|---|---|---|---|
| GET | `/channel/` | `get_current_user_id` | [_channel.py](../../../agentScope/src/agentscope/app/_router/_channel.py) |
| POST | `/channel/` | `get_current_user_id` | [_channel.py](../../../agentScope/src/agentscope/app/_router/_channel.py) |
| GET | `/channel/{id}` | `get_current_user_id` | [_channel.py](../../../agentScope/src/agentscope/app/_router/_channel.py) |
| PUT | `/channel/{id}` | `get_current_user_id` | [_channel.py](../../../agentScope/src/agentscope/app/_router/_channel.py) |
| DELETE | `/channel/{id}` | `get_current_user_id` | [_channel.py](../../../agentScope/src/agentscope/app/_router/_channel.py) |

### 定时任务 `/schedule`

| 方法 | 路径 | 依赖函数 | 源文件 |
|---|---|---|---|
| GET | `/schedule/` | `get_current_user_id` | [_schedule.py](../../../agentScope/src/agentscope/app/_router/_schedule.py) |
| POST | `/schedule/` | `get_current_user_id` | [_schedule.py](../../../agentScope/src/agentscope/app/_router/_schedule.py) |
| PUT | `/schedule/{id}` | `get_current_user_id` | [_schedule.py](../../../agentScope/src/agentscope/app/_router/_schedule.py) |
| DELETE | `/schedule/{id}` | `get_current_user_id` | [_schedule.py](../../../agentScope/src/agentscope/app/_router/_schedule.py) |

### 资源中心 `/hub`

| 方法 | 路径 | 依赖函数 | 源文件 |
|---|---|---|---|
| GET | `/hub/mcp` | `get_current_user_id` | [_hub.py](../../../agentScope/src/agentscope/app/_router/_hub.py) |
| GET | `/hub/skill` | `get_current_user_id` | [_hub.py](../../../agentScope/src/agentscope/app/_router/_hub.py) |

### 工作空间 `/workspace`

| 方法 | 路径 | 依赖函数 | 源文件 |
|---|---|---|---|
| GET | `/workspace/` | `get_current_user_id` | [_workspace.py](../../../agentScope/src/agentscope/app/_router/_workspace.py) |
| GET | `/workspace/{id}` | `get_current_user_id` | [_workspace.py](../../../agentScope/src/agentscope/app/_router/_workspace.py) |

### 模型管理 `/model` `/tts-model` `/embedding-model`

| 方法 | 路径 | 依赖函数 | 源文件 |
|---|---|---|---|
| GET | `/model/` | `get_current_user_id` | [_model.py](../../../agentScope/src/agentscope/app/_router/_model.py) |
| GET | `/tts-model/` | `get_current_user_id` | [_tts_model.py](../../../agentScope/src/agentscope/app/_router/_tts_model.py) |
| GET | `/embedding-model/` | `get_current_user_id` | [_embedding_model.py](../../../agentScope/src/agentscope/app/_router/_embedding_model.py) |

### 健康检查 `/health`

| 方法 | 路径 | 依赖函数 | 源文件 |
|---|---|---|---|
| GET | `/health` | 无（公开接口） | [_health.py](../../../agentScope/src/agentscope/app/_router/_health.py) |

---

## 平台项目路由

> 源码路径：`C:\Users\st\Desktop\agent-platform\backend\app\`

### 认证模块 `/auth`

| 方法 | 路径 | 依赖函数 | 说明 | 源文件 |
|---|---|---|---|---|
| POST | `/auth/login` | 无 | 公开，登录 | [router.py](../../backend/app/auth/router.py) |
| GET | `/auth/me` | `get_current_user` | 当前用户信息 | [router.py](../../backend/app/auth/router.py) |
| POST | `/auth/refresh` | 无 | 刷新 token | [router.py](../../backend/app/auth/router.py) |
| POST | `/auth/logout` | `get_current_user` | 登出 | [router.py](../../backend/app/auth/router.py) |
| POST | `/auth/register` | `require_role(DEVELOPER)` | 注册 | [router.py](../../backend/app/auth/router.py) |
| GET | `/auth/oauth/login` | 无 | OAuth 授权 URL | [router.py](../../backend/app/auth/router.py) |
| POST | `/auth/callback` | 无 | OAuth 回调 | [router.py](../../backend/app/auth/router.py) |

### 发布模块 `/publish`

| 方法 | 路径 | 依赖函数 | 说明 | 源文件 |
|---|---|---|---|---|
| POST | `/publish/agent/{id}` | `require_role(DEVELOPER)` | 发布/更新 | [router.py](../../backend/app/publish/router.py) |
| GET | `/publish/list` | 无 | 浏览已发布 | [router.py](../../backend/app/publish/router.py) |
| GET | `/publish/my` | `require_role(DEVELOPER)` | 我发布的 | [router.py](../../backend/app/publish/router.py) |
| GET | `/publish/{id}` | 无 | 智能体详情 | [router.py](../../backend/app/publish/router.py) |
| GET | `/publish/{id}/versions` | `get_current_user` | 版本历史 | [router.py](../../backend/app/publish/router.py) |
| GET | `/publish/{id}/versions/{ver}` | `get_current_user` | 版本详情 | [router.py](../../backend/app/publish/router.py) |
| POST | `/publish/{id}/rollback/{ver}` | `require_role(DEVELOPER)` | 回滚版本 | [router.py](../../backend/app/publish/router.py) |
| POST | `/publish/{id}/execute` | `get_current_user` | 任务模式执行 | [router.py](../../backend/app/publish/router.py) |
| POST | `/publish/{id}/chat` | `get_current_user` | 对话模式 | [router.py](../../backend/app/publish/router.py) |

### 下架模块 `/unpublish`

| 方法 | 路径 | 依赖函数 | 说明 | 源文件 |
|---|---|---|---|---|
| POST | `/unpublish/agent/{id}` | `require_role(DEVELOPER)` | 下架智能体 | [router.py](../../backend/app/publish/router.py) |
