# App.tsx JSX 转译示例

## 概述

以 App.tsx 的 return 语句为例，展示 JSX 经过 Vite 转译和 React 处理后的完整形态。

## 第一阶段：编写 JSX

开发者写的类 HTML 语法：

```tsx
return (
    <AuthProvider>
        <OnbordaProvider>
            <Onborda
                steps={tours}
                cardComponent={TourCard}
                shadowOpacity="0.6"
                cardTransition={{ type: 'spring', duration: 0.4 }}
            >
                <UploadProvider>
                    <RouterProvider router={router} />
                </UploadProvider>
                <Toaster richColors position="top-right" />
            </Onborda>
        </OnbordaProvider>
    </AuthProvider>
);
```

## 第二阶段：Vite 转译成 React.createElement（构建时）

Vite 将每一层 JSX 转换成 `React.createElement(type, props, ...children)` 调用：

```js
React.createElement(
    AuthProvider,
    null,
    React.createElement(
        OnbordaProvider,
        null,
        React.createElement(
            Onborda,
            {
                steps: tours,
                cardComponent: TourCard,
                shadowOpacity: "0.6",
                cardTransition: { type: 'spring', duration: 0.4 }
            },
            React.createElement(
                UploadProvider,
                null,
                React.createElement(RouterProvider, { router: router })
            ),
            React.createElement(Toaster, { richColors: true, position: "top-right" })
        )
    )
);
```

### 转译规则

| JSX 写法 | 转译结果 |
|---|---|
| `<AuthProvider>` | `React.createElement(AuthProvider, ...)` |
| `<Onborda steps={tours}>` | `React.createElement(Onborda, { steps: tours }, ...)` |
| `<RouterProvider router={router} />` | `React.createElement(RouterProvider, { router: router })` |

## 第三阶段：执行后返回虚拟 DOM 对象（运行时）

`React.createElement` 执行后返回一棵嵌套的 JS 对象树（虚拟 DOM）：

```js
{
  $$typeof: Symbol(react.element),
  type: AuthProvider,
  props: {
    children: {
      $$typeof: Symbol(react.element),
      type: OnbordaProvider,
      props: {
        children: {
          $$typeof: Symbol(react.element),
          type: Onborda,
          props: {
            steps: tours,
            cardComponent: TourCard,
            shadowOpacity: "0.6",
            cardTransition: { type: "spring", duration: 0.4 },
            children: [
              {
                $$typeof: Symbol(react.element),
                type: UploadProvider,
                props: {
                  children: {
                    $$typeof: Symbol(react.element),
                    type: RouterProvider,
                    props: { router: router },
                    key: null,
                    ref: null
                  }
                },
                key: null,
                ref: null
              },
              {
                $$typeof: Symbol(react.element),
                type: Toaster,
                props: { richColors: true, position: "top-right" },
                key: null,
                ref: null
              }
            ]
          },
          key: null,
          ref: null
        }
      },
      key: null,
      ref: null
    }
  },
  key: null,
  ref: null
}
```

### 对象结构说明

每个节点的结构相同：

| 字段 | 含义 |
|---|---|
| `$$typeof` | 标识符，固定为 `Symbol(react.element)`，表明这是 React 元素 |
| `type` | 组件类型，可以是函数（AuthProvider）、字符串（"div"）或 Provider |
| `props` | 属性集合，包含传入的参数和 `children` |
| `key` | 列表渲染时的唯一标识，未传则为 null |
| `ref` | DOM 引用，未传则为 null |

### children 的两种形态

```js
// 单个子节点 → children 是对象
props: {
    children: { type: RouterProvider, ... }
}

// 多个子节点 → children 是数组
props: {
    children: [
        { type: UploadProvider, ... },
        { type: Toaster, ... }
    ]
}
```

## 第四阶段：React 递归处理（运行时）

React 拿到这棵对象树后，从根节点开始递归处理：

```
AuthProvider（函数）→ 执行，返回 AuthContext.Provider
  └─ OnbordaProvider（函数）→ 执行，返回子节点
      └─ Onborda（函数）→ 执行，返回子节点
          ├─ UploadProvider（函数）→ 执行，返回子节点
          │   └─ RouterProvider → 处理路由，渲染页面
          └─ Toaster（函数）→ 执行，渲染通知组件
```

每层都走同一条路：读 type → 分发处理 → 处理 children → 直到底层 DOM。

## 第五阶段：AuthProvider 的 return 详解

### JSX

```tsx
return (
    <AuthContext.Provider value={value}>
        {children}
    </AuthContext.Provider>
);
```

### Vite 转译

```js
return React.createElement(AuthContext.Provider, { value: value }, children);
```

### React.createElement 返回值

```js
{
  $$typeof: Symbol(react.element),
  type: AuthContext.Provider,
  props: {
    value: value,        // { user, loading, isAuthenticated, login, logout }
    children: children   // ← 就是 OnbordaProvider 那棵对象树
  },
  key: null,
  ref: null
}
```

其中 `children` 的值就是：

```js
{
  $$typeof: Symbol(react.element),
  type: OnbordaProvider,
  props: {
    children: {
      $$typeof: Symbol(react.element),
      type: Onborda,
      props: {
        steps: tours,
        cardComponent: TourCard,
        shadowOpacity: "0.6",
        cardTransition: { type: "spring", duration: 0.4 },
        children: [
          { type: UploadProvider, props: { children: { type: RouterProvider, ... } } },
          { type: Toaster, props: { richColors: true, position: "top-right" } }
        ]
      }
    }
  }
}
```

### 本质

AuthProvider 的 return 就是用 `AuthContext.Provider` 包了一层，把 `value` 广播出去，`children` 原样透传。

## 第六阶段：Provider 与普通组件的处理区别

### 普通组件 vs Provider

```js
// 普通函数组件 → React 会执行这个函数
type: AuthProvider        → React 执行 AuthProvider(props)

// Provider → React 不执行，走内部特殊逻辑
type: AuthContext.Provider → React 内部：存 value，渲染 children
```

### React 处理 AuthContext.Provider 的内部逻辑

```
React 拿到 { type: AuthContext.Provider, props: { value, children } }
  │
  ├─ 识别出 type 是 Context.Provider（通过内部标记判断）
  │
  ├─ 不执行任何函数
  │
  ├─ 把 value 存进 AuthContext 的内部存储
  │   后续子组件调用 useContext(AuthContext) 时从这里取
  │
  └─ 渲染 props.children（继续递归处理 OnbordaProvider）
```

### 类比

- 普通函数组件 = 叫一个厨师做饭（执行函数，拿到菜）
- Provider = 往冰箱里放食材（存 value，不执行任何东西），别人可以从冰箱里拿（useContext）

Provider 不是被执行的函数，它是 React 内部的一个"存值 + 透传 children"的特殊机制。

### Provider 渲染 children 后的递归

```
Provider 存完 value 后，渲染 props.children
  │
  ▼
React 拿到 { type: OnbordaProvider, props: { children: {...} } }
  │
  ├─ 识别出 type 是 OnbordaProvider（普通函数组件）
  │
  ├─ 执行 OnbordaProvider(props)
  │
  ├─ OnbordaProvider 返回新的虚拟 DOM 对象
  │
  └─ React 继续递归处理返回值...
```

每一层都是同一个逻辑：拿到对象 → 看 type → 是函数就执行 → 对返回值继续递归。
