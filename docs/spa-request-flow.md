# SPA 请求流程说明

## 概述

前端采用 React 单页应用（SPA）架构，服务器只返回一个固定的 HTML 文件，页面内容由 React 在浏览器中动态渲染。

## 完整流程

```
浏览器访问 http://localhost:5173/
  │
  ├─ ① Vite 开发服务器返回固定的 index.html
  │     内容大致是：
  │     <html>
  │       <body>
  │         <div id="root"></div>        ← React 挂载点
  │         <script type="module" src="/src/main.tsx"></script>
  │       </body>
  │     </html>
  │
  ├─ ② 浏览器加载并执行 main.tsx
  │     React 挂载 <App /> 到 #root
  │
  └─ ③ React Router 读取当前 URL（/）
      匹配路由配置 → 发现需要 ProtectedRoute 守卫
      根据登录状态和角色 → 页内跳转到 /login、/admin/chat 或 /space
      全程不刷新页面（SPA 行为）
```

## 关键点

| 阶段 | 谁在工作 | 发生了什么 |
|---|---|---|
| 第一次请求 | Vite 开发服务器 | 返回固定的 index.html，跟访问哪个路径无关 |
| 之后 | 浏览器里的 React | 接管路由，根据 URL 渲染对应页面组件 |

## SPA 核心特征

- **一次加载**：服务器只返回一个 index.html，不按路径返回不同页面
- **页内跳转**：路由切换由 React Router 在浏览器端完成，不触发整页刷新
- **路径无关**：无论访问 `/`、`/admin/chat` 还是 `/login`，服务器返回的都是同一个 HTML 文件
- **动态渲染**：页面内容由 JavaScript 根据当前 URL 动态生成

## 路由跳转流程示例

```
用户访问 http://localhost:5173/admin/chat
  │
  ├─ 服务器：返回 index.html（和访问 / 时完全一样）
  ├─ 浏览器：加载 JS，React 启动
  └─ React Router：URL 是 /admin/chat
      → 匹配到 ProtectedRoute（roles: ['developer']）
      → 检查登录状态和角色
      → 有权限：渲染 ChatPage
      → 无权限：跳转到 /login 或 /space
```
