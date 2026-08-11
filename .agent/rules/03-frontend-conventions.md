# 前端开发规范

## 技术栈

- **框架**: React 19 + TypeScript 6.0
- **构建工具**: Vite 8
- **路由**: React Router DOM 7
- **UI 组件**: shadcn/ui (基于 Radix UI)
- **样式**: TailwindCSS 4.3 + CSS Variables
- **图标**: Lucide React
- **动画**: Framer Motion
- **国际化**: i18next + react-i18next
- **表单**: React Hook Form (如需要)
- **HTTP**: 自定义 fetch 封装

## 项目结构

```
src/
├── api/                    # API 客户端层
│   ├── client.ts          # HTTP 客户端封装
│   ├── health.ts          # 健康检查 API
│   ├── skill.ts           # Skill API
│   └── index.ts           # 导出所有 API
├── components/
│   ├── ui/                # shadcn/ui 组件（不修改）
│   ├── badge/             # 徽章组件
│   ├── error/             # 错误组件
│   ├── hub/               # Hub 相关组件
│   ├── layout/            # 布局组件
│   ├── select/            # 选择器组件
│   └── tour/              # 引导组件
├── context/               # React Context
│   └── UploadContext.tsx
├── hooks/                 # 自定义 Hooks
├── i18n/                  # 国际化
│   ├── index.ts
│   ├── useI18n.ts
│   ├── locales/
│   │   ├── en.json
│   │   └── zh.json
├── lib/                   # 工具库
│   └── utils.ts
├── pages/                 # 页面组件
│   ├── channel/           # 渠道管理
│   ├── chat/              # 聊天页面
│   ├── credential/        # 凭证管理
│   ├── knowledge/         # 知识库管理
│   ├── mcp/               # MCP Hub
│   ├── schedule/          # 调度管理
│   ├── setup/             # 初始化设置
│   └── skill/             # Skill Hub
├── utils/                 # 工具函数
├── App.tsx                # 应用入口
├── main.tsx               # React 渲染入口
└── index.css              # 全局样式
```

## 代码风格

### ESLint 配置
项目使用 TypeScript ESLint + React Hooks + Import Order:

```javascript
// eslint.config.js
rules: {
  'import-x/order': ['error', {
    groups: ['builtin', 'external', 'internal', 'index'],
    'newlines-between': 'always',
    alphabetize: { order: 'asc', caseInsensitive: true },
  }],
  'react-hooks/set-state-in-effect': 'off',
}
```

### 导入顺序
```typescript
// 1. React 核心
import { useState, useEffect } from 'react';

// 2. 第三方库（按字母序）
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';

// 3. shadcn/ui 组件
import { Button } from '@/components/ui/button';
import { Dialog } from '@/components/ui/dialog';

// 4. 内部组件
import { ChatViewport } from '@/pages/chat/ChatViewport';

// 5. API 和工具
import { client } from '@/api/client';
import { cn } from '@/lib/utils';

// 6. 类型定义
import type { Agent } from '@/api/types';
```

### 命名规范
- **组件**: PascalCase (`UserProfile.tsx`)
- **文件**: kebab-case (`user-profile.tsx`) 或 PascalCase
- **变量/函数**: camelCase (`getUserId`)
- **常量**: UPPER_SNAKE_CASE (`API_BASE_URL`)
- **类型/接口**: PascalCase (`UserProfile`, `ApiResponse`)

## TypeScript 规范

### 类型定义
```typescript
// ✅ 推荐：接口定义
interface Agent {
  id: string;
  name: string;
  description?: string;  // 可选字段
  tags: string[];
}

// ✅ 类型别名
type AgentStatus = 'active' | 'inactive' | 'archived';

// ✅ 泛型
interface ApiResponse<T> {
  data: T;
  status: number;
  message: string;
}
```

### 组件类型
```typescript
// ✅ 函数组件类型
interface ButtonProps {
  label: string;
  onClick: () => void;
  disabled?: boolean;
}

export function Button({ label, onClick, disabled = false }: ButtonProps) {
  return <button onClick={onClick} disabled={disabled}>{label}</button>;
}

// ✅ 带子组件
interface ContainerProps {
  children: React.ReactNode;
  className?: string;
}

export function Container({ children, className }: ContainerProps) {
  return <div className={className}>{children}</div>;
}
```

### 避免 any
```typescript
// ❌ 避免
function process(data: any) { }

// ✅ 使用具体类型
function process(data: unknown) {
  if (typeof data === 'string') {
    // 类型守卫
  }
}

// ✅ 泛型
function process<T>(data: T): T {
  return data;
}
```

## React 规范

### 函数组件
```typescript
// ✅ 推荐：箭头函数导出
export const UserProfile = ({ userId }: { userId: string }) => {
  const [user, setUser] = useState<User | null>(null);
  
  useEffect(() => {
    fetchUser(userId).then(setUser);
  }, [userId]);
  
  return <div>{user?.name}</div>;
};

// ✅ 也可以：函数声明导出
export function UserProfile({ userId }: { userId: string }) {
  // ...
}
```

### Hooks 规范
```typescript
// ✅ 自定义 Hook
export function useAgent(agentId: string) {
  const [agent, setAgent] = useState<Agent | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  
  useEffect(() => {
    setLoading(true);
    client.get<Agent>(`/api/agents/${agentId}`)
      .then(setAgent)
      .catch(setError)
      .finally(() => setLoading(false));
  }, [agentId]);
  
  return { agent, loading, error };
}
```

### 状态管理
```typescript
// ✅ useState
const [count, setCount] = useState(0);
const [user, setUser] = useState<User | null>(null);

// ✅ useReducer (复杂状态)
type Action = 
  | { type: 'increment' }
  | { type: 'decrement' }
  | { type: 'reset' };

function reducer(state: number, action: Action) {
  switch (action.type) {
    case 'increment': return state + 1;
    case 'decrement': return state - 1;
    case 'reset': return 0;
  }
}

const [count, dispatch] = useReducer(reducer, 0);
```

### Context 使用
```typescript
// ✅ 创建 Context
interface UploadContextValue {
  files: File[];
  addFile: (file: File) => void;
}

const UploadContext = createContext<UploadContextValue | null>(null);

export function UploadProvider({ children }: { children: React.ReactNode }) {
  const [files, setFiles] = useState<File[]>([]);
  
  const addFile = (file: File) => setFiles([...files, file]);
  
  return (
    <UploadContext.Provider value={{ files, addFile }}>
      {children}
    </UploadContext.Provider>
  );
}

// ✅ 使用 Context
export function useUpload() {
  const context = useContext(UploadContext);
  if (!context) {
    throw new Error('useUpload must be used within UploadProvider');
  }
  return context;
}
```

## 样式规范

### TailwindCSS
```typescript
// ✅ 使用 Tailwind utility classes
<div className="flex items-center gap-4 rounded-lg bg-white p-4 shadow-md">
  <span className="text-lg font-semibold">Hello</span>
</div>

// ✅ 条件类名
<div className={cn(
  "rounded-lg p-4",
  isActive && "bg-blue-500 text-white",
  isDisabled && "opacity-50 cursor-not-allowed"
)}>
  Content
</div>

// ✅ 响应式
<div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
  {/* ... */}
</div>
```

### cn 工具函数
```typescript
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs));
}
```

### CSS Variables (主题)
```css
/* index.css */
:root {
  --background: 0 0% 100%;
  --foreground: 222.2 84% 4.9%;
  --primary: 222.2 47.4% 11.2%;
  --primary-foreground: 210 40% 98%;
  /* ... */
}

.dark {
  --background: 222.2 84% 4.9%;
  --foreground: 210 40% 98%;
  /* ... */
}
```

## API 客户端

### client.ts 封装
```typescript
// src/api/client.ts
export const client = {
  get: <T>(path: string, params?: Record<string, string>) => 
    request<T>(path, { method: 'GET', params }),
  
  post: <T>(path: string, body?: unknown) => 
    request<T>(path, { method: 'POST', body }),
  
  patch: <T>(path: string, body?: unknown) => 
    request<T>(path, { method: 'PATCH', body }),
  
  delete: <T>(path: string) => 
    request<T>(path, { method: 'DELETE' }),
  
  stream: (path: string, options?: RequestOptions) => 
    streamRequest(path, options),
};
```

### API 模块
```typescript
// src/api/agent.ts
import { client } from './client';
import type { Agent, CreateAgentRequest } from './types';

export const agentApi = {
  list: () => client.get<Agent[]>('/api/agents'),
  
  get: (id: string) => client.get<Agent>(`/api/agents/${id}`),
  
  create: (data: CreateAgentRequest) => 
    client.post<Agent>('/api/agents', data),
  
  update: (id: string, data: Partial<Agent>) => 
    client.patch<Agent>(`/api/agents/${id}`, data),
  
  delete: (id: string) => 
    client.delete(`/api/agents/${id}`),
};
```

### 错误处理
```typescript
// ✅ 使用 toast 提示
import { toast } from 'sonner';

try {
  const agent = await agentApi.get(agentId);
  setAgent(agent);
} catch (error) {
  if (error instanceof ApiError) {
    toast.error(error.detail);  // 已在 client 中处理
  } else {
    toast.error('Unknown error occurred');
  }
}

// ✅ 静默错误（不显示 toast）
const result = await client.get('/api/agents', undefined, { silent: true });
```

## 路由规范

### React Router v7
```typescript
// App.tsx
import { createBrowserRouter, RouterProvider } from 'react-router-dom';

const router = createBrowserRouter([
  {
    element: <AppLayout />,
    errorElement: <RouteError />,
    children: [
      { path: '/', element: <Navigate to="/chat" replace /> },
      { path: '/chat/:agentId?/:sessionId?', element: <ChatPage /> },
      { path: '/schedule', element: <SchedulePage /> },
      // ...
    ],
  },
]);

function App() {
  return <RouterProvider router={router} />;
}
```

### 导航
```typescript
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';

function Component() {
  const navigate = useNavigate();
  const { agentId } = useParams<{ agentId: string }>();
  const [searchParams] = useSearchParams();
  
  // 编程式导航
  navigate('/chat/agent-123');
  navigate('/chat', { replace: true });
  navigate(-1); // 返回
  
  // 查询参数
  const filter = searchParams.get('filter');
}
```

## 国际化

### i18next 配置
```typescript
// src/i18n/index.ts
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

import en from './locales/en.json';
import zh from './locales/zh.json';

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      zh: { translation: zh },
    },
    fallbackLng: 'en',
    interpolation: {
      escapeValue: false,
    },
  });

export default i18n;
```

### 使用翻译
```typescript
import { useTranslation } from 'react-i18next';

function Component() {
  const { t, i18n } = useTranslation();
  
  return (
    <div>
      <h1>{t('welcome')}</h1>
      <button onClick={() => i18n.changeLanguage('zh')}>
        切换语言
      </button>
    </div>
  );
}
```

### 翻译文件
```json
// locales/en.json
{
  "welcome": "Welcome",
  "chat": {
    "title": "Chat",
    "send": "Send"
  }
}

// locales/zh.json
{
  "welcome": "欢迎",
  "chat": {
    "title": "聊天",
    "send": "发送"
  }
}
```

## 性能优化

### React.memo
```typescript
// ✅ 优化重渲染
export const AgentCard = memo(({ agent }: { agent: Agent }) => {
  return <div>{agent.name}</div>;
});
```

### useMemo / useCallback
```typescript
// ✅ 缓存计算结果
const filteredAgents = useMemo(
  () => agents.filter(a => a.name.includes(search)),
  [agents, search]
);

// ✅ 缓存函数
const handleClick = useCallback(
  () => console.log(agentId),
  [agentId]
);
```

### 懒加载
```typescript
import { lazy, Suspense } from 'react';

const ChatPage = lazy(() => import('./pages/chat'));

function App() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <ChatPage />
    </Suspense>
  );
}
```

## 测试规范

### 组件测试
```typescript
import { render, screen } from '@testing-library/react';
import { UserProfile } from './UserProfile';

test('renders user name', () => {
  render(<UserProfile userId="123" />);
  const element = screen.getByText(/John Doe/i);
  expect(element).toBeInTheDocument();
});
```

## 常见陷阱

### ❌ 避免在渲染中调用异步
```typescript
// ❌ 错误
function Component() {
  const data = await fetch('/api/data');  // 不能在组件中直接 await
  return <div>{data}</div>;
}

// ✅ 正确
function Component() {
  const [data, setData] = useState(null);
  
  useEffect(() => {
    fetch('/api/data').then(setData);
  }, []);
  
  return <div>{data}</div>;
}
```

### ❌ 避免直接修改状态
```typescript
// ❌ 错误
const [items, setItems] = useState([1, 2, 3]);
items.push(4);  // 直接修改

// ✅ 正确
setItems([...items, 4]);  // 创建新数组
```

### ❌ 避免在 useEffect 中遗漏依赖
```typescript
// ❌ 错误
useEffect(() => {
  console.log(userId);
}, []);  // 缺少 userId 依赖

// ✅ 正确
useEffect(() => {
  console.log(userId);
}, [userId]);
```
