# 开发工作流和最佳实践

## 开发环境设置

### 后端启动
```bash
# 进入后端目录
cd backend

# 同步依赖（使用 uv）
uv sync

# 启动开发服务器（热重载）
uv run python main.py

# 或直接使用 uvicorn
uv run uvicorn main:app --host 0.0.0.0 --port 9000 --reload
```

**前置条件:**
- Python 3.11+ 已安装
- Redis 运行在 `localhost:6379`
- Qdrant 可选（默认使用内存模式）

### 前端启动
```bash
# 进入前端目录
cd frontend

# 安装依赖（使用 pnpm）
pnpm install

# 启动开发服务器
pnpm dev

# 访问 http://localhost:5173
```

**Vite 代理配置:**
前端开发服务器自动代理 `/api` 请求到 `http://localhost:9000`。

### 首次设置流程
1. 访问 `http://localhost:5173`
2. 自动跳转到 `/setup` 页面
3. 配置服务器地址（默认 `http://localhost:9000`）
4. 输入用户名
5. 点击"完成设置"

配置存储在 localStorage：
- `server_url` - 后端地址
- `username` - 用户标识

## 代码风格和规范

### 后端 (Python)

**使用 Black 格式化:**
```bash
uv run black backend/
```

**类型检查:**
```bash
uv run mypy backend/
```

**关键约定:**
- 所有函数必须有类型注解
- 使用 `async def` 定义异步函数
- Pydantic 模型用于 API schema
- SQLAlchemy 模型用于数据库（如果使用）

### 前端 (TypeScript)

**ESLint 检查:**
```bash
pnpm lint
```

**自动修复:**
```bash
pnpm lint:fix
```

**构建检查:**
```bash
pnpm build
```

**关键约定:**
- 导入按字母序排列，分组换行
- 组件使用函数式声明或箭头函数
- Props 定义使用 interface
- 避免 `any`，使用具体类型或 `unknown`

## 文件组织原则

### 后端模块结构
```
backend/
├── main.py              # 入口文件（调用 agentscope.create_app）
├── _auth/               # 扩展模块示例（计划中）
│   ├── __init__.py
│   ├── models.py       # 数据模型
│   ├── schemas.py      # API Schema
│   ├── service.py      # 业务逻辑
│   ├── router.py       # FastAPI 路由
│   └── dependencies.py # 依赖注入
└── pyproject.toml      # 依赖配置
```

### 前端组件结构
```
src/
├── api/                 # API 客户端（按资源分文件）
├── components/
│   ├── ui/             # shadcn/ui 基础组件（不修改）
│   ├── chat/           # 聊天相关组件
│   ├── dialog/         # 对话框组件
│   ├── panel/          # 面板组件
│   └── ...
├── pages/              # 页面组件
├── hooks/              # 自定义 Hooks
├── lib/                # 工具函数
└── i18n/               # 国际化
```

**组件命名:**
- 页面组件: `ChatPage.tsx`
- 通用组件: `ModelSelect.tsx`
- UI 组件: `button.tsx` (shadcn/ui 风格)

## Git 工作流

### 分支策略
```bash
main          # 主分支，稳定版本
├── feature/  # 功能分支
├── fix/      # 修复分支
└── docs/     # 文档分支
```

### 提交规范
```bash
# 功能
git commit -m "feat: add Agent publishing mechanism"

# 修复
git commit -m "fix: resolve session creation race condition"

# 文档
git commit -m "docs: update API documentation"

# 样式
git commit -m "style: format code with Black"

# 重构
git commit -m "refactor: extract session service layer"

# 测试
git commit -m "test: add unit tests for agent API"
```

## 测试策略

### 后端测试
```bash
# 运行所有测试
uv run pytest

# 运行特定测试
uv run pytest tests/test_agent.py

# 覆盖率报告
uv run pytest --cov=backend
```

**测试结构:**
```python
# tests/test_agent.py
import pytest
from httpx import AsyncClient
from main import app

@pytest.mark.asyncio
async def test_create_agent():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/agent/",
            json={"name": "Test Agent"},
            headers={"X-User-ID": "test-user"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "agent_id" in data
```

### 前端测试
```bash
# 运行测试（需配置）
pnpm test
```

**测试库:**
- `@testing-library/react` - 组件测试
- `vitest` - 测试运行器

## 调试技巧

### 后端调试

**日志输出:**
```python
import logging

logger = logging.getLogger(__name__)
logger.debug(f"Session {session_id} created")
logger.info(f"Agent {agent_id} configured")
logger.warning(f"Rate limit approaching for user {user_id}")
logger.error(f"Failed to connect to Redis: {e}", exc_info=True)
```

**断点调试 (VS Code):**
```json
// .vscode/launch.json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: FastAPI",
      "type": "debugpy",
      "request": "launch",
      "module": "uvicorn",
      "args": ["main:app", "--host", "0.0.0.0", "--port", "9000", "--reload"],
      "cwd": "${workspaceFolder}/backend",
      "justMyCode": false
    }
  ]
}
```

### 前端调试

**浏览器 DevTools:**
- Network: 查看 API 请求/响应
- Console: 查看日志和错误
- React DevTools: 检查组件层级和 state

**调试 SSE 流:**
```typescript
// 添加日志
for await (const event of stream) {
  console.log('SSE Event:', event.type, event);
  // ...
}
```

**VS Code 调试:**
```json
// .vscode/launch.json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Chrome: Frontend",
      "type": "chrome",
      "request": "launch",
      "url": "http://localhost:5173",
      "webRoot": "${workspaceFolder}/frontend/src"
    }
  ]
}
```

## 常见问题和解决方案

### 1. Redis 连接失败
**错误:** `ConnectionError: Error connecting to Redis`

**解决:**
```bash
# 检查 Redis 是否运行
redis-cli ping  # 应返回 PONG

# 启动 Redis
redis-server

# 或使用 Docker
docker run -d -p 6379:6379 redis
```

### 2. 前端 API 代理失败
**错误:** `Failed to fetch` 或 `ECONNREFUSED`

**解决:**
- 检查后端是否运行在 `localhost:9000`
- 确认 `vite.config.ts` 代理配置正确
- 清除浏览器缓存

### 3. Python 版本不匹配
**错误:** `agentscope requires Python >=3.11`

**解决:**
```bash
# 安装 Python 3.11+
# macOS
brew install python@3.11

# Ubuntu
sudo apt install python3.11

# 使用 pyenv
pyenv install 3.11.9
pyenv local 3.11.9
```

### 4. pnpm 依赖安装失败
**错误:** `ERR_PNPM_PEER_DEP_ISSUES`

**解决:**
```bash
# 清除缓存
pnpm store prune

# 重新安装
rm -rf node_modules pnpm-lock.yaml
pnpm install
```

### 5. SSE 连接断开
**症状:** 消息不更新，事件流中断

**解决:**
- 检查网络连接
- 查看浏览器 Console 是否有错误
- 后端检查 Redis 连接
- 增加超时时间

### 6. CORS 错误
**错误:** `Access-Control-Allow-Origin header is missing`

**解决:**
确认 `backend/main.py` 中 CORS 配置：
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 性能优化

### 后端优化

**数据库查询:**
```python
# ❌ N+1 查询
for agent_id in agent_ids:
    agent = await db.get(Agent, agent_id)

# ✅ 批量查询
agents = await db.execute(
    select(Agent).where(Agent.id.in_(agent_ids))
)
```

**缓存策略:**
```python
from functools import lru_cache

@lru_cache(maxsize=128)
def get_model_config(model_name: str) -> dict:
    return load_from_db(model_name)
```

**异步 I/O:**
```python
# ✅ 并发请求
import asyncio

results = await asyncio.gather(
    fetch_agent(agent_id1),
    fetch_agent(agent_id2),
    fetch_agent(agent_id3),
)
```

### 前端优化

**避免重复渲染:**
```typescript
// 使用 React.memo
export const AgentCard = memo(({ agent }: { agent: Agent }) => {
  return <div>{agent.name}</div>;
});

// 使用 useMemo
const filteredAgents = useMemo(
  () => agents.filter(a => a.name.includes(search)),
  [agents, search]
);

// 使用 useCallback
const handleClick = useCallback(
  () => console.log(agentId),
  [agentId]
);
```

**代码分割:**
```typescript
import { lazy, Suspense } from 'react';

const ChatPage = lazy(() => import('./pages/chat'));

<Suspense fallback={<Loading />}>
  <ChatPage />
</Suspense>
```

**虚拟滚动（长列表）:**
```typescript
import { useVirtualizer } from '@tanstack/react-virtual';

// 仅渲染可见项
const virtualizer = useVirtualizer({
  count: messages.length,
  getScrollElement: () => scrollRef.current,
  estimateSize: () => 100,
});
```

## 部署准备

### 环境变量
创建 `.env` 文件：
```bash
# 后端
REDIS_HOST=localhost
REDIS_PORT=6379
CLAWHUB_API_TOKEN=your_token_here
AMAP_API_KEY=your_key_here

# 生产环境
CORS_ORIGINS=https://yourdomain.com
```

### 构建前端
```bash
cd frontend
pnpm build

# 输出到 dist/ 目录
# 使用 Nginx 或其他静态服务器托管
```

### 生产运行后端
```bash
cd backend

# 使用 gunicorn + uvicorn workers
uv run gunicorn main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:9000
```

## 文档维护

### 更新 API 文档
API 文档自动生成（FastAPI）：
```
访问: http://localhost:9000/docs
```

### 更新 Plan.md
当架构或需求变更时，更新 `Plan.md` 文档。

### 更新 .agent/rules
当代码规范或架构模式变化时，更新本规则文档。

## 扩展开发指南

### 添加新的 API 端点

**后端:**
```python
# backend/_mymodule/router.py
from fastapi import APIRouter

router = APIRouter(prefix="/mymodule", tags=["mymodule"])

@router.get("/")
async def list_items():
    return {"items": []}

# backend/main.py
from _mymodule.router import router as mymodule_router
app.include_router(mymodule_router)
```

**前端:**
```typescript
// src/api/mymodule.ts
import { client } from './client';

export const mymoduleApi = {
  list: () => client.get<{ items: unknown[] }>('/mymodule/'),
};

// 在组件中使用
const { items } = await mymoduleApi.list();
```

### 添加新的页面

```typescript
// src/pages/mypage/index.tsx
export function MyPage() {
  return <div>My Page</div>;
}

// src/App.tsx
import { MyPage } from '@/pages/mypage';

const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: '/mypage', element: <MyPage /> },
      // ...
    ],
  },
]);
```

### 添加新的 Context

```typescript
// src/context/MyContext.tsx
import { createContext, useContext, useState } from 'react';

interface MyContextValue {
  data: string;
  setData: (data: string) => void;
}

const MyContext = createContext<MyContextValue | null>(null);

export function MyProvider({ children }: { children: React.ReactNode }) {
  const [data, setData] = useState('');
  return (
    <MyContext.Provider value={{ data, setData }}>
      {children}
    </MyContext.Provider>
  );
}

export function useMyContext() {
  const context = useContext(MyContext);
  if (!context) throw new Error('useMyContext must be used within MyProvider');
  return context;
}
```

## 参考资源

### 官方文档
- AgentScope: https://agentscope.io
- FastAPI: https://fastapi.tiangolo.com
- React: https://react.dev
- TailwindCSS: https://tailwindcss.com
- shadcn/ui: https://ui.shadcn.com

### 社区资源
- AgentScope GitHub: https://github.com/modelscope/agentscope
- MCP Protocol: https://modelcontextprotocol.io
