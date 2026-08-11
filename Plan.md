# 智能体平台实施方案

## 概述

将 AgentScope 改造为支持两种用户角色的智能体平台：
- **开发者（developer）**：创建/配置 Agent、技能、MCP、知识库，调试后发布
- **终端用户（end_user）**：仅使用已发布的 Agent，不可修改配置

### 使用模式

平台支持两种 Agent 使用模式，由开发者在发布时定义：

| 模式 | 说明 | 用户流程 |
|------|------|----------|
| **对话模式** | 用户与 Agent 自由对话 | 选择 Agent → 直接进入聊天 |
| **任务模式** | 用户填写预定义表单，Agent 根据参数执行任务 | 选择 Agent → 填写表单 → 提交执行 → 查看结果/进入对话 |

**任务模式设计**（借鉴 Dify）：
- 开发者发布 Agent 时配置 `input_schema`（JSON Schema 格式定义输入参数）
- 终端用户点击 Agent 后，前端根据 `input_schema` 自动渲染表单
- 用户填写表单提交后，参数注入 Agent（作为首条用户消息），Agent 开始执行
- 支持字段类型：`text`、`textarea`、`number`、`select`、`boolean`、`password`

## 项目结构

```
agent-platform/
├── backend/                    # Python 后端（FastAPI）
│   ├── main.py                # 应用入口（调用 agentscope.create_app）
│   ├── pyproject.toml         # 依赖配置（uv）
│   └── uv.lock                # 依赖锁定文件
├── frontend/                   # React 前端（Vite）
│   ├── src/
│   │   ├── api/               # API 客户端层（基于 @agentscope-ai/agentscope）
│   │   ├── components/        # 可复用 UI 组件
│   │   ├── context/           # React Context
│   │   ├── hooks/             # 自定义 Hooks
│   │   ├── i18n/              # 国际化（中/英）
│   │   ├── lib/               # 工具库
│   │   ├── pages/             # 页面组件
│   │   │   ├── channel/       # 渠道管理
│   │   │   ├── chat/          # 聊天页（ChatViewport）
│   │   │   ├── credential/    # 凭证管理
│   │   │   ├── knowledge/     # 知识库管理
│   │   │   ├── mcp/           # MCP 管理
│   │   │   ├── schedule/      # 调度管理
│   │   │   ├── setup/         # 初始化设置
│   │   │   └── skill/         # 技能管理
│   │   └── utils/             # 工具函数
│   ├── package.json
│   └── vite.config.ts         # Vite 配置（API 代理到 localhost:9000）
└── Plan.md
```

**依赖关系**：
- 后端依赖 `agentscope[service]>=2.0.6`（通过 PyPI 安装，**不可修改源码**）
- 前端依赖 `@agentscope-ai/agentscope`（通过 npm 安装）
- 存储：Redis（会话/消息总线）、Qdrant（向量存储）
- 渠道：飞书、Discord

**架构约束**：
- **禁止修改 agentscope 源码**：所有扩展功能必须通过独立模块实现
- 后端通过 `create_app()` 创建 FastAPI 应用，可在其上挂载额外路由和中间件
- 前端 API 层已有独立的 `src/api/` 模块，可在此基础上扩展

### 安全约束：沙盒执行

**问题**：当前 `LocalWorkspaceManager` 使 Agent 的代码执行（MCP 工具、Skill、文件操作）直接在宿主机运行，多租户场景下存在安全风险：
- 终端用户可能触发开发者创建的恶意 Agent
- MCP 工具可能执行任意代码（如 `browser-use` 的 `npx` 命令）
- Skill 可能包含可执行脚本

**方案**：引入沙盒执行环境，支持 Docker 和 Kubernetes 两种后端，部署时通过配置指定

```
backend/_sandbox/
├── __init__.py
├── base.py                # 沙盒抽象基类（定义统一接口）
├── docker_manager.py      # Docker 沙盒实现（docker SDK）
├── k8s_manager.py         # Kubernetes 沙盒实现（kubernetes Python client）
├── factory.py             # 工厂类：根据配置创建对应的沙盒管理器
├── workspace.py           # 沙盒版 WorkspaceManager（替代 LocalWorkspaceManager）
└── Dockerfile             # 沙盒容器镜像（Python + 常用工具）
```

**Dockerfile 基础镜像**（Docker 和 K8s 共用）：
```dockerfile
FROM python:3.11-slim
# 预装常用工具
RUN apt-get update && apt-get install -y \
    git curl nodejs npm \
    && rm -rf /var/lib/apt/lists/*
# 安全限制：非 root 用户
RUN useradd -m sandbox && chown -R sandbox:sandbox /home/sandbox
USER sandbox
WORKDIR /home/sandbox/workspace
```

**沙盒抽象接口**（`base.py`）：
```python
class SandboxManager(ABC):
    @abstractmethod
    def create(self, session_id: str) -> SandboxInstance: ...

    @abstractmethod
    def destroy(self, session_id: str) -> None: ...

    @abstractmethod
    def get_workspace(self, session_id: str) -> WorkspaceBase: ...
```

**部署配置**（通过环境变量或配置文件指定）：
```python
# backend/main.py
SANDBOX_BACKEND = os.getenv("SANDBOX_BACKEND", "local")  # local | docker | k8s

if SANDBOX_BACKEND == "local":
    workspace_manager = LocalWorkspaceManager(basedir="./workspaces")
elif SANDBOX_BACKEND == "docker":
    workspace_manager = DockerSandboxManager(
        image="agent-platform-sandbox:latest",
        resource_limits={"cpu": 1, "memory": "512m"},
    )
elif SANDBOX_BACKEND == "k8s":
    workspace_manager = K8sSandboxManager(
        image="agent-platform-sandbox:latest",
        namespace="agent-sessions",
        resource_limits={"cpu": "1", "memory": "512Mi"},
        storage_class="standard",
    )
```

**沙盒管理逻辑**（两种后端统一）：
1. Session 创建时 → 启动隔离环境（Docker 容器 / K8s Pod），挂载独立存储作为 workspace
2. Agent 执行工具时 → 在隔离环境中执行（文件读写、代码运行、MCP 进程）
3. Session 结束/超时 → 停止并销毁隔离环境，清理存储
4. 资源限制：CPU（1核）、内存（512MB）、磁盘（100MB）、网络（可选隔离）

**Docker vs Kubernetes 对比**：
| 特性 | Docker | Kubernetes |
|------|--------|------------|
| 适用场景 | 单机/小规模部署 | 集群/大规模部署 |
| 编排能力 | 无（需自行管理） | 自动调度、扩缩容 |
| 存储 | Docker Volume | PersistentVolume / emptyDir |
| 网络隔离 | Docker Network | NetworkPolicy |
| 资源限制 | `--cpus` / `--memory` | ResourceQuota / LimitRange |
| 运维复杂度 | 低 | 高（需要 K8s 集群） |
| 依赖 | Docker Engine | K8s cluster + kubectl config |

**开发者 vs 终端用户的沙盒策略**：
| 角色 | 沙盒策略 | 说明 |
|------|----------|------|
| developer | 可选（默认本地） | 开发调试时可直接在宿主机执行，提高效率 |
| end_user | 强制沙盒 | 终端用户执行的 Agent 必须在隔离环境中运行 |

---

## 一、后端改造

### 1.1 用户模型与认证

**新增模块**: `backend/_auth/`

```
backend/_auth/
├── __init__.py
├── models.py              # User 模型、Role 枚举
├── oauth2.py              # OAuth2 password 模式 token 端点
├── middleware.py          # JWT 认证中间件
└── dependencies.py        # FastAPI 依赖注入（获取当前用户）
```

**User 模型**（存储在 PostgreSQL 中）:
- `user_id`: str
- `username`: str
- `password_hash`: str（bcrypt）
- `role`: "developer" | "end_user"
- `created_at`: datetime

**OAuth2 Token 端点**:
- `POST /auth/token` - 密码模式获取 access_token
- `GET /auth/me` - 获取当前用户信息
- `POST /auth/refresh` - 刷新 token

**JWT Token 结构**:
```json
{
  "sub": "user_id",
  "username": "xxx",
  "role": "developer|end_user",
  "exp": 1234567890
}
```

**集成方式**：在 `backend/main.py` 中，`create_app()` 返回的 FastAPI `app` 对象上挂载认证路由和中间件：

```python
# backend/main.py（修改）
from _auth.router import auth_router
from _auth.middleware import AuthMiddleware

app = create_app(...)
app.include_router(auth_router)
app.add_middleware(AuthMiddleware)
```

### 1.2 Agent 发布机制

**设计原则**：不修改 agentscope 源码，通过独立的发布管理模块实现

**新增模块**: `backend/_publish/`

```
backend/_publish/
├── __init__.py
├── models.py              # 发布记录模型（独立数据库表）
├── service.py             # 发布业务逻辑
└── router.py              # 发布相关 API 路由
```

**数据库表设计**（两张表：发布记录 + 版本历史）:

`agent_publications`（发布记录，每个 Agent 一条，跟踪当前发布状态）:
```python
class AgentPublication(Base):
    __tablename__ = "agent_publications"

    id: str                    # 主键
    agent_id: str              # 关联的 Agent ID（来自 agentscope）
    agent_name: str            # Agent 名称（冗余存储）
    agent_description: str     # Agent 描述（冗余存储）
    published: bool            # 是否已发布
    current_version: str       # 当前发布版本号（如 "1.2.0"）
    published_at: datetime     # 最近发布时间
    unpublished_at: datetime   # 取消发布时间
    published_by: str          # 发布者 user_id
    execution_mode: str        # "chat" | "task"（对话模式 / 任务模式）
    input_schema: JSONSchema   # 任务模式的输入参数定义（JSON Schema 格式，对话模式为空）
    created_at: datetime
    updated_at: datetime
```

`agent_versions`（版本历史，每次发布生成一条记录）:
```python
class AgentVersion(Base):
    __tablename__ = "agent_versions"

    id: str                    # 主键
    publication_id: str        # 关联的发布记录 ID
    agent_id: str              # 关联的 Agent ID
    version: str               # 版本号（缩短的 SHA256 哈希，如 "a3f2c8d"，后端自动生成）
    release_notes: str         # 发布内容/更新说明（必填）
    execution_mode: str        # 该版本的执行模式
    input_schema: JSONSchema   # 该版本的输入参数定义
    agent_snapshot: dict       # Agent 配置快照（system_prompt、context_config 等，用于回滚）
    published_by: str          # 发布者 user_id
    published_at: datetime     # 发布时间
    is_current: bool           # 是否为当前活跃版本
```

**API 端点**:
- `POST /publish/agent/{agent_id}` - 发布/更新 Agent（body 包含 release_notes、execution_mode、input_schema，版本号由后端自动生成）
- `POST /unpublish/agent/{agent_id}` - 取消发布
- `GET /publish/list` - 获取所有已发布的 Agent（终端用户可见，显示最新版本号）
- `GET /publish/my` - 获取当前用户发布的 Agent（开发者可见）
- `GET /publish/{agent_id}` - 获取单个已发布 Agent 详情（含当前版本的 input_schema）
- `GET /publish/{agent_id}/versions` - 获取 Agent 的版本历史列表
- `GET /publish/{agent_id}/versions/{version}` - 获取指定版本的详情（含 release_notes）
- `POST /publish/{agent_id}/rollback/{version}` - 回滚到指定版本
- `POST /publish/{agent_id}/execute` - 任务模式：提交表单参数执行 Agent（创建 session 并注入参数）

**实现逻辑**:
1. 发布时：
   - 调用 agentscope 的 `GET /agent/{agent_id}` 获取 Agent 详情
   - 校验 release_notes 非空
   - 后端自动生成版本号：基于发布内容生成缩短的 SHA256 哈希（7位，如 `a3f2c8d`），确保唯一性
   - 如果是首次发布：创建 `agent_publications` 记录 + 第一条 `agent_versions` 记录
   - 如果是更新发布：更新 `agent_publications` 的 `current_version`，新增 `agent_versions` 记录，旧版本 `is_current` 设为 false
   - 保存 Agent 配置快照到 `agent_snapshot`（用于版本回滚）
2. 取消发布时：更新 `agent_publications` 表的 `published` 字段
3. 版本回滚时：将指定版本的 `agent_snapshot` 恢复，更新 `current_version`
4. 查询已发布 Agent 时：从 `agent_publications` 表读取，不依赖 agentscope 的 Agent 列表 API
5. 任务模式执行时（`POST /publish/{agent_id}/execute`）：
   - 接收用户提交的表单参数（JSON）
   - 调用 agentscope 的 `POST /sessions/` 创建新 session
   - 将表单参数格式化为结构化文本，作为首条用户消息发送给 Agent
   - 返回 session_id，前端据此进入聊天或结果展示页

**参数注入方式**：
将表单参数作为首条用户消息注入，不修改 Agent 的 system_prompt：
```
用户提交表单后，自动生成首条消息：
「以下是任务参数：
- topic: 人工智能在医疗诊断中的应用
- field: 计算机科学
- word_count: 5000
- citation_style: APA
- key_arguments: 1. AI提高诊断准确率 2. 伦理挑战

请根据以上参数执行任务。」
```

**发布请求体示例**:
```json
{
  "release_notes": "新增论文摘要生成功能，优化翻译质量",
  "execution_mode": "task",
  "input_schema": {
    "properties": {
      "topic": {"type": "string", "title": "论文主题"},
      "field": {"type": "string", "title": "学科领域", "enum": ["计算机科学", "医学", "法学"]}
    },
    "required": ["topic", "field"]
  }
}
```

**发布响应体示例**:
```json
{
  "version": "a3f2c8d",
  "agent_id": "xxx",
  "published_at": "2026-08-11T10:00:00Z"
}
```

**与 agentscope 的集成**:
- 通过 agent_id 关联，不修改 agentscope 的任何模型
- 发布状态存储在独立的数据库表中
- 终端用户聊天时，通过 agent_id 调用 agentscope 的会话 API
- 任务模式的参数注入在 `_publish` 模块中完成，与 agentscope 完全解耦

### 1.3 API 访问控制

**终端用户 API 可访问端点**:
- `GET /publish/list` - 已发布 Agent 列表
- `GET /publish/{agent_id}` - 获取单个已发布 Agent 详情（含 input_schema）
- `POST /publish/{agent_id}/execute` - 任务模式提交执行
- `POST /sessions/` - 创建会话
- `PATCH /sessions/{id}` - 更新会话（仅限模型配置）
- `POST /chat/` - 聊天
- 其他只读操作

**实现方式**：通过 FastAPI 依赖注入，在需要权限控制的端点上添加 `require_role("developer")` 或 `require_role("end_user")` 依赖

---

## 二、前端改造

### 2.1 项目结构变更

```
frontend/src/
├── pages/
│   ├── login/                 # 新增：登录页
│   │   └── index.tsx
│   ├── admin/                 # 重命名：现有完整界面 → /admin/*
│   │   ├── channel/           # 原 pages/channel/
│   │   ├── chat/              # 原 pages/chat/
│   │   ├── credential/        # 原 pages/credential/
│   │   ├── knowledge/         # 原 pages/knowledge/
│   │   ├── mcp/               # 原 pages/mcp/
│   │   ├── schedule/          # 原 pages/schedule/
│   │   ├── setup/             # 原 pages/setup/
│   │   └── skill/             # 原 pages/skill/
│   └── space/                 # 新增：开发者空间（终端用户界面）
│       ├── index.tsx          # 空间首页（已发布 Agent 列表）
│       └── chat.tsx           # 用户聊天页
├── components/
│   ├── auth/                  # 新增：认证相关组件
│   │   ├── AuthProvider.tsx
│   │   ├── ProtectedRoute.tsx
│   │   └── RoleGuard.tsx
│   └── ...                    # 现有组件保持不变
├── api/
│   ├── auth.ts                # 新增：认证 API
│   ├── publish.ts             # 新增：发布管理 API
│   ├── client.ts              # 修改：支持 JWT header
│   ── ...                    # 现有 API 模块保持不变
├── hooks/
│   ├── useAuth.ts             # 新增：认证 Hook
│   └── ...                    # 现有 Hooks 保持不变
└── ...
```

### 2.2 路由设计

```typescript
// 登录页（未认证时）
'/login' → LoginPage

// 开发者界面（需要 developer 角色）
'/admin' → AdminLayout
  '/admin/chat/:agentId?/:sessionId?' → 现有 ChatPage
  '/admin/schedule' → SchedulePage
  '/admin/channel' → ChannelPage
  '/admin/credential' → CredentialPage
  '/admin/mcp' → MCPHubPage
  '/admin/skill' → SkillHubPage
  '/admin/knowledge' → KnowledgePage
  '/admin/setup' → SetupPage

// 开发者空间（需要 end_user 角色）
'/space' → SpaceLayout
  '/space' → AgentListPage (已发布 Agent 卡片列表)
  '/space/launchpad/:agentId' → LaunchpadPage (启动确认页：对话模式直接进入聊天，任务模式展示表单)
  '/space/chat/:agentId/:sessionId?' → UserChatPage (简化版聊天)
  '/space/task/:agentId/:sessionId?' → TaskResultPage (任务执行结果展示)
```

### 2.3 认证流程

1. 用户访问任意页面 → 检查 localStorage 是否有有效 token
2. 无 token → 重定向到 `/login`
3. 登录成功 → 存储 token 和用户信息到 localStorage + context
4. 根据 `user.role` 重定向到对应界面：
    - `developer` → `/admin/chat`
    - `end_user` → `/space`
5. API 请求自动携带 `Authorization: Bearer <token>` header

### 2.4 开发者空间（终端用户）

类似应用市场的概念，终端用户可以浏览、搜索和使用已发布的智能体。

**空间首页** (`/space`):
- 卡片式展示已发布的 Agent，类似应用商店风格
- 每个卡片显示：名称、描述、当前版本号、执行模式标签（对话/任务）、发布者信息
- 支持按执行模式筛选（对话/任务）、搜索
- 点击卡片进入 Launchpad 页面

**Launchpad 启动确认页** (`/space/launchpad/:agentId`):
- 展示 Agent 名称、描述、当前版本号、已配置的 MCP 列表、默认 Model
- **对话模式**：展示确认信息，用户点击"开始对话"→ 创建 session → 进入聊天
- **任务模式**：根据 `input_schema` 渲染动态表单，用户填写后点击"提交执行"→ 调用 `/publish/{agent_id}/execute` → 进入结果页或聊天页

**表单渲染组件** (`DynamicForm`):
- 根据 JSON Schema 自动生成表单 UI
- 支持字段类型：
  - `string` → 文本输入框（`format: textarea` → 多行文本框）
  - `integer` / `number` → 数字输入框（支持 min/max）
  - `boolean` → 开关/复选框
  - `enum` → 下拉选择框
  - `string` + `format: password` → 密码输入框
- 必填字段标记（根据 `required` 数组）
- 默认值填充（根据 `default` 字段）
- 表单验证（类型检查、必填校验、枚举值校验）

**用户聊天页** (`/space/chat/:agentId`):
- 复用现有 `ChatViewport` 组件（位于 `frontend/src/pages/chat/ChatViewport.tsx`）
- 隐藏：Agent 编辑/删除、模型选择器、权限模式切换、工作空间面板
- 仅保留：会话列表、聊天输入、消息展示

**任务结果页** (`/space/task/:agentId/:sessionId`):
- 展示任务执行结果（Agent 回复）
- 可选择"继续对话"（转入聊天模式）或"重新提交"（返回表单）

### 2.6 开发者版本管理界面

**发布对话框**（开发者在 admin 界面触发）:
- 发布内容文本域（`release_notes`，必填，支持 Markdown）
- 执行模式选择（对话/任务）
- 任务模式时展示 `input_schema` 配置区
- 提交前预览：展示即将发布的 Agent 配置摘要
- 发布成功后展示自动生成的版本号（如 `a3f2c8d`）

**版本历史页**（`/admin/agent/:agentId/versions`）:
- 时间线形式展示所有版本，最新版本标记"当前"
- 每个版本显示：版本号、发布时间、发布内容摘要、执行模式
- 点击版本可展开查看详情（完整 release_notes、input_schema）
- 支持回滚到指定版本（需确认对话框）

**已发布 Agent 卡片**（开发者视图）:
- 显示当前版本号 + 版本总数
- 快捷操作：发布新版本、查看版本历史、取消发布

### 2.5 API Client 改造

**修改 `frontend/src/api/client.ts`**:
```typescript
// 请求拦截器：自动添加 Authorization header
const headers: Record<string, string> = {
  'Content-Type': 'application/json',
};
const token = localStorage.getItem('access_token');
if (token) {
  headers['Authorization'] = `Bearer ${token}`;
}
```

**新增 `frontend/src/api/auth.ts`**:
```typescript
export const authApi = {
  login: (username: string, password: string) =>
    client.post<TokenResponse>('/auth/token', { username, password, grant_type: 'password' }),
  me: () => client.get<UserInfo>('/auth/me'),
  refresh: () => client.post<TokenResponse>('/auth/refresh'),
};
```

**新增 `frontend/src/api/publish.ts`**:
```typescript
export const publishApi = {
  publish: (agentId: string, body: PublishRequest) =>
    client.post(`/publish/agent/${agentId}`, body),
  unpublish: (agentId: string) => client.post(`/unpublish/agent/${agentId}`),
  listPublished: () => client.get<PublishedAgent[]>('/publish/list'),
  listMyPublished: () => client.get<PublishedAgent[]>('/publish/my'),
  getPublished: (agentId: string) => client.get<PublishedAgentDetail>(`/publish/${agentId}`),
  getVersions: (agentId: string) => client.get<AgentVersion[]>(`/publish/${agentId}/versions`),
  getVersion: (agentId: string, version: string) =>
    client.get<AgentVersionDetail>(`/publish/${agentId}/versions/${version}`),
  rollback: (agentId: string, version: string) =>
    client.post(`/publish/${agentId}/rollback/${version}`),
  execute: (agentId: string, params: Record<string, unknown>) =>
    client.post<ExecuteResponse>(`/publish/${agentId}/execute`, { input: params }),
};
```

**新增类型定义** (`frontend/src/api/types.ts`):
```typescript
export interface PublishRequest {
  release_notes: string;       // 发布内容/更新说明，必填
  execution_mode: 'chat' | 'task';
  input_schema?: JSONSchema;   // 任务模式必填
}

export interface PublishResponse {
  version: string;             // 后端自动生成的版本号（缩短 SHA256 哈希，如 "a3f2c8d"）
  agent_id: string;
  published_at: string;
}

export interface PublishedAgentDetail {
  id: string;
  agent_id: string;
  agent_name: string;
  agent_description: string;
  current_version: string;     // 当前发布版本号
  execution_mode: 'chat' | 'task';
  input_schema: JSONSchema | null;
  published_at: string;
}

export interface AgentVersion {
  id: string;
  version: string;             // 版本号
  release_notes: string;       // 发布内容
  execution_mode: 'chat' | 'task';
  published_by: string;
  published_at: string;
  is_current: boolean;         // 是否为当前活跃版本
}

export interface AgentVersionDetail extends AgentVersion {
  input_schema: JSONSchema | null;
  agent_snapshot: Record<string, unknown>;  // Agent 配置快照
}

export interface ExecuteResponse {
  session_id: string;
  agent_id: string;
}
```
```

---

## 三、实施步骤

### Phase 1: 后端认证基础 (预计 2-3 天)
1. 在 `backend/` 下创建 `_auth` 模块，实现 User 模型和 JWT 工具
2. 实现 `/auth/token` 和 `/auth/me` 端点
3. 在 `backend/main.py` 中注册认证路由和中间件
4. 创建默认管理员账户（首次启动时）

### Phase 2: Agent 发布机制 (预计 4 天)
1. 在 `backend/` 下创建 `_publish` 模块，设计两张表：`agent_publications`（发布记录）+ `agent_versions`（版本历史）
2. 实现发布 API：自动生成版本号（缩短 SHA256 哈希）、release_notes 必填，保存 Agent 配置快照
3. 实现版本历史 API（`GET /publish/{agent_id}/versions`）和版本详情 API
4. 实现版本回滚 API（`POST /publish/{agent_id}/rollback/{version}`）
5. 实现取消发布 API
6. 实现已发布 Agent 列表查询 API 和单个详情 API
7. 实现任务模式执行端点（`POST /publish/{agent_id}/execute`）：创建 session + 参数注入
8. 添加发布状态与 agentscope Agent 的关联逻辑

### Phase 3: API 访问控制 (预计 1 天)
1. 实现基于角色的 API 访问控制中间件
2. 为 agentscope 原有端点添加角色校验
3. 确保终端用户只能访问允许的端点

### Phase 4: 前端登录与路由 (预计 2 天)
1. 创建 `frontend/src/pages/login/` 登录页面
2. 实现 `AuthProvider`、`ProtectedRoute`、`RoleGuard` 组件
3. 重构路由结构（/admin/* 和 /user/*）
4. 修改 API Client 支持 JWT header
5. 新增 `auth.ts` 和 `publish.ts` API 模块

### Phase 5: 开发者空间 (预计 3 天)
1. 创建 `frontend/src/pages/space/` 开发者空间首页（已发布 Agent 列表，含搜索和筛选）
2. 创建 Launchpad 启动确认页（对话模式确认 / 任务模式表单渲染）
3. 实现 `DynamicForm` 动态表单组件（基于 JSON Schema 自动渲染）
4. 创建简化版聊天页（复用 `ChatViewport`）
5. 创建任务结果页（展示执行结果，支持继续对话/重新提交）
6. 隐藏开发者专属功能，调整侧边栏和导航

### Phase 6: 集成测试与优化 (预计 2 天)
1. 端到端测试登录流程
2. 验证角色权限控制
3. 测试 Agent 发布/使用流程（对话模式 + 任务模式）
4. 测试表单渲染和参数注入的完整性
5. 测试 token 刷新和过期处理

### Phase 7: 沙盒环境 (预计 4-5 天)
1. 创建 `backend/_sandbox/` 模块，编写沙盒 Dockerfile 和抽象基类
2. 实现 `DockerSandboxManager`（Docker SDK 集成，容器生命周期管理）
3. 实现 `K8sSandboxManager`（kubernetes Python client，Pod 生命周期管理）
4. 实现 `SandboxFactory`：根据 `SANDBOX_BACKEND` 环境变量创建对应管理器
5. 实现 Session → 隔离环境的映射关系（创建/复用/销毁）
6. 配置资源限制（CPU、内存、磁盘、网络隔离）
7. 在 `backend/main.py` 中根据环境变量切换 WorkspaceManager
8. 测试 Docker 后端：Agent 工具执行、MCP 进程、文件操作均在容器内完成
9. 测试 K8s 后端：Pod 创建/调度/销毁、PVC 挂载
10. 测试：隔离环境超时自动清理、异常退出处理

---

## 四、关键文件清单

### 后端新增/修改
| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/_auth/` | 新增 | 认证模块（User 模型、JWT、OAuth2） |
| `backend/_publish/` | 新增 | 发布管理模块（独立数据库表，含 input_schema 和 execution_mode） |
| `backend/_publish/router.py` | 新增 | 发布 API + 任务执行端点 |
| `backend/_sandbox/` | 新增 | 沙盒模块（Docker/K8s 双后端，隔离 Workspace） |
| `backend/_sandbox/base.py` | 新增 | 沙盒抽象基类（统一接口定义） |
| `backend/_sandbox/docker_manager.py` | 新增 | Docker 沙盒实现 |
| `backend/_sandbox/k8s_manager.py` | 新增 | Kubernetes 沙盒实现 |
| `backend/_sandbox/factory.py` | 新增 | 沙盒工厂类（根据配置创建对应管理器） |
| `backend/_sandbox/workspace.py` | 新增 | 沙盒版 WorkspaceManager |
| `backend/main.py` | 修改 | 注册认证路由、发布路由、添加中间件 |
| `backend/pyproject.toml` | 修改 | 添加 PostgreSQL 驱动依赖 |

### 前端新增/修改
| 文件 | 操作 | 说明 |
|------|------|------|
| `frontend/src/pages/login/` | 新增 | 登录页 |
| `frontend/src/pages/space/` | 新增 | 开发者空间（终端用户界面：列表页、Launchpad、聊天页、任务结果页） |
| `frontend/src/pages/admin/publish/` | 新增 | 开发者版本管理（发布对话框、版本历史页） |
| `frontend/src/components/DynamicForm/` | 新增 | 动态表单组件（基于 JSON Schema 渲染） |
| `frontend/src/pages/admin/` | 重命名 | 现有页面迁移到 admin 目录 |
| `frontend/src/components/auth/` | 新增 | 认证组件（AuthProvider, ProtectedRoute, RoleGuard） |
| `frontend/src/api/auth.ts` | 新增 | 认证 API |
| `frontend/src/api/publish.ts` | 新增 | 发布管理 API |
| `frontend/src/api/client.ts` | 修改 | 支持 JWT header |
| `frontend/src/hooks/useAuth.ts` | 新增 | 认证 Hook |
| `frontend/src/App.tsx` | 修改 | 重构路由结构 |

---

## 五、注意事项

1. **agentscope 源码不可修改**：`agentscope` 是通过 PyPI 安装的依赖，所有扩展功能必须通过独立模块实现，通过 agent_id 关联
2. **发布机制解耦**：使用独立的 `agent_publications` 数据库表存储发布状态，与 agentscope 的 AgentData 完全解耦
3. **向后兼容**：保留现有 Setup 页面的 username 方式作为开发模式（无认证时的降级方案）
4. **Token 刷新**：实现静默刷新，避免用户频繁重新登录
5. **密码安全**：使用 bcrypt 存储密码哈希（已在 `pyproject.toml` 中引入 `passlib[bcrypt]`）
6. **CORS 配置**：确保认证 API 支持跨域请求（已在 `backend/main.py` 中配置）
7. **错误处理**：401 时自动跳转登录页，清除过期 token
8. **前端 API 客户端**：当前前端使用 `@agentscope-ai/agentscope` 包提供的 API，需确认是否支持自定义 Authorization header；如不支持，需自行实现 HTTP 客户端
9. **数据库选型**：需要引入 PostgreSQL 作为用户和发布记录的存储（agentscope 当前使用 Redis + Qdrant）
10. **任务模式参数注入**：表单参数作为首条用户消息注入 Agent，不修改 system_prompt，与 agentscope 完全解耦
11. **表单渲染**：前端 `DynamicForm` 组件根据 JSON Schema 自动渲染，支持 text/textarea/number/select/boolean/password 等类型
12. **开发者发布体验**：开发者在发布 Agent 时只需填写发布内容（release_notes），版本号由后端自动生成（缩短的 SHA256 哈希，如 `a3f2c8d`），任务模式需配置 input_schema
13. **版本管理**：每次发布生成新版本记录，支持查看版本历史和回滚到指定版本；Agent 配置快照保存在 `agent_snapshot` 字段中
14. **沙盒安全**：终端用户执行的 Agent 必须在沙盒中运行，防止恶意代码执行；开发者调试时可选本地执行
15. **双后端支持**：沙盒支持 Docker 和 Kubernetes 两种后端，通过 `SANDBOX_BACKEND` 环境变量指定（`local` / `docker` / `k8s`）
16. **资源隔离**：每个 Session 独立隔离环境，限制 CPU/内存/磁盘，防止资源耗尽攻击
17. **环境清理**：Session 结束或超时后自动销毁隔离环境，避免僵尸资源占用
18. **K8s 依赖**：K8s 后端需要集群访问权限（kubeconfig），生产环境建议配置 RBAC 限制 Pod 操作权限
19. **开发者空间**：终端用户通过 `/space` 路由访问已发布的智能体，类似应用市场，支持浏览、搜索和使用
19. **开发者空间**：终端用户通过 `/space` 路由访问已发布的智能体，类似应用市场，支持浏览、搜索和使用
