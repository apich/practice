# Agent Platform - 项目概览

## 项目定位

基于 **AgentScope 2.0.5+** 的智能体开发平台，提供完整的 Agent 生命周期管理（创建、配置、调试、调度、渠道集成）。

当前为**单用户开发者模式**，通过 `localStorage` 存储 username 作为用户标识。计划扩展为双角色模型（开发者/终端用户）+ OAuth2/JWT 认证（详见 Plan.md）。

## 技术栈

### 后端
- **框架**: FastAPI (基于 `agentscope[service]>=2.0.6` 提供的 `create_app()`)
- **语言**: Python 3.11+ (AgentScope 2.0 强制要求)
- **存储**: 
  - Redis (会话存储、消息总线) - `localhost:6379`
  - Qdrant (向量存储，默认 `:memory:` 模式)
- **依赖管理**: uv + pyproject.toml
- **核心依赖**: 
  - `agentscope[service]>=2.0.6` (不可修改源码)
  - `passlib[bcrypt]` (密码哈希)
  - `uvicorn` (ASGI 服务器)
  - `python-socketio` (WebSocket 支持)

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
- **HTTP 客户端**: 自定义 fetch 封装 (`src/api/client.ts`)
- **依赖管理**: pnpm
- **通知**: sonner (toast 通知)

### 渠道集成
- Discord (DiscordChannel)
- 飞书 (FeishuChannel)

## 项目结构

```
agent-platform/
├── backend/
│   ├── main.py                 # FastAPI 入口 (调用 agentscope.create_app)
│   ├── pyproject.toml          # Python 依赖配置
│   └── workspaces/             # Agent 工作空间目录
├── frontend/
│   ├── src/
│   │   ├── api/                # API 客户端层
│   │   ├── components/         # 可复用 UI 组件
│   │   ├── context/            # React Context (如 UploadContext)
│   │   ├── hooks/              # 自定义 Hooks
│   │   ├── i18n/               # 国际化配置
│   │   ├── lib/                # 工具库
│   │   ├── pages/              # 页面组件
│   │   │   ├── channel/        # 渠道管理
│   │   │   ├── chat/           # 聊天页 (ChatViewport 核心组件)
│   │   │   ├── credential/     # 凭证管理
│   │   │   ├── knowledge/      # 知识库管理
│   │   │   ├── mcp/            # MCP Hub 管理
│   │   │   ├── schedule/       # 调度任务管理
│   │   │   ├── setup/          # 初始化设置
│   │   │   └── skill/          # Skill Hub 管理
│   │   └── utils/              # 工具函数
│   ├── package.json
│   ├── vite.config.ts          # Vite 配置 (API 代理到 :9000)
│   ├── eslint.config.js        # ESLint 配置 (TypeScript + React)
│   └── tsconfig.json           # TypeScript 配置
├── Plan.md                     # 实施方案文档
└── README.md
```

## 架构约束

### 🚫 禁止修改 AgentScope 源码
- `agentscope` 是通过 PyPI 安装的依赖包
- 所有扩展功能必须通过**独立模块**实现
- 通过 `agent_id` 关联，不修改 AgentScope 的任何数据模型

### 扩展方式
- 后端: 在 `create_app()` 返回的 FastAPI app 上挂载额外路由和中间件
- 前端: 在 `src/api/` 和 `src/pages/` 中添加新模块
- 使用独立数据库表存储扩展数据（如发布状态、用户信息）

## 核心特性

1. **Agent 管理**: 创建、配置、调试 Agent
2. **MCP 集成**: 通过 MCP Hub 浏览和安装 MCP 服务器
3. **Skill 管理**: 通过 Skill Hub 浏览和安装技能
4. **知识库**: RAG 知识库管理 (Qdrant 向量存储)
5. **调度任务**: 定时执行 Agent 任务
6. **渠道集成**: Discord、飞书机器人
7. **凭证管理**: 统一管理 API 密钥
8. **长期记忆**: 基于 Markdown 文件的 Agent 记忆 (AgenticMemoryMiddleware)

## API 代理配置

前端开发服务器 (Vite) 通过代理访问后端:
```typescript
// vite.config.ts
server: {
  proxy: {
    '/api': 'http://localhost:9000',
  },
}
```

后端运行在 `localhost:9000` (可通过 `uvicorn` 配置修改)

## 身份验证

### 当前实现 (简化模式)
- 使用 `localStorage.getItem('username')` 作为用户标识
- 通过 `X-User-ID` header 传递用户 ID
- 无密码验证、无 token 机制

### 计划扩展 (Plan.md 中定义)
- OAuth2 + JWT 双角色模型
- 开发者 (developer) vs 终端用户 (end_user)
- Agent 发布机制（对话模式/任务模式）
- 沙盒执行环境 (Docker/K8s)
