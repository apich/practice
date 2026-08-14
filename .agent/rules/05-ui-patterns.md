# UI 组件与交互模式

## 核心页面架构

### AppLayout (应用布局)
```
┌─────────────────────────────────────┐
│  AppSidebar  │  SidebarInset        │
│  (导航栏)    │  (内容区 <Outlet>)   │
│              │                       │
│              │                       │
└─────────────────────────────────────┘
```

**技术实现:**
- 使用 `SidebarProvider` 管理侧边栏状态
- `<Outlet>` 渲染当前路由的页面组件
- 侧边栏可折叠（通过 `SidebarTrigger`）

### ChatViewport (聊天视图核心)

**组件职责:**
ChatViewport 是整个聊天交互的核心组件，负责：
- 消息历史渲染（滚动加载）
- 模型选择和参数配置
- 权限模式切换
- 工作空间面板管理
- SSE 事件流订阅
- 实时状态更新

**布局结构:**
```
┌──────────────────────────────────────────────────────┐
│ Header (模型选择 | 权限模式 | 面板切换)                │
├──────────────────────────────────────────────────────┤
│                                                      │
│  ChatContent (消息列表)  │  PanelDock (右侧面板)   │
│                         │                          │
│                         │  - MCP                   │
│                         │  - Skill                 │
│                         │  - Knowledge             │
│                         │  - Permission            │
│                         │  - Team                  │
│                         │  - Task                  │
│                                                      │
└──────────────────────────────────────────────────────┘
```

**面板系统 (PanelDock):**
- 支持多列布局（每列最多 2 个面板）
- 拖放排序
- 折叠/展开
- 布局持久化到 `localStorage` (key: `chat_panel_layout`)

**已知面板类型:**
```typescript
type PanelKey =
  | 'mcp'         // MCP 工具管理
  | 'skill'       // Skill 管理
  | 'permission'  // 权限请求处理
  | 'knowledge'   // 知识库查询
  | 'team'        // 团队成员管理
  | 'task';       // 任务管理
```

## 核心交互流程

### 1. 创建和启动会话

```typescript
// 1. 创建会话
const { session_id } = await sessionApi.create({
  agent_id: 'agent-123',
  workspace_id: 'workspace-456',  // 可选
  chat_model_config: { ... },     // 可选
});

// 2. 导航到聊天页
navigate(`/admin/chat/${agentId}/${session_id}`);

// 3. 订阅 SSE 事件流
const eventStream = sessionApi.streamEvents(session_id, agent_id, abortSignal);
for await (const event of eventStream) {
  handleEvent(event);
}
```

### 2. 发送消息和接收响应

```typescript
// 1. 构造用户消息
const userMsg: Msg = {
  id: uuid(),
  role: 'user',
  name: 'User',
  content: [{ type: 'text', text: 'Hello!' }],
};

// 2. 触发聊天（fire-and-forget）
await chatApi.trigger({
  agent_id: agentId,
  session_id: sessionId,
  input: userMsg,
});

// 3. 通过 SSE 接收事件
// 事件流已在步骤 1.3 订阅
// 事件类型：
// - text_block_delta: 流式文本片段
// - tool_call_start/end: 工具调用
// - user_confirm_request: 需要用户确认
// - message: 完整消息
// - error: 错误
```

### 3. 处理权限请求 (HITL)

**流程:**
```typescript
// 1. 收到 user_confirm_request 事件
{
  type: 'user_confirm_request',
  request_id: '...',
  tool_name: 'Write',
  args: { path: '/file.txt', content: '...' },
  message: 'Allow agent to write file?',
}

// 2. 用户选择 Approve/Reject
const response: UserConfirmResultEvent = {
  type: 'user_confirm_result',
  request_id: '...',
  approved: true,  // or false
};

// 3. 回传决策
await chatApi.trigger({
  agent_id: agentId,
  session_id: sessionId,
  input: response,
});

// 4. Agent 继续执行
```

### 4. 更新会话配置

```typescript
// 切换模型
await sessionApi.update(sessionId, agentId, {
  chat_model_config: {
    type: 'dashscope_chat',
    credential_id: 'cred-123',
    model: 'qwen-plus',
    parameters: {},
  },
});

// 更新返回 409 表示会话正在运行，无法更新
// 设置 { silent: true } 避免自动 toast
```

### 5. 中断运行中的会话

```typescript
// 发送中断信号
await sessionApi.interrupt(sessionId, agentId);

// 返回 202 Accepted，中断信号已广播
// Agent 会在下一个安全点停止
```

### 6. 工作空间文件操作

```typescript
// 列出目录
const { path, entries } = await workspaceApi.list(workspaceId, '/src');

// 读取文件
const content = await workspaceApi.read(workspaceId, '/src/main.py');

// 写入文件
await workspaceApi.write(workspaceId, {
  path: '/src/new.py',
  content: 'print("hello")',
});

// 删除文件
await workspaceApi.delete(workspaceId, '/src/old.py');
```

## 状态管理模式

### Context-based 状态
项目使用 React Context 管理跨组件状态：

**UploadContext (文件上传):**
```typescript
const { files, addFile } = useUpload();
```

### Custom Hooks

**核心 Hooks:**
- `useMessages(sessionId, agentId)` - 消息历史管理
- `useSessions(agentId)` - 会话列表管理
- `useWorkspace(workspaceId)` - Workspace 文件树
- `useWorkspaceStatus(sessionId, agentId)` - Workspace 状态（Git）
- `useKnowledgeBases()` - 知识库列表
- `useAvailableModels(provider)` - 可用模型列表

**实现模式:**
```typescript
// 典型的 Hook 结构
export function useAgent(agentId: string) {
  const [agent, setAgent] = useState<Agent | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  
  useEffect(() => {
    setLoading(true);
    agentApi.get(agentId)
      .then(setAgent)
      .catch(setError)
      .finally(() => setLoading(false));
  }, [agentId]);
  
  return { agent, loading, error };
}
```

### 本地状态持久化

**localStorage 键:**
- `access_token` - JWT 访问令牌
- `refresh_token` - JWT 刷新令牌
- `user_info` - 登录用户信息 JSON（`{ user_id, username, role }`）
- `user_id` - 规范化用户标识（UUID，优先于 username）
- `username` - 用户名字符串（仅展示用途）
- `chat_panel_layout` - 聊天面板布局
- `i18nextLng` - 语言偏好（i18next 自动管理）

## 动态表单渲染

### JSON Schema → Form

**Agent 创建/编辑:**
```typescript
// 1. 获取 Schema
const { schema } = await agentApi.getSchema();

// 2. Schema 结构
{
  type: 'object',
  properties: {
    name: { type: 'string', title: 'Agent Name' },
    system_prompt: { type: 'string', format: 'textarea' },
    context_config: {
      type: 'object',
      properties: {
        trigger_ratio: { type: 'number', minimum: 0, maximum: 1 },
        // ...
      }
    },
    react_config: { type: 'object', ... },
    invite_config: { type: 'object', ... },
  },
  required: ['name'],
}

// 3. 前端根据 Schema 动态渲染表单
// - 顶层标量字段 → "identity" 部分
// - 顶层对象字段 → 独立配置部分（折叠面板）
```

**字段类型映射:**
- `type: 'string'` → `<Input>`
- `type: 'string', format: 'textarea'` → `<Textarea>`
- `type: 'string', format: 'password'` → `<Input type="password">`
- `type: 'number'` → `<Input type="number">`
- `type: 'boolean'` → `<Switch>` 或 `<Checkbox>`
- `enum: [...]` → `<Select>` 下拉选择

**MCP/Credential 安装表单:**
同样基于 `inputs_schema` 动态渲染，支持 `writeOnly: true` 标记密钥字段。

## 通知系统

### Toast (sonner)

**使用方式:**
```typescript
import { toast } from 'sonner';

// 成功提示
toast.success('Session created successfully');

// 错误提示（API 自动调用）
toast.error('Failed to create session: Agent not found');

// 信息提示
toast.info('Model updated');

// 警告提示
toast.warning('Session is running, cannot update');
```

**位置:** `top-right`（配置在 `App.tsx` 的 `<Toaster>`）

## 国际化 (i18n)

### 使用翻译

```typescript
import { useTranslation } from '@/i18n/useI18n';

function Component() {
  const { t } = useTranslation();
  
  return (
    <div>
      <h1>{t('chat.title')}</h1>
      <p>{t('chat.description', { name: 'Agent' })}</p>
    </div>
  );
}
```

### 切换语言

```typescript
const { i18n } = useTranslation();
i18n.changeLanguage('zh');  // 或 'en'
```

### 翻译文件位置
- `src/i18n/locales/en.json`
- `src/i18n/locales/zh.json`

## SSE 事件处理模式

### 订阅和处理

```typescript
// 1. 创建 AbortController
const abortController = new AbortController();

// 2. 订阅事件流
const stream = sessionApi.streamEvents(
  sessionId,
  agentId,
  abortController.signal
);

// 3. 处理事件
try {
  for await (const event of stream) {
    switch (event.type) {
      case 'text_block_delta':
        appendText(event.text);
        break;
      case 'tool_call_start':
        showToolCall(event.tool_name);
        break;
      case 'message':
        addMessage(event.msg);
        break;
      case 'error':
        handleError(event.error);
        break;
      // ...
    }
  }
} catch (error) {
  if (error.name === 'AbortError') {
    // 用户主动取消，正常行为
  } else {
    console.error('Stream error:', error);
  }
}

// 4. 清理
useEffect(() => {
  return () => abortController.abort();
}, []);
```

### 心跳保活
SSE 流包含心跳帧（comment 格式 `:...\n`），前端自动忽略。

## 路由和导航

### 路由结构
```typescript
/login                           → 登录页（公开）
/admin                           → Navigate to /admin/chat
/admin/chat/:agentId?/:sessionId?/:memberId? → Admin 聊天页（仅 developer）
/admin/schedule                  → 调度管理
/admin/channel                   → 渠道管理
/admin/credential                → 凭证管理
/admin/mcp                       → MCP Hub 浏览
/admin/mcp/:hubId                → 指定 Hub
/admin/skill                     → Skill Hub 浏览
/admin/skill/:hubId              → 指定 Hub
/admin/knowledge                 → 知识库管理
/admin/knowledge/:kbId           → 知识库详情
/profile                         → 用户资料
/space                           → 终端用户市场（已发布 Agent 列表）
/space/launchpad/:agentId        → 启动确认页（对话确认 / 任务表单）
/space/chat/:agentId/:sessionId? → 用户聊天页
/space/task/:agentId/:sessionId? → 任务结果页
```

**角色守卫:**
- `/admin/*` 与 `/` 使用 `ProtectedRoute roles={['developer']}`
- `/space/*` 使用 `ProtectedRoute roles={['end_user', 'developer']}`
- 角色不匹配时重定向到角色主页（developer → `/admin/chat`，end_user → `/space`）

### 导航模式

**程序式导航:**
```typescript
import { useNavigate } from 'react-router-dom';

const navigate = useNavigate();

// 导航到会话
navigate(`/admin/chat/${agentId}/${sessionId}`);

// Space 空间导航
navigate(`/space/launchpad/${agentId}`);

// 替换历史
navigate('/admin/chat', { replace: true });

// 返回
navigate(-1);
```

**参数获取:**
```typescript
import { useParams, useSearchParams } from 'react-router-dom';

const { agentId, sessionId } = useParams<{ agentId: string; sessionId: string }>();
const [searchParams] = useSearchParams();
const filter = searchParams.get('filter');
```

## 错误边界

### RouteError 组件
路由级别的错误边界，捕获页面崩溃：

```typescript
// App.tsx
const router = createBrowserRouter([
  {
    element: <AppLayout />,
    errorElement: <RouteError />,  // 顶层错误边界
    children: [
      {
        errorElement: <RouteError />,  // 内容区错误边界
        children: [
          { path: '/admin/chat/:agentId?/:sessionId?', element: <ChatPage /> },
          // ...
        ],
      },
    ],
  },
]);
```

崩溃后 AppLayout（导航栏）仍可用，用户可导航到其他页面。

## 引导和新手教程 (Onborda)

### Tour 系统
使用 `onborda` 库提供交互式引导：

```typescript
// buildChatTour.ts
export function buildChatTour(t: TFunction) {
  return [
    {
      icon: <MessageSquare />,
      title: t('tour.chat.step1.title'),
      content: t('tour.chat.step1.content'),
      selector: '#chat-input',
      side: 'top',
    },
    // ...
  ];
}

// App.tsx
<Onborda steps={tours} cardComponent={TourCard}>
  {children}
</Onborda>
```

### 触发方式
- 首次访问自动触发
- 或通过 UI 按钮手动触发

## 性能优化

### 懒加载（按需）
当前未使用 React.lazy，所有页面组件都是同步导入。

### 虚拟滚动
消息列表可能需要虚拟滚动优化（长会话历史）。

### useMemo/useCallback
在 ChatViewport 等复杂组件中使用 `useMemo` 缓存计算结果，`useCallback` 缓存事件处理器。

## 样式系统

### Tailwind 工具类
```typescript
// 使用 cn 工具函数合并类名
import { cn } from '@/lib/utils';

<div className={cn(
  "rounded-lg p-4",
  isActive && "bg-blue-500 text-white",
  isDisabled && "opacity-50 cursor-not-allowed"
)}>
```

### CSS Variables (主题)
主题通过 CSS 变量定义，支持亮色/暗色模式：

```css
:root {
  --background: 0 0% 100%;
  --foreground: 222.2 84% 4.9%;
  --primary: 222.2 47.4% 11.2%;
  /* ... */
}

.dark {
  --background: 222.2 84% 4.9%;
  --foreground: 210 40% 98%;
  /* ... */
}
```

### shadcn/ui 组件
不修改 `components/ui/` 下的文件，这些是生成的基础组件。自定义组件放在其他目录。
