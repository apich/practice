# AgentDialog 创建智能体时的 401 错误处理流程

本文档记录前端在创建智能体（AgentDialog）时，后端返回 401 的完整处理链路。

---

## 1. 流程概述

当用户点击"创建智能体"按钮时，如果 JWT 已过期，后端返回 401，前端的处理流程是：

1. `streamRequest` 捕获 401 状态码
2. 调用 `clearAuthAndRedirect` 弹出 toast 提示 + 5秒后跳转登录页
3. 抛出一个 **detail 为空** 的 `ApiError(401, '')`
4. `AgentDialog` catch 到该异常，因为 `detail` 为空，不显示第二个弹窗

**设计意图：401 由 `streamRequest` 统一处理（弹 toast + 跳登录），抛空 detail 避免调用方再弹一次重复的错误提示。**

---

## 2. 完整调用链

### 第 1 步：AgentDialog 触发请求

用户点击创建按钮 → `AgentDialog` 调用：

```typescript
await client.post("/agent/", data, {}, { silent: true });
```

`silent: true` 表示不在 `streamRequest` 中自动弹 toast（由调用方自行处理）。

### 第 2 步：streamRequest 发起请求

[client.ts:121-186](../../../frontend/src/api/client.ts#L121-L186) 中的 `streamRequest`：

```typescript
// 构建请求头，附带 Authorization: Bearer {token}
res = await fetch(url.toString(), {
    method,
    headers: buildHeaders(body !== undefined, options?.skipAuth),
    body: body ? JSON.stringify(body) : undefined,
    signal: combined,
});
```

### 第 3 步：后端返回 401

JWT 过期后，后端中间件校验失败，返回：

```
HTTP/1.1 401 Unauthorized
{"detail": "Token has expired"}
```

### 第 4 步：streamRequest 处理 401

[client.ts:168-182](../../../frontend/src/api/client.ts#L168-L182)：

```typescript
if (!res.ok) {
    // ① 提取后端返回的错误信息
    const detail = await extractErrorDetail(res);  // "Token has expired"
    const error = new ApiError(res.status, detail);

    // ② 判断是否为 401 且非 /auth/ 端点
    if (res.status === 401 && !path.startsWith('/auth/')) {
        // ③ 弹出 toast + 5秒后跳转登录
        clearAuthAndRedirect("登录已过期，请重新登录");
        // ④ 抛出空 detail 的异常，避免调用方重复弹窗
        throw new ApiError(401, '');
    } else if (!silent) {
        toast.error(detail);  // 非 401 错误：弹 toast
    }

    throw error;
}
```

**关键点：** 步骤 ② 中 `extractErrorDetail` 已经提取了后端的错误信息（`"Token has expired"`），但步骤 ④ 故意抛出空 detail 的新 `ApiError`，覆盖了原始错误信息。

### 第 5 步：clearAuthAndRedirect 执行

[client.ts:34-51](../../../frontend/src/api/client.ts#L34-L51)：

```typescript
export function clearAuthAndRedirect(message?: string) {
    // ① 清除本地认证状态
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user_info');

    const msg = message || '登录过期，请重新登录';

    // ② 弹出 toast 提示（第一个弹窗）
    if (window.location.pathname !== '/login') {
        toast.error(msg, { position: 'top-center' });

        // ③ 5秒后跳转登录页
        setTimeout(() => {
            window.location.href = '/login';
        }, 5000);
    }
}
```

**执行效果：**
- 弹出 toast：`"登录已过期，请重新登录"` ← **唯一的弹窗**
- 5秒后跳转 `/login`

### 第 6 步：AgentDialog catch 异常

[AgentDialog.tsx:85-86](../../../frontend/src/components/dialog/AgentDialog.tsx#L85-L86)：

```typescript
catch (e) {
    setErrorMsg(formatApiErrorForAlert(e));  // e = ApiError(401, '')
}
```

### 第 7 步：formatApiErrorForAlert 处理空 detail

[api-error.ts:10-32](../../../frontend/src/lib/api-error.ts#L10-L32)：

```typescript
export function formatApiErrorForAlert(err: unknown): string {
    if (err instanceof ApiError) {
        const { detail } = err;  // detail = ''（空字符串）
        try {
            const parsed = JSON.parse(detail);  // JSON.parse('') → 抛异常
            // ...
        } catch {
            // 走到这里
        }
        return detail;  // 返回 ''
    }
    // ...
}
```

**执行结果：** `formatApiErrorForAlert(ApiError(401, ''))` 返回 `''`。

**最终效果：** `setErrorMsg('')` → 空字符串 → **不弹第二个弹窗**。

---

## 3. 流程图

```
点击创建智能体
    │
    ▼
AgentDialog → client.post("/agent/", data, {silent: true})
    │
    ▼
streamRequest → fetch → 后端返回 401 {"detail": "Token has expired"}
    │
    ├─── clearAuthAndRedirect("登录已过期，请重新登录")
    │       ├─ 清除 localStorage（access_token / refresh_token / user_info）
    │       ├─ toast.error("登录已过期，请重新登录")    ← ✅ 唯一的弹窗
    │       └─ setTimeout 5s → 跳转 /login
    │
    └─── throw ApiError(401, '')                        ← detail 为空
            │
            ▼
        AgentDialog catch (e)
            │
            ├─ formatApiErrorForAlert(ApiError(401, ''))
            │   ├─ err instanceof ApiError → true
            │   ├─ detail = ''
            │   ├─ JSON.parse('') → 异常
            │   └─ return ''
            │
            └─ setErrorMsg('')                          ← ❌ 不弹第二个弹窗
```

---

## 4. 关键设计点

### 4.1 为什么抛空 detail？

[client.ts:176](../../../frontend/src/api/client.ts#L176)：

```typescript
throw new ApiError(401, '');  // 抛空错误，调用方 catch 后显示空字符串，不会弹窗
```

如果抛出带 detail 的异常（`ApiError(401, "Token has expired")`），AgentDialog 的 catch 会弹出第二个错误弹窗，与 toast 重复。抛空 detail 确保 401 的提示由 `clearAuthAndRedirect` **统一处理**。

### 4.2 为什么 /auth/ 端点跳过 401 处理？

[client.ts:174](../../../frontend/src/api/client.ts#L174)：

```typescript
if (res.status === 401 && !path.startsWith('/auth/')) {
```

`/auth/login`、`/auth/refresh` 等端点本身可能返回 401（如密码错误），不应触发全局登出和跳转。这些端点的 401 由调用方自行处理。

### 4.3 silent 参数的作用

`AgentDialog` 传入 `{ silent: true }`，但对 401 处理无影响——401 的 toast 由 `clearAuthAndRedirect` 发出，不走 `if (!silent) toast.error(detail)` 的分支。`silent` 只影响非 401 的错误提示。

---

## 5. 相关代码文件

| 文件 | 作用 |
|---|---|
| [client.ts](../../../frontend/src/api/client.ts) | `streamRequest`、`clearAuthAndRedirect`、`ApiError` 定义 |
| [AgentDialog.tsx](../../../frontend/src/components/dialog/AgentDialog.tsx) | 创建智能体的对话框，catch 后调用 `formatApiErrorForAlert` |
| [api-error.ts](../../../frontend/src/lib/api-error.ts) | `formatApiErrorForAlert` 错误格式化函数 |
