# API 架构与接口规范

## API 基础架构

### 后端端点前缀
API 端点不使用统一 `/api/` 前缀——各资源前缀直接代理到后端（见 `frontend/vite.config.ts` 中的 proxy 配置）。

### 身份验证
**当前实现（JWT + 双角色）:**
- 登录成功后签发 `access_token`（短时，默认 30 分钟）+ `refresh_token`（长时，默认 7 天）
- 所有请求自动携带 `Authorization: Bearer <token>` header
- Token 存于 localStorage：`access_token`、`refresh_token`、`user_info`、`user_id`
- 401 时自动清除 token 并跳转 `/login`
- **开发模式回退**：无 token 时使用 `X-User-ID` header（`localStorage.getItem('user_id')` 或 `username`），与 Setup 页兼容

**角色访问控制:**
- `AccessControlMiddleware` 拦截 `end_user` 角色访问开发者专用前缀（`/agent`、`/credential`、`/mcp`、`/skill`、`/knowledge*`、`/schedule`、`/channel`、`/hub`、`/model`、`/publish/my`、`/publish/agent`、`/unpublish`、`/auth/register` 等）→ 403
- 公开路径（`/health`、`/docs`、`/redoc`、`/openapi.json`、`/auth/token`、`/auth/refresh`）不受角色检查限制（见 `app/auth/middleware.py` 的 `PUBLIC_PATHS`）
- 路由级使用 `require_role(Role.DEVELOPER)` 依赖做细粒度控制

### 错误处理
```typescript
// ApiError 结构
class ApiError extends Error {
  status: number;    // HTTP 状态码
  detail: string;    // 从后端提取的错误详情
}

// 特殊状态码
TIMEOUT_STATUS = 408  // 请求超时
status = 0            // 网络错误（无法连接到服务器）
```

自动 toast 提示错误，除非设置 `{ silent: true }`。

## 平台扩展 API

### Auth API (`/auth/`)

**端点列表:**
- `POST /auth/login` - JSON 登录（username + password），返回 tokens
- `GET /auth/oauth/login` - 生成 OAuth2.0 授权 URL（Authorization Code + PKCE）
- `POST /auth/callback` - OAuth2.0 回调（code → 本地 JWT）
- `GET /auth/me` - 获取当前用户信息（需认证）
- `POST /auth/refresh` - 刷新 access token
- `POST /auth/logout` - 注销（协调点，客户端清空本地 token）
- `POST /auth/register` - 注册新用户（仅 developer 角色）

**数据结构:**
```typescript
interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
  user_id: string;
  username: string;
  role: 'developer' | 'end_user';
}

interface UserInfoResponse {
  user_id: string;
  username: string;
  role: string;
  created_at: string | null;
}

interface LoginUrlResponse {
  login_url: string;   // 跳转 OAuth 授权页
  state: string;       // CSRF 防护
  redirect_uri: string;
}
```

**登录流程:**
```
POST /auth/login (username, password)
  ├─ 已配置 OAUTH_AUTH_SERVER_URL?  →  委托外部鉴权服务 (grant_type=password)
  │     ├─ 获取 userinfo → 同步/创建本地用户
  │     └─ 签发本地 JWT
  └─ 否则 / 回退  →  本地 bcrypt 校验 users 表
        └─ 签发本地 JWT
```

**JWT 结构:**
```json
{
  "sub": "user_id",
  "username": "xxx",
  "role": "developer",
  "roles": ["developer"],
  "permissions": ["agent:chat", "..."],
  "type": "access" | "refresh",
  "iss": "agent-platform",
  "iat": 1234567890,
  "exp": 1234567890
}
```

### Publish API (`/publish/`, `/unpublish/`)

**端点列表:**
- `POST /publish/agent/{agent_id}` - 发布/更新 Agent（开发者；body 含 release_notes、execution_mode、input_schema）
- `POST /unpublish/agent/{agent_id}` - 取消发布（开发者）
- `GET /publish/list` - 所有已发布 Agent（终端用户可见）
- `GET /publish/my` - 当前开发者发布的 Agent
- `GET /publish/{agent_id}` - 单个已发布 Agent 详情（含 input_schema）
- `GET /publish/{agent_id}/versions` - 版本历史
- `GET /publish/{agent_id}/versions/{version}` - 指定版本详情（含 agent_snapshot）
- `POST /publish/{agent_id}/rollback/{version}` - 回滚到指定版本（开发者）
- `POST /publish/{agent_id}/execute` - 任务模式执行（body: `{ input: params }`）
- `POST /publish/{agent_id}/chat` - 对话模式启动（创建 session）

**数据结构:**
```typescript
interface PublishRequest {
  release_notes: string;                    // 必填
  execution_mode: 'chat' | 'task';
  input_schema?: JSONSchema | null;         // task 模式必填
}

interface PublishResponse {
  version: string;          // 7 位短 SHA256 哈希，如 "a3f2c8d"
  agent_id: string;
  published_at: string;
}

interface PublishedAgentDetail {
  id: string;
  agent_id: string;
  agent_name: string;
  agent_description: string;
  published: boolean;
  current_version: string;
  execution_mode: 'chat' | 'task';
  input_schema: JSONSchema | null;
  published_at: string | null;
  unpublished_at: string | null;
  published_by: string;
}

interface AgentVersion {
  id: string;
  version: string;
  release_notes: string;
  execution_mode: 'chat' | 'task';
  published_by: string;
  published_at: string;
  is_current: boolean;
}

interface AgentVersionDetail extends AgentVersion {
  input_schema: JSONSchema | null;
  agent_snapshot: Record<string, unknown>;
}

interface ExecuteResponse {
  session_id: string;
  agent_id: string;
}
```

**实现要点:**
- 版本号由后端生成（`agent_id + release_notes + timestamp` 的 SHA256 前 7 位）
- 发布时保存 Agent 配置快照（`agent_snapshot`）用于回滚
- 任务模式执行：创建 session + 将表单参数格式化为首条用户消息注入（不修改 system_prompt）
- 对话模式启动：创建 session 并记录执行审计（`agent_executions` 表）

### Health API (`/health`)

**端点:**
- `GET /health` - 健康检查（无认证要求）

```typescript
interface HealthResponse {
  status: 'ok' | 'not_ready';
  version: string;
  components: Record<string, 'ok' | 'not_ready' | 'disabled'>;
}
```

组件检查包括：`storage`、`message_bus`、`workspace_manager`、`chat_service`、`session_service`、`scheduler_manager` 等；`mcp_hubs`/`skill_hubs` 未配置时为 `disabled`。

## 核心 API 模块

### Agent API (`/agent/`)

**端点列表:**
- `GET /agent/` - 获取 Agent 列表
- `GET /agent/schema/v2` - 获取 AgentData JSON Schema（用于动态表单渲染）
- `POST /agent/` - 创建 Agent
- `PATCH /agent/{agentId}` - 更新 Agent
- `DELETE /agent/{agentId}` - 删除 Agent

**Agent 数据结构:**
```typescript
interface AgentData {
  id: string;
  name: string;
  system_prompt: string;
  context_config: ContextConfig;      // 上下文压缩配置
  react_config: ReActConfig;          // ReAct 循环配置
  invite_config: InviteConfig;        // 子 Agent 邀请配置
}

interface AgentView extends RecordBase {
  user_id: string;
  data: AgentData;
  editable: boolean;  // 是否可编辑（共享权限判断）
}
```

**配置对象:**
```typescript
interface ContextConfig {
  trigger_ratio?: number;           // 触发压缩的比例
  reserve_ratio?: number;           // 保留的上下文比例
  tool_result_limit?: number;       // 工具结果长度限制
  compression_prompt?: string;      // 自定义压缩提示词
  summary_template?: string;        // 摘要模板
}

interface ReActConfig {
  max_iters?: number;              // 最大迭代次数
  stop_on_reject?: boolean;        // 工具调用被拒绝时是否停止
}

interface InviteConfig {
  invitable?: boolean;             // 是否可被邀请为子 Agent
  invite_description?: string | null;  // 邀请描述
}
```

### Session API (`/sessions/`)

**端点列表:**
- `GET /sessions/?agent_id={agentId}` - 获取 Agent 的会话列表
- `POST /sessions/` - 创建新会话
- `PATCH /sessions/{sessionId}` - 更新会话配置（模型、知识库等）
- `DELETE /sessions/{sessionId}` - 删除会话
- `POST /sessions/{sessionId}/interrupt` - 中断正在运行的会话
- `GET /sessions/{sessionId}/messages` - 获取消息历史（分页）
- `GET /sessions/{sessionId}/stream` - SSE 事件流订阅

**Session 数据结构:**
```typescript
interface SessionRecord extends RecordBase {
  user_id: string;
  agent_id: string;
  source: 'user' | 'schedule' | 'channel';  // 会话来源
  source_schedule_id: string | null;
  source_channel_id: string | null;
  team_id: string | null;  // 团队 ID（Team 功能）
  config: SessionConfig;
  state: AgentState;       // Agent 状态（大部分已裁剪）
}

interface SessionConfig {
  name: string;
  chat_model_config: ChatModelConfig;
  fallback_chat_model_config: ChatModelConfig | null;  // 备用模型
  tts_model_config: TTSModelConfig | null;             // TTS 配置
  knowledge_config: SessionKnowledgeConfig | null;     // 知识库配置
  workspace_id: string;
  cwd: string | null;  // 当前工作目录（workspace 内的路径）
}
```

**SessionView (增强返回):**
```typescript
interface SessionView {
  session: SessionRecord;  // state 已裁剪（移除 context/summary/tool_context）
  is_running: boolean;     // @deprecated 使用 status
  status: 'running' | 'idle' | 'awaiting_permission' | 'awaiting_external_result';
  team: TeamDetailResponse | null;  // 团队详情（若在团队中）
}
```

**更新会话（PATCH 语义）:**
- 省略字段 → 保持不变
- 设置为 `null` → 清除/禁用
- 设置为值 → 替换

### Chat API (`/chat/`)

**Fire-and-forget 触发模式:**
```typescript
// POST /chat/
interface ChatRequest {
  agent_id: string;
  session_id: string;
  input: Msg | Msg[] | UserConfirmResultEvent | ExternalExecutionResultEvent | null;
}

// 响应立即返回
{ status: "started", session_id: "..." }

// 实际事件通过 SSE 流 (GET /sessions/{id}/stream) 推送
```

**SSE 事件流:**
```typescript
// 订阅方式
sessionApi.streamEvents(sessionId, agentId, signal)

// 事件类型（来自 @agentscope-ai/agentscope/event）
type AgentEvent = 
  | { type: 'text_block_start', ... }
  | { type: 'text_block_delta', text: string, ... }
  | { type: 'text_block_end', ... }
  | { type: 'tool_call_start', tool_name: string, ... }
  | { type: 'tool_call_end', result: unknown, ... }
  | { type: 'user_confirm_request', ... }
  | { type: 'external_execution_request', ... }
  | { type: 'message', msg: Msg, ... }
  | { type: 'error', error: string, ... }
  // ...
```

### MCP API (`/mcp/`)

**库管理 API:**
- `GET /mcp/` - 获取用户的 MCP 库列表
- `POST /mcp/` - 手动添加 MCP（不通过 Hub）
- `GET /mcp/{mcpId}` - 获取 MCP 详情
- `PATCH /mcp/{mcpId}` - 更新 MCP 配置
- `DELETE /mcp/{mcpId}` - 从库中删除 MCP

**Workspace MCP API:**
- `GET /workspace/{workspaceId}/mcp` - 获取 workspace 中已启用的 MCP
- `POST /workspace/{workspaceId}/mcp` - 添加 MCP 到 workspace
- `PATCH /workspace/{workspaceId}/mcp/{name}` - 更新 workspace MCP
- `DELETE /workspace/{workspaceId}/mcp/{name}` - 从 workspace 移除 MCP

**MCP 数据结构:**
```typescript
interface MCPClient {
  name: string;          // 唯一标识符 (正则: ^[a-zA-Z0-9_-]+$)
  is_stateful: boolean;  // 有状态/无状态
  mcp_config: StdioMCPConfig | HttpMCPConfig;
}

interface StdioMCPConfig {
  type: 'stdio_mcp';
  command: string;
  args?: string[] | null;
  env?: Record<string, string> | null;
  cwd?: string | null;
  encoding_error_handler?: 'strict' | 'ignore' | 'replace';
}

interface HttpMCPConfig {
  type: 'http_mcp';
  url: string;
  headers?: Record<string, string> | null;
  timeout?: number | null;
}

interface MCPClientStatus extends MCPClient {
  is_healthy: boolean;
  tools: ToolInfo[];
  error: string | null;  // 健康检查失败原因
}
```

### Hub API (`/hub/`)

**MCP Hub:**
- `GET /hub/mcp/` - 获取已注册的 MCP Hub 列表
- `GET /hub/mcp/{hubId}` - 浏览 Hub（分页、搜索）
- `GET /hub/mcp/{hubId}/{cardId}` - 获取 MCP 卡片详情
- `POST /hub/mcp/{hubId}/{cardId}/install` - 安装 MCP 到库

**Skill Hub:**
- `GET /hub/skill/` - 获取已注册的 Skill Hub 列表
- `GET /hub/skill/{hubId}` - 浏览 Hub
- `GET /hub/skill/{hubId}/{cardId}` - 获取 Skill 卡片详情
- `POST /hub/skill/{hubId}/{cardId}/install` - 安装 Skill 到库

**Hub 卡片结构:**
```typescript
interface MCPCard {
  hub_id: string;
  id: string;              // 卡片 ID（不一定 URL 安全，需编码）
  name: string;
  display_name?: string | null;
  description: string;
  tags: string[];
  version?: string | null;
  is_stateful: boolean;
  author?: string | null;
  icon_url?: string | null;
  url?: string | null;
  installs?: number | null;
  downloads?: number | null;
  auth: 'none' | 'inputs';         // 是否需要配置表单
  inputs_schema: Partial<JSONSchema>;  // 安装表单 Schema
  readme?: string | null;          // 详情页才返回
  config_template: StdioMCPConfig | HttpMCPConfig;  // 模板（含占位符）
}
```

### Knowledge Base API (`/knowledge_bases/`)

**核心端点:**
- `GET /knowledge_bases/` - 获取知识库列表
- `POST /knowledge_bases/` - 创建知识库
- `GET /knowledge_bases/{kbId}` - 获取详情
- `PATCH /knowledge_bases/{kbId}` - 更新元数据（不能修改 embedding 模型）
- `DELETE /knowledge_bases/{kbId}` - 删除知识库

**文档管理:**
- `GET /knowledge_bases/{kbId}/documents` - 获取文档列表
- `POST /knowledge_bases/{kbId}/documents` - 上传文档（multipart/form-data）
- `GET /knowledge_bases/{kbId}/documents/status` - 批量查询文档状态
- `DELETE /knowledge_bases/{kbId}/documents/{docId}` - 删除文档
- `POST /knowledge_bases/{kbId}/search` - 向量搜索

**配置查询:**
- `GET /knowledge_bases/embedding_models` - 获取可用的 Embedding 模型（受策略限制）
- `GET /knowledge_bases/middleware/parameters_schema` - RAG 中间件参数 Schema
- `GET /knowledge_bases/supported_content_types` - 支持的文件类型

**数据结构:**
```typescript
interface KnowledgeBaseView {
  id: string;
  name: string;
  description: string;
  embedding_model_config: EmbeddingModelConfig;
  created_at: string;
  updated_at: string;
  editable: boolean;
}

interface EmbeddingModelConfig {
  type: string;
  credential_id: string;
  model: string;
  dimensions: number;  // 固定在创建时，不可更改
  parameters: Record<string, unknown>;
}

type KnowledgeDocumentStatus = 
  | 'pending'
  | 'parsing'
  | 'chunking'
  | 'indexing'
  | 'ready'
  | 'error';

interface KnowledgeDocumentView {
  id: string;
  filename: string;
  size: number;
  content_type: string | null;
  status: KnowledgeDocumentStatus;
  error: string | null;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}
```

### Schedule API (`/schedule/`)

**端点列表:**
- `GET /schedule/` - 获取调度任务列表
- `POST /schedule/` - 创建调度任务
- `GET /schedule/{scheduleId}` - 获取详情
- `PATCH /schedule/{scheduleId}` - 更新任务
- `DELETE /schedule/{scheduleId}` - 删除任务
- `GET /schedule/{scheduleId}/sessions` - 获取任务执行产生的会话

**数据结构:**
```typescript
interface ScheduleData {
  name: string;
  description: string;
  enabled: boolean;
  timezone: string;                    // IANA 时区
  cron_expression: string;             // 标准 cron 表达式
  started_at: string;                  // ISO datetime
  ended_at: string | null;             // null = 无限期
  chat_model_config: ChatModelConfig;
  stateful: boolean;                   // 是否保持会话状态
  permission_mode: PermissionMode;
  source: 'USER' | 'AGENT';           // 创建来源
  source_session_id: string;
}
```

### Channel API (`/channel/`)

**端点列表:**
- `GET /channel/` - 获取渠道列表
- `GET /channel/types` - 获取支持的渠道类型
- `POST /channel/` - 创建渠道
- `GET /channel/{channelId}` - 获取详情
- `PATCH /channel/{channelId}` - 更新配置
- `DELETE /channel/{channelId}` - 删除渠道
- `GET /channel/{channelId}/status` - 获取连接状态
- `GET /channel/{channelId}/sessions` - 获取渠道产生的会话
- `GET /channel/{channelId}/chats` - 获取渠道中的对话列表

**数据结构:**
```typescript
interface ChannelRecord {
  id: string;
  channel_type: string;              // 'discord' | 'feishu'
  name: string | null;
  user_id: string;
  platform_bot_id: string;
  enabled: boolean;
  platform_config: Record<string, unknown>;
  routing: RoutingConfig;            // 路由规则
  session: SessionSettings;          // 会话默认配置
  created_at: string;
  updated_at: string;
}

interface RoutingConfig {
  bindings: ChannelBinding[];
}

interface ChannelBinding {
  match_key: string;                 // 匹配字段（如 'channel_id'）
  match_value: string;               // 匹配值（'*' = 通配符）
  agent_id: string;                  // 路由到的 Agent
  session_scope: 'per_chat' | 'per_chat_user';  // 会话分组策略
}

type ChannelState = 'stopped' | 'connecting' | 'retrying' | 'connected' | 'failed';
```

### Credential API (`/credential/`)

**端点列表:**
- `GET /credential/` - 获取凭证列表
- `GET /credential/schemas` - 获取所有凭证类型的 Schema
- `POST /credential/` - 创建凭证
- `GET /credential/{credentialId}` - 获取详情
- `PATCH /credential/{credentialId}` - 更新凭证
- `DELETE /credential/{credentialId}` - 删除凭证

**数据结构:**
```typescript
interface CredentialView extends RecordBase {
  user_id: string;
  data: Record<string, unknown>;     // 凭证数据（共享时秘密字段被裁剪）
  editable: boolean;                 // 是否可编辑
}

interface CredentialSchema extends JSONSchema {
  title: string;                     // 凭证类型名称
  type: string;                      // 'object'
  properties: Record<string, JSONSchemaProperty>;
  required?: string[];
}
```

### Workspace API (`/workspace/`)

**端点列表:**
- `GET /workspace/{workspaceId}/status` - 获取 workspace 状态（路径、Git 状态）
- `GET /workspace/{workspaceId}/list?path={path}` - 列出目录内容
- `GET /workspace/{workspaceId}/read?path={path}` - 读取文件内容
- `POST /workspace/{workspaceId}/write` - 写入文件
- `DELETE /workspace/{workspaceId}/delete?path={path}` - 删除文件/目录

**数据结构:**
```typescript
interface WorkspaceStatus {
  workdir: string;    // Workspace 根目录绝对路径
  cwd: string;        // 当前工作目录绝对路径
  git: GitStatus | null;
}

interface GitStatus {
  branch: string | null;
  head: string | null;
  ahead: number | null;
  behind: number | null;
  insertions: number;
  deletions: number;
  staged: number;
  unstaged: number;
  untracked: number;
  conflicted: number;
}
```

### Model API (`/model/`, `/embedding-model/`, `/tts-model/`)

**端点列表:**
- `GET /model/?provider={provider}` - 获取聊天模型列表
- `GET /embedding-model/?provider={provider}` - 获取 Embedding 模型列表
- `GET /tts-model/?provider={provider}` - 获取 TTS 模型列表

## 通用约定

### RecordBase
所有记录类型都继承自 `RecordBase`:
```typescript
interface RecordBase {
  id: string;
  created_at: string;  // ISO 8601
  updated_at: string;
}
```

### 分页响应
列表端点通常返回：
```typescript
interface ListResponse<T> {
  items: T[];  // 或具名字段如 agents, sessions, schedules
  total: number;
}
```

Hub 使用游标分页：
```typescript
interface HubPage<T> {
  cards: T[];
  next_cursor: string | null;  // null = 最后一页
}
```

### PATCH 语义
- **省略字段** → 保持不变
- **设置为 `null`** → 清除/禁用（对于可选字段）
- **设置为值** → 替换

### 权限判断
资源视图包含 `editable: boolean` 字段，表示当前用户是否可编辑/删除。

### 错误响应
```json
{
  "detail": "Error message"
}
```

或更详细的：
```json
{
  "detail": {
    "message": "Invalid input",
    "field": "agent_name",
    "constraint": "must be alphanumeric"
  }
}
```
