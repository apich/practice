# 后端 API 接口文档

> 基础地址：`http://localhost:9000`
> 认证方式：JWT Bearer Token（`Authorization: Bearer <access_token>`）

---

## 1. 认证模块 `/auth`

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| POST | `/auth/login` | 登录（本地密码或 OAuth2 委托） | 公开 |
| GET | `/auth/me` | 获取当前用户信息 | 已登录 |
| POST | `/auth/refresh` | 刷新 access_token | 已登录 |
| POST | `/auth/logout` | 登出（客户端清除 token） | 已登录 |
| POST | `/auth/register` | 注册新用户 | developer |
| GET | `/auth/oauth/login` | 获取 OAuth2 授权 URL（PKCE） | 公开 |
| POST | `/auth/callback` | OAuth2 回调（code 换 token） | 公开 |

### 登录流程

```
POST /auth/login
Body: {"username": "xxx", "password": "xxx"}

响应:
- 200: {"access_token", "refresh_token", "token_type", "user_id", "username", "role"}
- 401: {"detail": "Incorrect username or password"}

Cookie 写入:
- user_permissions_0: gzip+base64 编码的权限数据（分片）
- user_permissions_count: 分片数量
```

---

## 2. 智能体发布模块 `/publish`

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| POST | `/publish/agent/{agent_id}` | 发布/更新智能体 | developer |
| GET | `/publish/list` | 浏览所有已发布智能体 | 公开 |
| GET | `/publish/my` | 查看我发布的智能体 | developer |
| GET | `/publish/{agent_id}` | 查看单个智能体详情 | 公开 |
| GET | `/publish/{agent_id}/versions` | 版本历史 | 已登录 |
| GET | `/publish/{agent_id}/versions/{ver}` | 版本详情 | 已登录 |
| POST | `/publish/{agent_id}/rollback/{ver}` | 回滚到指定版本 | developer |
| POST | `/publish/{agent_id}/execute` | 执行任务模式智能体 | 已登录 |
| POST | `/publish/{agent_id}/chat` | 开始对话模式 | 已登录 |

---

## 3. 智能体下架模块 `/unpublish`

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| POST | `/unpublish/agent/{agent_id}` | 下架智能体 | developer |

---

## 4. AgentScope 路由（由 agentscope 框架提供）

以下路由由 `agentscope.create_app` 自动生成，平台通过中间件控制访问权限。

### 4.1 智能体管理 `/agent`

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/agent/` | 列出所有智能体配置 | developer |
| POST | `/agent/` | 创建智能体配置 | developer |
| GET | `/agent/{id}` | 获取智能体配置详情 | developer |
| PUT | `/agent/{id}` | 更新智能体配置 | developer |
| DELETE | `/agent/{id}` | 删除智能体配置 | developer |

### 4.2 对话管理 `/chat` `/sessions`

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| POST | `/chat` | 发送消息并获取流式回复 | 已登录 |
| GET | `/sessions/` | 列出所有会话 | 已登录 |
| GET | `/sessions/{id}` | 获取会话详情 | 已登录 |
| DELETE | `/sessions/{id}` | 删除会话 | 已登录 |

### 4.3 工作空间 `/workspace`

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/workspace/` | 列出工作空间 | 已登录 |
| GET | `/workspace/{id}` | 工作空间详情 | 已登录 |

### 4.4 知识库 `/knowledge` `/knowledge_bases`

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/knowledge_bases/` | 列出知识库 | developer |
| POST | `/knowledge_bases/` | 创建知识库 | developer |
| GET | `/knowledge_bases/{id}` | 知识库详情 | developer |
| PUT | `/knowledge_bases/{id}` | 更新知识库 | developer |
| DELETE | `/knowledge_bases/{id}` | 删除知识库 | developer |
| POST | `/knowledge/{id}/upload` | 上传文档到知识库 | developer |

### 4.5 凭证管理 `/credential`

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/credential/` | 列出凭证 | developer |
| POST | `/credential/` | 创建凭证 | developer |
| PUT | `/credential/{id}` | 更新凭证 | developer |
| DELETE | `/credential/{id}` | 删除凭证 | developer |

### 4.6 MCP Hub `/mcp`

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/mcp/` | 列出 MCP 服务 | developer |
| POST | `/mcp/` | 添加 MCP 服务 | developer |
| DELETE | `/mcp/{id}` | 删除 MCP 服务 | developer |

### 4.7 Skill Hub `/skill`

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/skill/` | 列出 Skill | developer |
| POST | `/skill/` | 添加 Skill | developer |
| DELETE | `/skill/{id}` | 删除 Skill | developer |

### 4.8 频道适配器 `/channel`

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/channel/` | 列出频道 | developer |
| POST | `/channel/` | 创建频道 | developer |
| GET | `/channel/{id}` | 频道详情 | developer |
| PUT | `/channel/{id}` | 更新频道 | developer |
| DELETE | `/channel/{id}` | 删除频道 | developer |

### 4.9 定时任务 `/schedule`

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/schedule/` | 列出定时任务 | developer |
| POST | `/schedule/` | 创建定时任务 | developer |
| PUT | `/schedule/{id}` | 更新定时任务 | developer |
| DELETE | `/schedule/{id}` | 删除定时任务 | developer |

### 4.10 资源中心 `/hub`

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/hub/mcp` | 浏览 MCP Hub（GitHub） | developer |
| GET | `/hub/skill` | 浏览 Skill Hub（Claw） | developer |

### 4.11 模型管理 `/model` `/tts-model` `/embedding-model`

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/model/` | 列出可用模型 | developer |
| GET | `/tts-model/` | 列出 TTS 模型 | developer |
| GET | `/embedding-model/` | 列出 Embedding 模型 | developer |

---

## 5. 健康检查

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/health` | 服务健康检查 | 公开 |

---

## 6. 权限控制说明

### 角色

| 角色 | 说明 |
|---|---|
| `developer` | 开发者，可管理智能体、凭证、知识库等 |
| `end_user` | 终端用户，只能浏览和使用已发布的智能体 |

### 权限验证装饰器

```python
from app.auth.deps import require_permissions

# OR 逻辑：满足其一即可
@router.post("/endpoint", dependencies=[Depends(require_permissions(["perm:a", "perm:b"]))])

# AND 逻辑：必须全部满足
@router.post("/endpoint", dependencies=[Depends(require_permissions(["perm:a", "perm:b"], logic="AND"))])
```

### Cookie 权限数据格式

登录成功后，后端在 Cookie 中写入压缩的权限数据：

| Cookie | 说明 |
|---|---|
| `user_permissions_0` | gzip + base64 编码的权限 JSON（分片 0） |
| `user_permissions_1` | 分片 1（如有） |
| `user_permissions_count` | 分片总数 |

安全属性：`HttpOnly=true`、`SameSite=strict`、`Secure`（生产环境）
