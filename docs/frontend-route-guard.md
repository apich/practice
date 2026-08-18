# 前端路由守卫说明

## 概述

前端有两个守卫组件，分别负责页面级和操作级的权限控制。两者都基于角色（role）判断，守卫方式不同。

## 守卫组件对照

| 组件 | 文件 | 守卫方式 | 守卫粒度 | 用途 |
|---|---|---|---|---|
| `ProtectedRoute` | `frontend/src/components/auth/ProtectedRoute.tsx` | 不通过 → 跳转页面 | 页面级 | 拦截整个页面访问 |
| `RoleGuard` | `frontend/src/components/auth/RoleGuard.tsx` | 不通过 → 隐藏组件 | 操作级 | 控制按钮/组件显隐 |

## ProtectedRoute — 页面级守卫

### 守卫方式

不通过时**跳转到其他页面**，用户完全看不到被保护的页面。

### 守卫流程

```
用户访问某页面（如 /admin/chat）
  │
  ├─ React Router 匹配到路由配置
  │   element: <ProtectedRoute roles={['developer']}>
  │
  ├─ ProtectedRoute 执行检查
  │   ├─ loading 中 → 不渲染，等待
  │   ├─ 未登录 → <Navigate to="/login" />，跳转登录页
  │   ├─ 角色不匹配 → <Navigate to="/space" />，跳转对应首页
  │   └─ 通过 → 渲染子页面 <Outlet />
  │
  └─ 用户看到目标页面或被跳转到其他页面
```

### 使用方式

在路由配置文件（App.tsx）中使用：

```tsx
// developer 专属页面
{
  element: <ProtectedRoute roles={['developer']} />,
  children: [
    { path: '/admin/chat', element: <ChatPage /> },
    { path: '/admin/schedule', element: <SchedulePage /> },
    // ...
  ],
}

// end_user + developer 共享页面
{
  element: <ProtectedRoute roles={['end_user', 'developer']} />,
  children: [
    { path: '/space', element: <SpacePage /> },
    // ...
  ],
}
```

## RoleGuard — 操作级守卫

### 守卫方式

不通过时**隐藏子组件**，不跳转，页面本身正常显示。

### 守卫流程

```
页面渲染到某个组件
  │
  ├─ RoleGuard 执行检查
  │   ├─ 角色匹配 → 渲染子组件（如 <DeleteButton />）
  │   └─ 角色不匹配 → 渲染 fallback（默认 null，即隐藏）
  │
  └─ 页面其他内容不受影响
```

### 使用方式

在页面组件中使用：

```tsx
// 只有 developer 能看到这个按钮
<RoleGuard roles={['developer']}>
  <DeleteButton />
</RoleGuard>

// end_user 看到替代内容，developer 看到真正的按钮
<RoleGuard roles={['developer']} fallback={<span>无权限</span>}>
  <AdminPanel />
</RoleGuard>
```

## 两者配合使用

```
┌─────────────────────────────────────────────┐
│  ProtectedRoute（页面级）                     │
│  拦截：未登录 / 角色不对 → 整个页面看不到       │
│                                             │
│  ┌─────────────────────────────────────┐    │
│  │  页面内容                            │    │
│  │                                     │    │
│  │  普通内容（所有角色可见）              │    │
│  │                                     │    │
│  │  ┌─────────────────────────────┐    │    │
│  │  │  RoleGuard（操作级）          │    │    │
│  │  │  developer 专属按钮          │    │    │
│  │  │  end_user 看不到             │    │    │
│  │  └─────────────────────────────┘    │    │
│  └─────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
```
