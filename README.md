# Agent Platform

> [English](README.en.md) | 中文

基于 AgentScope 2.0 的 AI Agent 构建与分发平台。开发者可构建并发布智能体，终端用户可在应用市场中浏览并使用已发布的智能体。

**核心流程：** 开发 → 发布 → 浏览 → 使用

- **开发者**：在 Admin 空间中构建、配置 AI 智能体，并发布到应用市场
- **终端用户**：在 Space 空间中浏览已发布的智能体，通过对话或表单直接使用

平台内置身份认证（JWT / OAuth2.0 密码模式）、角色权限控制、智能体版本管理、知识库管理、MCP / Skill Hub、Channel 适配器、定时任务及沙盒隔离执行。

## 项目结构

```
agent-platform/
├── backend/                    # Python 后端 (FastAPI + AgentScope)
│   ├── app/
│   │   ├── main.py             # 应用入口 — 集成 AgentScope create_app + 平台扩展
│   │   ├── storage_channel.py  # AsyncSQLAlchemyStorage Channel 支持补丁
│   │   ├── core/               # 核心基础设施
│   │   │   ├── config.py       # 集中式配置 (pydantic-settings)
│   │   │   ├── database.py     # SQLAlchemy 异步引擎与会话管理
│   │   │   └── exceptions.py   # 全局异常处理器
│   │   ├── auth/               # 认证与授权
│   │   │   ├── router.py       # /auth/* 端点 (登录、注册、刷新)
│   │   │   ├── service.py      # AuthService — OAuth2.0 密码模式委托
│   │   │   ├── security.py     # JWT 工具, SecurityService (TTLCache)
│   │   │   ├── middleware.py   # AuthMiddleware + AccessControlMiddleware
│   │   │   ├── deps.py         # AuthContext 依赖注入
│   │   │   └── models.py       # User ORM 模型, Role 常量
│   │   ├── publish/            # 智能体发布与版本管理
│   │   ├── sandbox/            # Docker / K8s 沙盒管理器
│   │   │   ├── base.py         # 沙盒基类
│   │   │   ├── docker_manager.py
│   │   │   ├── k8s_manager.py
│   │   │   ├── factory.py      # 沙盒工厂
│   │   │   └── workspace.py    # SandboxWorkspaceManager
│   │   └── ...
│   ├── .env.example            # 配置模板
│   └── pyproject.toml          # Python 依赖
├── frontend/                   # React 前端 (Vite + TailwindCSS)
│   ├── src/
│   │   ├── pages/              # 页面模块
│   │   │   ├── chat/           # Admin 聊天与智能体调试
│   │   │   ├── space/          # 终端用户市场、启动台、对话
│   │   │   ├── knowledge/      # 知识库管理
│   │   │   ├── mcp/            # MCP Hub 浏览与管理
│   │   │   ├── skill/          # Skill Hub 浏览与管理
│   │   │   ├── channel/        # Channel 适配器 (飞书/Discord)
│   │   │   ├── schedule/       # 定时任务
│   │   │   ├── credential/     # 凭证管理
│   │   │   ├── login/          # 登录页
│   │   │   ├── profile/        # 用户资料
│   │   │   └── setup/          # 初始设置
│   │   ├── components/         # UI 组件、鉴权守卫、对话框、导览
│   │   ├── hooks/              # useAuth, useChat, useAgents 等
│   │   └── api/                # API 客户端 (含 JWT 支持, 18 个模块)
│   └── package.json
└── Plan.md                     # 开发计划与架构设计
```

## 环境要求

| 依赖 | 版本 | 用途 |
|---|---|---|
| Python | >= 3.11 | 后端运行时 |
| Node.js | >= 18 | 前端构建 |
| pnpm | >= 8 | 前端包管理器 |
| Redis | >= 6 | 消息总线 (SSE 事件流、分布式锁) |

> 平台数据库默认使用 SQLite（零配置启动），AgentScope 存储与平台存储共用同一数据库。生产环境可切换为 PostgreSQL。

## 快速开始

### 1. 后端

#### 方式 A：使用 `uv`（推荐）

```bash
cd backend

# 安装 uv（如尚未安装）
pip install uv

# 创建虚拟环境并安装依赖
uv sync

# 复制配置模板
cp .env.example .env
# 按需编辑 .env（所有配置项均有默认值，开发环境可不修改）

# 启动服务
uv run python -m app.main
```

#### 方式 B：使用标准 `venv` + `pip`

```bash
cd backend

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
#   Windows (PowerShell):
.venv\Scripts\Activate.ps1
#   Windows (CMD):
.venv\Scripts\activate.bat
#   Linux / macOS:
source .venv/bin/activate

# 安装依赖
pip install -e ".[dev]"

# 复制配置模板
cp .env.example .env   # Windows 上使用: copy .env.example .env

# 启动服务
python -m app.main
```

后端启动在 `http://localhost:9000`，API 文档位于 `http://localhost:9000/docs`。

#### 默认账号

首次启动时自动创建默认开发者账号：

| 用户名 | 密码 | 角色 |
|---|---|---|
| `admin` | `admin` | developer |

### 2. 前端

```bash
cd frontend

# 安装依赖
pnpm install

# 启动开发服务器
pnpm dev
```

前端启动在 `http://localhost:5173`。

## 配置说明

所有配置集中在 `backend/.env` 文件中（完整模板见 `.env.example`）。关键配置项：

### 应用

| 变量 | 默认值 | 说明 |
|---|---|---|
| `APP_HOST` | `0.0.0.0` | 监听地址 |
| `APP_PORT` | `9000` | 监听端口 |
| `APP_DEBUG` | `true` | 调试模式（启用热重载） |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | 允许的 CORS 来源（逗号分隔） |

### 数据库

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DATABASE_URL` | *(空 → SQLite)* | 生产环境 PostgreSQL 连接串，如 `postgresql+asyncpg://user:pass@localhost:5432/agent_platform` |
| `DATABASE_ECHO` | `false` | 是否打印 SQL 语句 |
| `DATABASE_POOL_SIZE` | `10` | 连接池大小 |
| `DATABASE_MAX_OVERFLOW` | `20` | 连接池最大溢出 |
| `DATABASE_POOL_RECYCLE` | `3600` | 连接回收时间（秒） |

### Redis

| 变量 | 默认值 | 说明 |
|---|---|---|
| `REDIS_HOST` | `localhost` | Redis 主机 |
| `REDIS_PORT` | `6379` | Redis 端口 |
| `REDIS_DB` | `10` | Redis 数据库编号 |
| `REDIS_PASSWORD` | *(空)* | Redis 密码 |

### 身份认证

| 变量 | 默认值 | 说明 |
|---|---|---|
| `JWT_SECRET_KEY` | `agent-platform-dev-secret-...` | JWT 签名密钥（**生产环境务必修改**） |
| `JWT_ACCESS_EXPIRE_MINUTES` | `30` | 访问令牌有效期（分钟） |
| `JWT_REFRESH_EXPIRE_DAYS` | `7` | 刷新令牌有效期（天） |
| `ENABLE_PASSWORD_LOGIN` | `true` | 是否启用本地密码登录 |
| `ENABLE_REGISTER` | `true` | 是否启用用户注册（仅开发者可操作） |
| `SEED_DEFAULT_ADMIN` | `true` | 首次启动是否自动创建默认管理员 |
| `SEED_ADMIN_USERNAME` | `admin` | 默认管理员用户名 |
| `SEED_ADMIN_PASSWORD` | `admin` | 默认管理员密码（**生产环境务必修改**） |

### OAuth2.0 密码模式委托

当配置了 `OAUTH_AUTH_SERVER_URL` 时，`POST /auth/token` 端点会委托外部鉴权服务进行身份验证（OAuth2.0 Password Grant，`grant_type=password`）。验证通过后，用户同步到本地数据库并签发本地 JWT。

```env
OAUTH_AUTH_SERVER_URL=https://auth.example.com
OAUTH_CLIENT_ID=agent-platform
OAUTH_CLIENT_SECRET=your-client-secret
OAUTH_SCOPES=openid profile email
OAUTH_TOKEN_PATH=/oauth2/token
OAUTH_USERINFO_URL=https://auth.example.com/userinfo
OAUTH_TOKEN_CACHE_TTL=300
```

当 `OAUTH_AUTH_SERVER_URL` 为空（默认）时，平台仅使用本地 bcrypt 密码校验。

**登录流程：**

```
POST /auth/token (username, password)
  ├─ 已配置 OAUTH_AUTH_SERVER_URL?  →  委托外部鉴权服务
  │     ├─ grant_type=password  →  access_token
  │     ├─ 获取 userinfo
  │     ├─ 同步/创建本地用户
  │     └─ 签发本地 JWT  →  返回响应
  └─ 否则 / 回退  →  本地数据库校验 (bcrypt)
        └─ 签发本地 JWT  →  返回响应
```

### LLM 模型

| 变量 | 默认值 | 说明 |
|---|---|---|
| `MODEL_API_KEY` | *(空)* | 模型 API 密钥 |
| `MODEL_API_BASE` | `https://api.openai.com/v1` | 模型 API 地址 |
| `MODEL_NAME` | `gpt-4o` | 默认模型名称 |

### 向量存储 (Qdrant)

| 变量 | 默认值 | 说明 |
|---|---|---|
| `QDRANT_LOCATION` | `:memory:` | 内存模式（重启丢失）；生产环境设为持久化路径或远程地址 |

### 沙盒隔离

| 变量 | 默认值 | 说明 |
|---|---|---|
| `SANDBOX_BACKEND` | `local` | `disabled` / `local` / `docker` / `k8s` |

使用 Docker 或 K8s 沙盒时，需安装可选依赖：

```bash
# uv
uv sync --extra sandbox-docker
uv sync --extra sandbox-k8s

# pip
pip install -e ".[sandbox-docker]"
pip install -e ".[sandbox-k8s]"
```

## 架构

```
┌──────────────────────────────────────────────────────────────┐
│                        前端 (React + Vite)                     │
│                                                               │
│  ┌────────────────────────────┐  ┌─────────────────────────┐ │
│  │  /admin/*                  │  │  /space/*               │ │
│  │  开发者空间                │  │  终端用户应用市场       │ │
│  │  ├─ chat      智能体调试   │  │  ├─ 浏览已发布智能体    │ │
│  │  ├─ knowledge 知识库管理   │  │  ├─ 对话 / 表单使用     │ │
│  │  ├─ mcp       MCP Hub     │  │  └─ 任务结果查看        │ │
│  │  ├─ skill     Skill Hub   │  │                          │ │
│  │  ├─ channel   频道适配     │  │                          │ │
│  │  ├─ schedule  定时任务     │  │                          │ │
│  │  └─ credential 凭证管理    │  │                          │ │
│  └────────────┬───────────────┘  └────────────┬────────────┘ │
│               └──────── API 客户端 ───────────┘              │
│                  JWT Bearer Token + i18n                      │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                    后端 (FastAPI + AgentScope)                  │
│                                                                │
│  CORS → AuthMiddleware → AccessControl → AgentScope Routes     │
│                                                                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ auth/    │ │ publish/ │ │ sandbox/ │ │ core/            │ │
│  │JWT+OAuth │ │ 版本管理  │ │Docker/K8s│ │ config + database│ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘ │
│                                                                │
│  AgentScope 集成:                                              │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────────────┐│
│  │ Storage      │ │ Message Bus  │ │ Knowledge Base         ││
│  │ (SQLAlchemy) │ │ (Redis)      │ │ (Qdrant + CollectionPer││
│  │              │ │              │ │  KbManager)            ││
│  └──────────────┘ └──────────────┘ └────────────────────────┘│
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────────────┐│
│  │ MCP Hubs     │ │ Skill Hubs   │ │ Channels               ││
│  │ (GitHub)     │ │ (Claw)       │ │ (飞书 / Discord)       ││
│  └──────────────┘ └──────────────┘ └────────────────────────┘│
└────────────────────────────────────────────────────────────────┘
```

## 开发

```bash
# 后端 — 热重载模式
cd backend && uv run python -m app.main
# (或激活 venv 后: python -m app.main)

# 前端 — 热重载模式
cd frontend && pnpm dev

# 运行后端测试
cd backend && uv run pytest
# (或激活 venv 后: pytest)
```
