# JSX 到 React 渲染的完整流程

## 概述

JSX 不是浏览器能识别的语法，需要 Vite 在构建时转译成 JavaScript 函数调用，再由 React 框架在运行时处理。

## 完整流程

```
① 编写 JSX
   <AuthContext.Provider value={value}>{children}</AuthContext.Provider>

          │
          ▼  Vite 转译（构建时）

② 变成 React.createElement 调用
   React.createElement(AuthContext.Provider, { value: value }, children)

          │
          ▼  执行（运行时）

③ 返回一个普通的 JS 对象（虚拟 DOM 节点）
   {
     $$typeof: Symbol(react.element),
     type: AuthContext.Provider,
     props: { value: value, children: children },
     key: null,
     ref: null,
   }

          │
          ▼  交给 React 框架

④ React 根据 type 做分发
   ├─ type 是字符串（"div"） → 创建真实 DOM 节点
   ├─ type 是函数（组件）    → 执行函数，拿到返回值继续处理
   └─ type 是 Provider      → 执行特殊逻辑：存 value，渲染 children

          │
          ▼

⑤ Provider 的特殊逻辑
   ├─ 把 value 存进 AuthContext 这个"频道"
   ├─ 渲染 children（递归处理子节点）
   └─ 子组件调用 useContext(AuthContext) 时，React 从"频道"里取 value 返回
```

## 各阶段详解

### ① 编写 JSX

开发者写的类 HTML 语法：

```tsx
<AuthContext.Provider value={value}>
    {children}
</AuthContext.Provider>
```

### ② Vite 转译（构建时）

Vite 使用 Babel/SWC 把 JSX 转成 `React.createElement` 调用：

```js
React.createElement(
    AuthContext.Provider,  // 类型：Provider 组件
    { value: value },      // 属性：传入的 value
    children               // 子元素：props 里的 children
);
```

### ③ React.createElement 返回虚拟 DOM 对象

`React.createElement` 不操作真实 DOM，只返回一个普通的 JS 对象：

```js
{
    $$typeof: Symbol(react.element),  // 标识：表明这是 React 元素
    type: AuthContext.Provider,        // 类型：指向 Provider
    props: {
        value: value,                  // 传入的数据
        children: children             // 子组件
    },
    key: null,
    ref: null,
}
```

### ④ React 框架处理（运行时）

React 收到这个对象后，根据 `type` 字段做分发处理：

| type 类型 | 处理方式 | 例子 |
|---|---|---|
| 字符串 | 创建真实 DOM 节点 | `"div"` → `<div>` |
| 函数组件 | 执行函数，递归处理返回值 | `MyComponent()` |
| 类组件 | 实例化类，调用 render() | `new MyClass().render()` |
| Provider | 存值 + 渲染 children | `AuthContext.Provider` |

### ⑤ Provider 的特殊逻辑

Provider 是 React 内置的特殊组件，不渲染任何 DOM 元素：

```
React 识别出 type 是 AuthContext.Provider
  │
  ├─ 把 value 存进 AuthContext 内部的存储
  │
  ├─ 渲染 children（递归进入下一轮处理）
  │
  └─ 后续子组件调用 useContext(AuthContext) 时
     React 从存储中取出 value 返回
```

## 实际例子：认证状态共享

```tsx
// AuthProvider.tsx
const value = { user, loading, isAuthenticated };
<AuthContext.Provider value={value}>{children}</AuthContext.Provider>

// 任何子组件.tsx
const { user, isAuthenticated } = useAuth();  // 通过 useContext 获取 value
```

数据流：
```
AuthProvider 创建 value
    │
    ▼
AuthContext.Provider 存储 value（React 内部机制）
    │
    ▼
子组件调用 useContext(AuthContext)
    │
    ▼
React 从 AuthContext 的存储中取出 value 返回
```
