# AgentScope 2.0 API 规范

## ⚠️ 版本兼容性警告

AgentScope 2.0 与 1.x **完全不兼容**，API 有重大变更。

## 核心 API 变更

### Agent 创建
```python
# ❌ 1.x (已废弃)
from agentscope.agents import DialogAgent

# ✅ 2.0+
from agentscope.agent import Agent
```

### 模型配置
```python
# ✅ 2.0+ 凭证与模型分离
from agentscope.model import DashScopeChatModel, OpenAIChatModel, AnthropicChatModel
from agentscope.credential import DashScopeCredential, OpenAICredential, AnthropicCredential
```

### 消息类型
```python
# ✅ 2.0+
from agentscope.message import UserMsg

# 创建用户消息
msg = UserMsg(name="user", content="Hello")

# 提取文本内容
text = msg.get_text_content()  # Msg.content 是 list[ContentBlock]
```

### 流式响应
```python
# ✅ 2.0+
from agentscope.message import EventType

# agent.reply_stream() 返回异步生成器
async for event in agent.reply_stream(msg):
    if event.type == EventType.TEXT_BLOCK_DELTA:
        print(event.data)
```

### 重要说明
- `Agent.reply()` 是 **async** 方法（1.x 是同步的）
- **没有** ReActAgent/ArxivSearch/BingSearch/Calculator（1.x 有）
- ReAct 循环内置于 Agent（通过 `react_config` 配置）

## 工具系统 (Skill)

### 内置工具
```python
from agentscope.tool import Toolkit

# ✅ 2.0+ 内置工具列表
# 文件操作: Read, Write, Edit, Grep, Glob
# Shell: Bash, PowerShell
# 工具管理: ResetTools, SkillViewer
# 任务管理: TaskCreate, TaskGet, TaskList, TaskUpdate
```

### Toolkit 使用
```python
toolkit = Toolkit()
# 注册内置工具会自动加载
# 挂载到 Agent: Agent(..., toolkit=toolkit)
```

### 安装依赖
```bash
pip install agentscope[tools]  # 安装工具支持
```

## RAG 系统

### 向量存储
```python
from agentscope.rag import QdrantStore

# ✅ 支持的存储后端
vector_store = QdrantStore(location=":memory:")  # 内存模式
# 或 MilvusLiteStore / MongoDBStore / ElasticsearchStore
```

### 知识库管理
```python
from agentscope.app.rag.knowledge_base_manager import CollectionPerKbManager

kb_manager = CollectionPerKbManager(
    storage=storage,
    vector_store=vector_store,
)
```

### RAG Middleware
```python
from agentscope.rag import TextParser, ApproxTokenChunker
from agentscope.middleware import RAGMiddleware
from agentscope.model import DashScopeEmbeddingModel

# 文档解析和切块
parser = TextParser()
chunker = ApproxTokenChunker()
embedding_model = DashScopeEmbeddingModel(...)

# 挂载到 Agent
middleware = RAGMiddleware(
    mode="static",  # 或 "agentic"
    # ...
)
agent = Agent(..., middlewares=[middleware])
```

### 安装依赖
```bash
pip install agentscope[rag]  # 安装 RAG 支持
```

## MCP 集成

### MCP Client
```python
from agentscope.mcp import MCPClient, StdioMCPConfig, HttpMCPConfig

# Stdio 模式 (本地进程)
mcp = MCPClient(
    name="browser-use",
    mcp_config=StdioMCPConfig(
        command="npx",
        args=["@playwright/mcp@latest"],
        env={},
        cwd=None,
    ),
    is_stateful=True,  # 有状态/无状态
)

# HTTP/SSE 模式 (远程服务)
mcp = MCPClient(
    name="amap",
    mcp_config=HttpMCPConfig(
        url="https://mcp.amap.com/mcp?key=xxx",
        headers={},
        timeout=30,
    ),
    is_stateful=False,
)
```

### MCP 命名规则
- MCP 名称必须匹配正则: `^[a-zA-Z0-9_-]+$`
- URL 以 `/sse` 或 `/messages/` 结尾走 SSE 协议

### MCP 依赖
```python
# mcp<2.0.0 是核心依赖 (无需 extra)
from agentscope.mcp import MCPTool

# MCPClient 是 pydantic BaseModel
# 私有字段: _client, _session, _stack, _is_connected
# 方法:
#   - list_raw_tools() -> list[mcp.types.Tool]
#   - get_tool(name: str) -> MCPTool
```

### 挂载到 Toolkit
```python
toolkit = Toolkit()
for tool in mcp.list_raw_tools():
    mcp_tool = mcp.get_tool(tool.name)
    toolkit.register_tool(mcp_tool)
```

## Workspace 管理

### 本地工作空间
```python
from agentscope.app.workspace_manager import LocalWorkspaceManager

workspace_manager = LocalWorkspaceManager(
    basedir="./workspaces",
    default_mcps=[...],  # 默认 MCP 列表
)
```

### Workspace 隔离模式
- `PER_USER`: 每个用户独立工作空间
- `PER_AGENT`: 每个 Agent 独立工作空间（默认）
- `PER_SESSION`: 每个会话独立工作空间

## 长期记忆

### AgenticMemoryMiddleware
```python
from agentscope.middleware import AgenticMemoryMiddleware
from agentscope.workspace import WorkspaceBase

async def longterm_memory_factory(
    user_id: str,
    agent_id: str,
    session_id: str,
    workspace: WorkspaceBase,
) -> list[MiddlewareBase]:
    return [
        AgenticMemoryMiddleware(
            workdir=workspace.workdir,
            backend=workspace.get_backend(),
        ),
    ]

# 挂载到 create_app
app = create_app(
    extra_agent_middlewares=longterm_memory_factory,
    # ...
)
```

记忆存储为 Markdown 文件，位于 workspace 目录下。

## 权限系统

### 权限模式
```python
from agentscope.permission import PermissionContext, PermissionMode

# 权限模式枚举
PermissionMode.EXPLORE  # 只读模式（不能修改/创建/删除文件）
PermissionMode.NORMAL   # 正常模式
PermissionMode.ADMIN    # 管理员模式
```

### SubAgent 模板
```python
from agentscope.app import SubAgentTemplate

explorer_template = SubAgentTemplate(
    type="explorer",
    description="Read-only exploration agent",
    system_prompt_template="...",
    permission_context=PermissionContext(
        mode=PermissionMode.EXPLORE,
    ),
)

# 注册到 create_app
app = create_app(
    custom_subagent_templates=[explorer_template],
    # ...
)
```

## 消息总线

### Redis 消息总线 (推荐生产环境)
```python
from agentscope.app.message_bus import RedisMessageBus

message_bus = RedisMessageBus(
    host="localhost",
    port=6379,
)
```

### 内存消息总线 (仅开发测试)
```python
from agentscope.app.message_bus import InMemoryMessageBus

message_bus = InMemoryMessageBus()
```

## 存储后端

### Redis 存储
```python
from agentscope.app.storage import RedisStorage

storage = RedisStorage(
    host="localhost",
    port=6379,
    db=10,
)
```

## Hub 系统

### MCP Hub
```python
from agentscope.app.hub import GitHubMCPHub

mcp_hubs = [GitHubMCPHub()]
```

### Skill Hub
```python
from agentscope.app.hub import ClawSkillHub

skill_hubs = [
    ClawSkillHub(api_token=os.getenv("CLAWHUB_API_TOKEN"))
]
```

## 渠道系统

### Discord 渠道
```python
from agentscope.app.channel import DiscordChannel

channels = [DiscordChannel]
```

### 飞书渠道
```python
from agentscope.app.channel import FeishuChannel

channels = [FeishuChannel]
```

## Python 版本要求

AgentScope 2.0 **强制要求 Python 3.11+**

```bash
python --version  # 必须 >= 3.11
```
