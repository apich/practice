# Agent Platform

> [English](README.en.md) | 中文

基于 AgentScope 2.0 的 AI Agent 构建与分发平台。开发者可构建并发布智能体，终端用户可在应用市场中浏览并使用已发布的智能体。

**核心流程：** 开发 → 发布 → 浏览 → 使用

- **开发者**：在 Admin 空间中构建、配置 AI 智能体，并发布到应用市场
- **终端用户**：在 Space 空间中浏览已发布的智能体，通过对话或表单直接使用

平台内置身份认证（JWT / OAuth2.0 密码模式）、角色权限控制、智能体版本管理与沙盒隔离执行。

## 项目结构

```
agent-platform/
├── backend/                # Python 后端 (FastAPI + AgentScope)
│   ├── main.py             # 应用入口
│   ├── _config.py          # 集中式配置 (pydantic-settings)
│   ├── _auth/              # 认证与授权
│   │   ├── router.py       # /auth/* 端点 (登录、注册、刷新)
│   │   ├── service.py      # AuthService — OAuth2.0 密码模式委托
│   │   ├── security.py     # JWT 工具, SecurityService (TTLCache)
│   │   ├── middleware.py   # AuthMiddleware — JWT 解码 + AuthContext
│   │   ├── access_control.py  # 基于角色的 API 访问控制
│   │   ├── context.py      # AuthContext (ContextVar)
│   │   ├── exceptions.py   # AuthenticationError / AuthorizationError
│   │   └── models.py       # User ORM 模型, Role 常量
│   ├── _publish/           # 智能体发布与版本管理
│   ├── _sandbox/           # Docker / K8s 沙盒管理器
│   ├── _db/                # SQLAlchemy 异步引擎与会话
│   ├── .env.example        # 配置模板
│   └── pyproject.toml      # Python 依赖
├── frontend/               # React 前端 (Vite + TailwindCSS)
│   ├── src/
│   │   ├── pages/          # Admin (开发者) & Space (终端用户) 页面
│   │   ├── components/     # UI 组件、鉴权守卫、对话框
│   │   ├── hooks/          # useAuth 等
│   │   └── api/            # API 客户端 (含 JWT 支持)
│   └── package.json
└── Plan.md                 # 开发计划与架构设计
```

## 环境要求

| 依赖 | 版本 | 用途 |
|---|---|---|
| Python | >= 3.11 | 后端运行时 |
| Node.js | >= 18 | 前端构建 |
| pnpm | >= 8 | 前端包管理器 |
| Redis | >= 6 | 消息总线与存储后端 |

> 平台数据库默认使用 SQLite（零配置启动）。生产环境可切换为 PostgreSQL。

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
uv run python main.py
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
python main.py
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

### 数据库

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DATABASE_URL` | *(空 → SQLite)* | 生产环境 PostgreSQL 连接串，如 `postgresql+asyncpg://user:pass@localhost:5432/agent_platform` |

### 身份认证

| 变量 | 默认值 | 说明 |
|---|---|---|
| `JWT_SECRET_KEY` | `agent-platform-dev-secret-...` | JWT 签名密钥（**生产环境务必修改**） |
| `JWT_ACCESS_EXPIRE_MINUTES` | `30` | 访问令牌有效期（分钟） |
| `JWT_REFRESH_EXPIRE_DAYS` | `7` | 刷新令牌有效期（天） |
| `ENABLE_PASSWORD_LOGIN` | `true` | 是否启用本地密码登录 |
| `ENABLE_REGISTER` | `true` | 是否启用用户注册（仅开发者可操作） |
| `SEED_DEFAULT_ADMIN` | `true` | 首次启动是否自动创建默认管理员 |

### OAuth2.0 密码模式委托

当配置了 `OAUTH_AUTH_SERVER_URL` 时，`POST /auth/token` 端点会委托外部鉴权服务进行身份验证（OAuth2.0 Password Grant，`grant_type=password`）。验证通过后，用户同步到本地数据库并签发本地 JWT。

```env
OAUTH_AUTH_SERVER_URL=https://auth.example.com
OAUTH_CLIENT_ID=agent-platform
OAUTH_CLIENT_SECRET=your-client-secret
OAUTH_TOKEN_PATH=/oauth2/token
OAUTH_USERINFO_URL=https://auth.example.com/userinfo
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

### 沙盒隔离

| 变量 | 默认值 | 说明 |
|---|---|---|
| `SANDBOX_BACKEND` | `local` | `local` / `docker` / `k8s` |

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
┌─────────────────────────────────────────────────┐
│                   前端                            │
│  ┌──────────────┐    ┌──────────────────────┐   │
│  │  /admin/*    │    │  /space/*            │   │
│  │  开发者空间  │    │  终端用户应用市场     │   │
│  └──────┬───────┘    └──────────┬───────────┘   │
│         └──────── API 客户端 ───┘               │
│            JWT Bearer Token                      │
└─────────────────┬───────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────┐
│              后端 (FastAPI)                       │
│                                                   │
│  AuthMiddleware → AccessControl → AgentScope      │
│                                                   │
│  ┌─────────┐  ┌──────────┐  ┌────────────────┐  │
│  │ _auth/  │  │ _publish/ │  │  AgentScope    │  │
│  │JWT+OAuth│  │ 版本管理  │  │  核心 (ASGI)   │  │
│  └─────────┘  └──────────┘  └────────────────┘  │
│                                                   │
│  ┌─────────┐  ┌──────────┐                       │
│  │ _db/    │  │ _sandbox/ │                      │
│  │SQLAlchemy│ │Docker/K8s│                      │
│  └─────────┘  └──────────┘                       │
└───────────────────────────────────────────────────┘
```

## 开发

```bash
# 后端 — 热重载模式
cd backend && uv run python main.py
# (或激活 venv 后: python main.py)

# 前端 — 热重载模式
cd frontend && pnpm dev

# 运行后端测试
cd backend && uv run pytest
# (或激活 venv 后: pytest)
```
