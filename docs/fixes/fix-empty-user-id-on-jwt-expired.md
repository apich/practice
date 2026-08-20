# 修复：JWT 过期后 user_id 写入空字符串

## 目录

- [问题描述](#问题描述)
- [方案一：先跳转再在登录页展示提示](#方案一先跳转再在登录页展示提示)
  - [第 1 步：修复后端 _platform_get_user_id](#第-1-步修复后端-_platform_get_user_id)
  - [第 2 步：修改前端 clearAuthAndRedirect](#第-2-步修改前端-clearauthandredirect)
  - [第 3 步：修改调用处，传入提示信息](#第-3-步修改调用处传入提示信息)
  - [第 4 步：登录页读取并展示提示](#第-4-步登录页读取并展示提示)
- [方案二：先弹窗提示再跳转（推荐）](#方案二先弹窗提示再跳转推荐)
  - [第 1 步：修复后端 _platform_get_user_id](#第-1-步修复后端-_platform_get_user_id-1)
  - [第 2 步：修改前端 clearAuthAndRedirect](#第-2-步修改前端-clearauthandredirect-1)
  - [第 3 步：修改调用处的错误处理逻辑](#第-3-步修改调用处的错误处理逻辑)
- [总结](#总结)

---

## 问题描述

JWT 过期后，`decode_token` 返回 `None`，`request.state.user` 为 `None`。
`_platform_get_user_id` 在开发模式下返回空字符串 `""`，导致 `agents` / `sessions`
表写入 `user_id=""` 的脏数据，且前端不会跳转到登录页。

详见 [jwt-lifecycle-and-expiration-bug.md](../auth/jwt-lifecycle-and-expiration-bug.md)。

---

## 修改步骤

### 第 1 步：修复后端 `_platform_get_user_id`

**文件：** [backend/app/main.py:237-248](../../backend/app/main.py#L237-L248)

**当前代码：**

```python
async def _platform_get_user_id(request: FastAPIRequest) -> str:
    """Extract user ID from JWT (request.state.user) or X-User-ID header."""
    user_payload = getattr(request.state, "user", None)
    if user_payload:
        return user_payload.get("sub", "")
    if settings.is_production:
        raise HTTPException(status_code=401, 
                            detail="Authentication required",
                            headers={"WWW-Authenticate": "Bearer"}
                            )
    return request.headers.get("X-User-ID", "")
```

**替换为：**

```python
async def _platform_get_user_id(request: FastAPIRequest) -> str:
    """Extract user ID from JWT (request.state.user) or X-User-ID header."""
    user_payload = getattr(request.state, "user", None)
    if user_payload:
        return user_payload.get("sub", "")
    if settings.is_production:
        raise HTTPException(status_code=401, 
                            detail="Authentication required",
                            headers={"WWW-Authenticate": "Bearer"}
                            )
    current_user_id = request.headers.get("X-User-ID", "")
    if not current_user_id:
        raise HTTPException(status_code=401, 
                            detail="Authentication required",
                            headers={"WWW-Authenticate": "Bearer"})
    return current_user_id
```

**改动说明：** X-User-ID 为空时 `raise 401`，而非返回空字符串。

---

### 第 2 步：修改前端 `clearAuthAndRedirect`

**文件：** [frontend/src/api/client.ts:34-41](../../frontend/src/api/client.ts#L34-L41)

**当前代码：**

```typescript
export function clearAuthAndRedirect() {
	localStorage.removeItem('access_token');
	localStorage.removeItem('refresh_token');
	localStorage.removeItem('user_info');
	localStorage.removeItem('user_id');
	localStorage.removeItem('username');
	if (window.location.pathname !== '/login') {
		window.location.href = '/login';
	}
}
```

**替换为：**

```typescript
export function clearAuthAndRedirect(message?: string) {
	localStorage.removeItem('access_token');
	localStorage.removeItem('refresh_token');
	localStorage.removeItem('user_info');
	localStorage.removeItem('user_id');
	localStorage.removeItem('username');
	if (message) {
		sessionStorage.setItem('auth_redirect_message', message);
	}
	if (window.location.pathname !== '/login') {
		window.location.href = '/login';
	}
}
```

**改动说明：** 增加可选参数 `message`，跳转前存入 `sessionStorage`，
登录页读取后展示，避免页面刷新导致 toast 消失。

---

### 第 3 步：修改调用处，传入提示信息

**文件：** [frontend/src/api/client.ts:163-166](../../frontend/src/api/client.ts#L163-L166)

**当前代码：**

```typescript
if (res.status === 401 && !path.startsWith('/auth/')) {
    clearAuthAndRedirect();
}
```

**替换为：**

```typescript
if (res.status === 401 && !path.startsWith('/auth/')) {
    clearAuthAndRedirect('登录已过期，请重新登录');
}
```

**改动说明：** 调用时传入用户可见的提示文案。

---

### 第 4 步：登录页读取并展示提示

**文件：** [frontend/src/pages/login/index.tsx](../../frontend/src/pages/login/index.tsx)

**4a. 修改导入（第 2 行）：**

**当前代码：**

```typescript
import { useState } from 'react';
```

**替换为：**

```typescript
import { useEffect, useState } from 'react';
```

**4b. 添加 useEffect（第 28 行 `useState` 之后）：**

**当前代码：**

```typescript
const [errorMsg, setErrorMsg] = useState('');
```

**在这行之后添加：**

```typescript
// 读取跳转时存储的提示信息
useEffect(() => {
    const msg = sessionStorage.getItem('auth_redirect_message');
    if (msg) {
        setErrorMsg(msg);
        sessionStorage.removeItem('auth_redirect_message');
    }
}, []);
```

**改动说明：** 组件挂载时检查 `sessionStorage`，如果有跳转提示则展示并清除。

---

## 方案二：先弹窗提示再跳转（推荐）

方案一需要在登录页添加 `useEffect` 读取 `sessionStorage`，改动较多。
方案二利用 `sonner` 的 `position` 参数，让过期提示在窗口中间上方弹出，
用户看到提示后再跳转到登录页，体验更好。

### 第 1 步：修复后端 `_platform_get_user_id`

与方案一相同，见 [第 1 步](#第-1-步修复后端-_platform_get_user_id)。

### 第 2 步：修改前端 `clearAuthAndRedirect`

**文件：** [frontend/src/api/client.ts:34-41](../../frontend/src/api/client.ts#L34-L41)

**当前代码：**

```typescript
export function clearAuthAndRedirect() {
	localStorage.removeItem('access_token');
	localStorage.removeItem('refresh_token');
	localStorage.removeItem('user_info');
	localStorage.removeItem('user_id');
	localStorage.removeItem('username');
	if (window.location.pathname !== '/login') {
		window.location.href = '/login';
	}
}
```

**替换为：**

```typescript
export function clearAuthAndRedirect(message?: string) {
	localStorage.removeItem('access_token');
	localStorage.removeItem('refresh_token');
	localStorage.removeItem('user_info');
	localStorage.removeItem('user_id');
	localStorage.removeItem('username');

	const msg = message || '登录已过期，请重新登录';

	if (window.location.pathname !== '/login') {
		toast.error(msg, { position: 'top-center' });  // 窗口中间上方弹出
		setTimeout(() => {
			window.location.href = '/login';  // 1.5秒后跳转
		}, 1500);
	}
}
```

**改动说明：**
- 增加可选参数 `message`，默认值 `'登录已过期，请重新登录'`
- 先用 `toast.error(msg, { position: 'top-center' })` 在窗口中间上方弹出提示
- `setTimeout` 延迟 1.5 秒后跳转，用户有时间看到提示
- 其他 toast（如 403/500 错误）仍在右上角显示，互不影响

### 第 3 步：修改调用处的错误处理逻辑

**文件：** [frontend/src/api/client.ts:158-170](../../frontend/src/api/client.ts#L158-L170)

**当前代码：**

```typescript
if (!res.ok) {
    const detail = await extractErrorDetail(res);
    const error = new ApiError(res.status, detail);

    // 401 → token expired or invalid. Clear auth state and redirect to login.
    // Skip for /auth/ endpoints (login/refresh) so the caller can handle it.
    if (res.status === 401 && !path.startsWith('/auth/')) {
        clearAuthAndRedirect();
    }

    if (!silent) toast.error(detail);
    throw error;
}
```

**替换为：**

```typescript
if (!res.ok) {
    const detail = await extractErrorDetail(res);
    const error = new ApiError(res.status, detail);

    // 401 → token expired or invalid. Clear auth state and redirect to login.
    // Skip for /auth/ endpoints (login/refresh) so the caller can handle it.
    if (res.status === 401 && !path.startsWith('/auth/')) {
        clearAuthAndRedirect("登录已过期，请重新登录");
    } else if (!silent) {
        toast.error(detail);  // 非 401 的错误仍然弹 toast
    }

    throw error;
}
```

**改动说明：**
- 401 → 由 `clearAuthAndRedirect` 弹出过期提示，不重复弹 toast
- 403 / 500 / 其他 → 正常弹 toast 提示错误信息
- 避免 401 时同时弹两个 toast（过期提示 + 错误详情）

---

## 补充修复：401 时出现两个错误弹窗

### 问题现象

方案二实施后，401 时出现两个错误提示：
1. **窗口中间**："登录已过期，请重新登录" → 来自 `clearAuthAndRedirect` 的 `toast.error`
2. **对话框内**："Authentication required" → 来自 `throw error` 被调用方 `catch` 捕获后显示

### 原因分析

[client.ts](../../frontend/src/api/client.ts) 中 `clearAuthAndRedirect` 执行后，代码继续走到 `throw error`：

```typescript
if (res.status === 401 && !path.startsWith('/auth/')) {
    clearAuthAndRedirect("登录已过期，请重新登录");  // ← 弹窗 + 1.5秒后跳转
}
// ... 其他逻辑 ...
throw error;  // ← 错误继续抛出
```

调用方（如 [AgentDialog.tsx:85-86](../../frontend/src/components/dialog/AgentDialog.tsx#L85-L86)）的 `catch` 捕获了这个错误：

```typescript
try {
    await create({ ... }, { silent: true });
} catch (e) {
    setErrorMsg(formatApiErrorForAlert(e));  // ← 把 "Authentication required" 显示到对话框内
}
```

所以用户同时看到了两个错误提示。

### 修复方法

401 时 `clearAuthAndRedirect` 已经弹窗提示 + 1.5 秒后跳转登录页，不需要再 `throw error`。

**文件：** [frontend/src/api/client.ts:158-170](../../frontend/src/api/client.ts#L158-L170)

**当前代码：**

```typescript
if (res.status === 401 && !path.startsWith('/auth/')) {
    clearAuthAndRedirect("登录已过期，请重新登录");
} else if (!silent) {
    toast.error(detail);
}

throw error;
```

**替换为：**

```typescript
if (res.status === 401 && !path.startsWith('/auth/')) {
    clearAuthAndRedirect("登录已过期，请重新登录");
    return;  // 页面即将跳转，不抛错误，避免调用方重复显示
} else if (!silent) {
    toast.error(detail);
}

throw error;
```

**改动说明：** 401 时 `return` 直接返回，调用方不会进入 `catch`，只显示一个提示。

---

## 总结

### 方案一（先跳转，登录页展示提示）

| 步骤 | 文件 | 改动 |
|---|---|---|
| 1 | [main.py:237-248](../../backend/app/main.py#L237-L248) | X-User-ID 为空时 `raise 401` |
| 2 | [client.ts:34-41](../../frontend/src/api/client.ts#L34-L41) | `clearAuthAndRedirect` 增加 `message` 参数，存入 sessionStorage |
| 3 | [client.ts:163-166](../../frontend/src/api/client.ts#L163-L166) | 调用时传入 `'登录已过期，请重新登录'` |
| 4 | [login/index.tsx](../../frontend/src/pages/login/index.tsx) | 组件挂载时读取 sessionStorage 并展示提示 |

### 方案二（先弹窗提示，再跳转）— 推荐

| 步骤 | 文件 | 改动 |
|---|---|---|
| 1 | [main.py:237-248](../../backend/app/main.py#L237-L248) | X-User-ID 为空时 `raise 401` |
| 2 | [client.ts:34-41](../../frontend/src/api/client.ts#L34-L41) | `clearAuthAndRedirect` 用 `toast.error(msg, { position: 'top-center' })` 弹窗，1.5 秒后跳转 |
| 3 | [client.ts:158-170](../../frontend/src/api/client.ts#L158-L170) | 401 由 `clearAuthAndRedirect` 弹窗；其他错误走 `toast.error(detail)` |
