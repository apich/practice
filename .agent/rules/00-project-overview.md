# Agent Platform - 项目概览

## 项目定位

基于 **AgentScope 2.0.5+** 的智能体开发与分发平台，提供完整的 Agent 生命周期管理（创建、配置、调试、发布、版本管理、调度、渠道集成）。

当前为**双角色模型**：开发者（developer）在 Admin 空间构建、配置并发布智能体，终端用户（end_user）在 Space 空间浏览并使用已发布的智能体。内置 JWT 认证、OAuth2.0 委托、RBAC 角色访问控制。

## 技术栈

### 后端
- **框架**: FastAPI (基于 `agentscope[service]>=2.0.6` 提供的 `create_app()`)
- **语言**: Python 3.11+ (AgentScope 2.0 强制要求)
- **存储**:
  - 关系数据库: SQLAlchemy (异步)，默认 SQLite（零配置开发），生产环境可用 PostgreSQL
  - Redis (会话/消息总线) - `localhost:6379`，DB 编号默认 10
  - Qdrant (向量存储，默认 `:memory:` 模式)
- **依赖管理**: uv + pyproject.toml
- **核心依赖**:
  - `agentscope[service]>=2.0.6` (不可修改源码)
  - `PyJWT` (JWT Token)
  - `bcrypt` (密码哈希，直接使用 bcrypt 库避免 passlib 兼容问题)
  - `pydantic-settings` (集中式配置)
  - `cachetools` (Token/权限 TTL 缓存)
  - `httpx` (OAuth2.0 委托 HTTP 客户端)
  - `structlog` (结构化日志)

### 前端
- **框架**: React 19 + Vite 8
- **语言**: TypeScript 6.0
- **UI 库**:
  - shadcn/ui (基于 Radix UI)
  - TailwindCSS 4.3 (utility-first CSS)
  - Framer Motion (动画)
  - Lucide React (图标)
  - @agentscope-ai/agentscope (类型定义和消息模型)
- **状态管理**: React Context + Hooks (无全局状态管理库)
- **路由**: React Router DOM 7 (createBrowserRouter API)
- **国际化**: i18next + react-i18next (支持中英文)
- **HTTP 客户端**: 自定义 fetch 封装 (`src/api/client.ts`)，支持 JWT Bearer header 自动注入
- **依赖管理**: pnpm
- **通知**: sonner (toast 通知)

### 渠道集成
- Discord (DiscordChannel)
- 飞书 (FeishuChannel)

## 项目结构

```
agent-platform/
├── backend/
│   ├── app/                      # 后端主包（所有平台扩展位于此）
│   │   ├── main.py               # 应用入口 — 集成 AgentScope create_app + 平台扩展
│   │   ├── storage_channel.py    # AsyncSQLAlchemyStorage Channel 支持补丁
│   │   ├── core/                 # 核心基础设施
│   │   │   ├── config.py         # 集中式配置 (pydantic-settings)
│   │   │   ├── database.py       # SQLAlchemy 异步引擎与会话管理
│   │   │   └── exceptions.py     # 全局异常处理器
│   │   ├── auth/                 # 认证与授权
│   │   │   ├── router.py         # /auth/* 端点 (登录、注册、刷新、OAuth 回调)
│   │   │   ├── service.py        # AuthService — OAuth2.0 密码模式委托 + PKCE
│   │   │   ├── security.py       # JWT 工具, SecurityService (TTLCache)
│   │   │   ├── middleware.py     # AuthMiddleware + AccessControlMiddleware
│   │   │   ├── deps.py           # AuthContext + get_current_user / require_role
│   │   │   └── models.py         # User ORM 模型, Role 常量
│   │   ├── publish/              # 智能体发布与版本管理
│   │   │   ├── models.py         # AgentPublication / AgentVersion / AgentExecution
│   │   │   ├── service.py        # 发布业务逻辑 (版本号、快照、回滚、任务执行)
│   │   │   └── router.py         # /publish/* 与 /unpublish/* 路由
│   │   └── sandbox/              # Docker / K8s 沙盒管理器
│   │       ├── base.py           # 沙盒抽象基类
│   │       ├── docker_manager.py # Docker 沙盒实现
│   │       ├── k8s_manager.py    # Kubernetes 沙盒实现
│   │       ├── factory.py        # 沙盒工厂 (SANDBOX_BACKEND 切换)
│   │       ├── workspace.py      # SandboxWorkspaceManager
│   │       └── Dockerfile        # 沙盒镜像
│   ├── .env.example              # 配置模板
│   ├── pyproject.toml            # Python 依赖
│   └── workspaces/               # Agent 工作空间目录
├── frontend/
│   ├── src/
│   │   ├── api/                  # API 客户端层 (18 个模块, 含 JWT 支持)
│   │   │   ├── client.ts         # HTTP 客户端封装 (JWT + X-User-ID 回退)
│   │   │   ├── auth.ts           # 认证 API
│   │   │   ├── publish.ts        # 发布管理 API
│   │   │   └── ...               # agent/session/chat/mcp/skill/knowledge 等
│   │   ├── components/
│   │   │   ├── auth/             # AuthProvider, ProtectedRoute, RoleGuard
│   │   │   ├── form/             # SchemaForm 动态表单
│   │   │   ├── ui/               # shadcn/ui 基础组件
│   │   │   ├── chat/             # 聊天组件
│   │   │   ├── layout/           # AppLayout, AppSidebar
│   │   │   └── ...               # badge/dialog/drawer/error/hub/panel 等
│   │   ├── context/              # React Context (UploadContext)
│   │   ├── hooks/                # useAuth, useChat, useMessages, useAgents 等 (28 个)
│   │   ├── i18n/                 # 国际化 (中/英)
│   │   ├── lib/                  # 工具库
│   │   ├── pages/                # 页面组件
│   │   │   ├── chat/             # Admin 聊天与智能体调试
│   │   │   ├── space/            # 终端用户市场/启动台/聊天/任务结果
│   │   │   ├── login/            # 登录页
│   │   │   ├── profile/          # 用户资料
│   │   │   ├── knowledge/        # 知识库管理
│   │   │   ├── mcp/              # MCP Hub
│   │   │   ├── skill/            # Skill Hub
│   │   │   ├── channel/          # Channel 适配器
│   │   │   ├── schedule/         # 定时任务
│   │   │   ├── credential/       # 凭证管理
│   │   │   └── setup/            # 初始化设置
│   │   ├── types/                # 类型定义
│   │   ├── App.tsx               # 路由定义 (admin/space/login)
│   │   └── main.tsx              # React 渲染入口
│   └── package.json
└── Plan.md                       # 开发计划与架构设计 (已实现)
```

## 架构约束

### 🚫 禁止修改 AgentScope 源码
- `agentscope` 是通过 PyPI 安装的依赖包
- 所有扩展功能必须通过**独立模块**实现
- 通过 `agent_id` 关联，不修改 AgentScope 的任何数据模型

### 扩展方式
- 后端: 在 `create_app()` 返回的 FastAPI app 上挂载额外路由和中间件（位于 `app/` 下）
- 前端: 在 `src/api/` 和 `src/pages/` 中添加新模块
- 使用独立数据库表存储扩展数据（如用户、发布记录、版本历史）

## 核心特性

1. **双角色模型**: developer 构建/发布，end_user 浏览/使用
2. **JWT 认证**: OAuth2.0 密码模式 + Authorization Code (PKCE) 委托，本地 bcrypt 回退
3. **RBAC 访问控制**: `AccessControlMiddleware` 拦截 end_user 访问开发者端点
4. **Agent 发布机制**: 版本管理、快照回滚、对话/任务双执行模式
5. **Agent 管理**: 创建、配置、调试 Agent
6. **MCP 集成**: 通过 MCP Hub 浏览和安装 MCP 服务器
7. **Skill 管理**: 通过 Skill Hub 浏览和安装技能
8. **知识库**: RAG 知识库管理 (Qdrant 向量存储)
9. **调度任务**: 定时执行 Agent 任务
10. **渠道集成**: Discord、飞书机器人
11. **凭证管理**: 统一管理 API 密钥
12. **长期记忆**: 基于 Markdown 文件的 Agent 记忆 (AgenticMemoryMiddleware)
13. **沙盒执行**: Docker/K8s 隔离环境 (SANDBOX_BACKEND 切换)

## API 代理配置

前端开发服务器 (Vite) 通过代理访问后端:
```typescript
// vite.config.ts
server: {
  proxy: {
    '/auth': 'http://localhost:9000',
    '/publish': 'http://localhost:9000',
    '/agent': 'http://localhost:9000',
    // ... 全部后端前缀
  },
}
```

后端运行在 `localhost:9000` (可通过 `.env` 中 `APP_PORT` 修改)

## 身份验证

### 当前实现 (JWT + 双角色)
- 登录后签发 `access_token` (短时) + `refresh_token` (长时)，均存于 localStorage
- 所有 API 请求自动携带 `Authorization: Bearer <token>` header
- 开发者 (developer) → `/admin/*` 空间；终端用户 (end_user) → `/space` 空间
- 兼容开发模式：无 token 时回退到 `X-User-ID` header（Setup 页 `username` 方式）

### 扩展模块命名
平台扩展模块位于 `backend/app/` 下，不使用下划线前缀（与早期计划中的 `_auth/`、`_publish/` 命名不同）。
