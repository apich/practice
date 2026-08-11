# 后端开发规范

## 架构原则

### 🚫 禁止修改 AgentScope 源码
- `agentscope` 通过 PyPI 安装，视为**不可变依赖**
- 所有扩展功能必须通过**独立模块**实现
- 模块命名使用下划线前缀（如 `_auth/`, `_publish/`, `_sandbox/`）表示平台扩展

### 扩展方式
```python
# backend/main.py
from agentscope.app import create_app

# 1. 创建基础应用
app = create_app(
    storage=storage,
    message_bus=message_bus,
    workspace_manager=workspace_manager,
    # ...
)

# 2. 挂载扩展路由
from _auth.router import auth_router
from _publish.router import publish_router
app.include_router(auth_router)
app.include_router(publish_router)

# 3. 添加中间件
from _auth.middleware import AuthMiddleware
app.add_middleware(AuthMiddleware)
```

## 代码风格

### 导入顺序
```python
# 1. 标准库
import os
from typing import Optional

# 2. 第三方库
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# 3. agentscope 库
from agentscope.app import create_app
from agentscope.model import DashScopeChatModel

# 4. 本地模块
from _auth.models import User
from _publish.service import PublishService
```

### 文档字符串
```python
def create_session(user_id: str, agent_id: str) -> str:
    """Create a new session for the given user and agent.
    
    Args:
        user_id: The user identifier
        agent_id: The agent identifier
        
    Returns:
        The created session ID
        
    Raises:
        HTTPException: If agent not found or user unauthorized
    """
    pass
```

### 类型注解
- 所有函数参数和返回值必须有类型注解
- 使用 `typing` 模块的类型（`Optional`, `List`, `Dict` 等）
- Pydantic 模型优于普通 dict

```python
from typing import Optional, List
from pydantic import BaseModel

class Agent(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    tags: List[str] = []
```

## 依赖管理

### uv 工具链
```bash
# 添加依赖
uv add package-name

# 同步依赖
uv sync

# 运行脚本
uv run python backend/main.py
```

### pyproject.toml 结构
```toml
[project]
name = "agent-platform"
version = "0.1.0"
requires-python = ">=3.11"  # AgentScope 2.0 强制要求

dependencies = [
    "agentscope[service]>=2.0.6",
    "passlib[bcrypt]",
    "uvicorn",
]

[tool.uv]
dev-dependencies = [
    "pytest",
    "pytest-asyncio",
]
```

## 数据模型设计

### 与 AgentScope 解耦
使用独立数据库表存储扩展数据，通过 `agent_id` 关联：

```python
# ❌ 错误：修改 AgentScope 的模型
class Agent(AgentScopeAgent):
    published: bool  # 不要这样做！

# ✅ 正确：创建独立的发布记录表
class AgentPublication(Base):
    __tablename__ = "agent_publications"
    
    id: str
    agent_id: str  # 外键关联到 AgentScope 的 Agent
    published: bool
    published_at: datetime
    published_by: str
```

### Pydantic vs SQLAlchemy
- **API 层**: 使用 Pydantic 模型（请求/响应）
- **数据层**: 使用 SQLAlchemy 模型（数据库 ORM）
- 两者之间需要转换

```python
from pydantic import BaseModel
from sqlalchemy.orm import DeclarativeBase, Mapped

# API 层
class UserResponse(BaseModel):
    user_id: str
    username: str
    role: str

# 数据层
class UserModel(Base):
    __tablename__ = "users"
    
    user_id: Mapped[str] = mapped_column(primary_key=True)
    username: Mapped[str]
    password_hash: Mapped[str]
    role: Mapped[str]
    
    def to_response(self) -> UserResponse:
        return UserResponse(
            user_id=self.user_id,
            username=self.username,
            role=self.role,
        )
```

## 错误处理

### FastAPI HTTPException
```python
from fastapi import HTTPException, status

# 标准错误响应
raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Agent not found",
)

# 带额外信息
raise HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail={
        "message": "Invalid input",
        "field": "agent_name",
        "constraint": "must be alphanumeric",
    },
)
```

### 异步异常处理
```python
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )
```

## 异步编程

### async/await 规范
```python
# ✅ 异步端点
@router.post("/sessions/")
async def create_session(request: CreateSessionRequest) -> SessionResponse:
    session_id = await session_service.create(request)
    return SessionResponse(session_id=session_id)

# ✅ 异步服务层
class SessionService:
    async def create(self, request: CreateSessionRequest) -> str:
        # 异步数据库操作
        async with db.session() as session:
            result = await session.execute(...)
            return result.scalar_one()
```

### 注意事项
- AgentScope 2.0 的 `Agent.reply()` 是 **async** 方法
- 所有 I/O 操作（数据库、网络）应使用 async
- 避免在异步函数中使用阻塞操作（`time.sleep` → `asyncio.sleep`）

## 配置管理

### 环境变量
```python
import os
from typing import Optional

# 必需配置
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# 可选配置
CLAWHUB_API_TOKEN: Optional[str] = os.getenv("CLAWHUB_API_TOKEN")
AMAP_API_KEY: Optional[str] = os.getenv("AMAP_API_KEY")

# 功能开关
SANDBOX_BACKEND = os.getenv("SANDBOX_BACKEND", "local")  # local|docker|k8s
```

### .env 文件
```bash
# .env.example
REDIS_HOST=localhost
REDIS_PORT=6379
CLAWHUB_API_TOKEN=your_token_here
AMAP_API_KEY=your_key_here
SANDBOX_BACKEND=local
```

## 日志规范

### 日志级别
```python
import logging

logger = logging.getLogger(__name__)

# DEBUG: 详细诊断信息
logger.debug(f"Processing session {session_id}")

# INFO: 一般信息
logger.info(f"Session {session_id} created successfully")

# WARNING: 可恢复的错误
logger.warning(f"Agent {agent_id} not found, using default")

# ERROR: 严重错误
logger.error(f"Failed to create session: {e}", exc_info=True)
```

## 测试规范

### 单元测试
```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_session():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/sessions/",
            json={"user_id": "test", "agent_id": "agent1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
```

### 测试依赖
```toml
[tool.uv]
dev-dependencies = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "httpx>=0.24.0",
]
```

## 性能优化

### 数据库连接池
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

engine = create_async_engine(
    "postgresql+asyncpg://user:pass@localhost/db",
    pool_size=20,
    max_overflow=0,
)
```

### 缓存策略
```python
from functools import lru_cache

@lru_cache(maxsize=128)
def get_agent_config(agent_id: str) -> dict:
    # 缓存 Agent 配置，避免重复查询
    return fetch_from_db(agent_id)
```

### 批量操作
```python
# ❌ N+1 查询问题
for agent_id in agent_ids:
    agent = await db.get(Agent, agent_id)
    process(agent)

# ✅ 批量查询
agents = await db.execute(
    select(Agent).where(Agent.id.in_(agent_ids))
)
for agent in agents.scalars():
    process(agent)
```

## 安全规范

### 密码存储
```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 哈希密码
hashed = pwd_context.hash("plain_password")

# 验证密码
is_valid = pwd_context.verify("plain_password", hashed)
```

### API 密钥管理
```python
# ❌ 不要在响应中返回密钥
class RemoteAgent(BaseModel):
    name: str
    base_url: str
    api_key: str  # 危险！

# ✅ 使用只写字段
class RemoteAgent(BaseModel):
    name: str
    base_url: str
    api_key: str = Field(..., exclude=True)  # 不会序列化
```

### CORS 配置
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # 开发环境
    # allow_origins=["*"],  # ⚠️ 仅用于开发测试
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 模块组织

### 扩展模块结构
```
backend/_auth/
├── __init__.py
├── models.py          # 数据模型（SQLAlchemy）
├── schemas.py         # API 模式（Pydantic）
├── service.py         # 业务逻辑
├── router.py          # FastAPI 路由
├── middleware.py      # 中间件
└── dependencies.py    # 依赖注入
```

### 职责分离
- **models.py**: 数据库模型定义
- **schemas.py**: API 请求/响应模型
- **service.py**: 业务逻辑（不依赖 FastAPI）
- **router.py**: HTTP 端点（薄层，调用 service）
- **dependencies.py**: FastAPI 依赖函数

```python
# service.py (业务逻辑)
class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_user(self, username: str, password: str) -> User:
        # 业务逻辑
        pass

# router.py (HTTP 端点)
@router.post("/users/")
async def create_user(
    request: CreateUserRequest,
    service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    user = await service.create_user(request.username, request.password)
    return UserResponse.from_orm(user)
```
