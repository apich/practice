# sessions 与 messages 表 CRUD 流程

`sessions` 表和 `messages` 表是 agentscope 框架中最核心的两张表，分别存储**会话元数据**和**聊天消息**。
两者的写入时机、触发路径、更新策略完全不同。

---

## 一、表结构概览

### sessions 表（`SessionRow`）

> 源码：`agentscope/app/storage/_sql/_tables.py:136`

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | String(255) PK | 会话 ID |
| `created_at` | DateTime | 创建时间 |
| `updated_at` | DateTime | 更新时间 |
| `user_id` | String(255) | 所属用户 |
| `agent_id` | String(255) | 关联智能体 |
| `source` | String(16) | 来源（user / schedule / channel） |
| `source_schedule_id` | String(255) nullable | 来源定时任务 ID |
| `team_id` | String(255) nullable | 所属团队 ID |
| `payload` | JSON | 其余字段（config、state 等） |

### messages 表（`MessageRow`）

> 源码：`agentscope/app/storage/_sql/_tables.py:338`

| 列 | 类型 | 说明 |
|---|---|---|
| `session_id` | String(255) PK | 会话 ID（联合主键） |
| `msg_id` | String(255) PK | 消息 ID（联合主键） |
| `created_at` | DateTime | 创建时间 |
| `payload` | JSON | 完整消息内容（role、content、events 等） |

> **设计差异**：`sessions` 使用 `_JsonRecordMixin` 模式（索引字段提升为独立列 + payload JSON 存剩余字段）；
> `messages` 跳过了该模式，使用 `(session_id, msg_id)` 联合主键 + 单一 payload JSON，因为消息是会话的附属事件而非独立记录。

---

## 二、sessions 表操作流程

### 2.1 创建会话（INSERT）

```
用户点击"新建对话"
  → 前端 POST /sessions
    → _session.py: create_session()
      → storage.upsert_session()
        → _write_row(SessionRow, record)
          → _upsert_stmt() 生成原子 UPSERT
            → INSERT INTO sessions ...
          → sess.execute() + sess.commit()
```

> 路由入口：`agentscope/app/_router/_session.py:287`
> 存储方法：`agentscope/app/storage/_sql/_storage.py:1044`

**代码路径**：

```python
# _session.py:293 — 路由层
async def create_session(body: CreateSessionRequest, user_id, storage, ...):
    session_record = await storage.upsert_session(
        user_id=user_id,
        agent_id=body.agent_id,
        config=SessionConfig(...),
    )
    return CreateSessionResponse(session_id=session_record.id)
```

```python
# _storage.py:1044 — 存储层
async def upsert_session(self, user_id, agent_id, config, ...):
    record = SessionRecord(
        user_id=user_id,
        agent_id=agent_id,
        config=config,
        source=source,
        ...
    )
    await self._write_row(SessionRow, record, preserve_created_at=False)
    return record
```

> **注意**：`upsert_session` 是语义上的"创建或恢复"——如果传入的 `session_id` 已存在则更新，否则创建新记录。
> 但从路由层的调用来看，`create_session` 不传 `session_id`，所以总是 INSERT 新行。

### 2.2 更新会话状态（UPDATE）

每次 `chat_service.run()` 执行完毕（agent 回复成功、失败、或被打断），`finally` 块自动更新 session 的 state：

> 存储方法：`agentscope/app/storage/_sql/_storage.py:1108`

```python
# _storage.py:1108
async def update_session_state(self, user_id, agent_id, session_id, state):
    async with self._session() as sess:
        row = await sess.get(SessionRow, session_id)       # 读取已有记录
        record = _to_record(row, SessionRecord)
        record.state = state                                # 更新 state
        record.updated_at = _utcnow()                       # 更新时间戳
        new_row = _from_record(SessionRow, record)
        row.payload = new_row.payload                       # 只改 payload 列
        row.updated_at = new_row.updated_at                 # 只改 updated_at 列
        await sess.commit()
```

**触发时机**：

```python
# _chat.py:962 — finally 块，每次 run() 结束必执行
finally:
    async def _persist():
        if reply_msg is not None:
            await self._storage.upsert_message(...)         # 存消息
        await self._storage.update_session_state(...)       # 更新 session
    await asyncio.shield(asyncio.create_task(_persist()))
```

### 2.3 删除会话（DELETE）

```
用户删除会话
  → 前端 DELETE /sessions/{session_id}
    → _session.py: delete_session()
      → SessionService.delete_session()
        → storage.delete_session()
          → 级联删除：先删 messages，再删 session
```

> 路由入口：`agentscope/app/_router/_session.py:366`

```python
# _storage.py:408 — 级联删除实现
async def _delete_session_impl(self, sess, user_id, agent_id, session_id):
    # 1. 如果 session 是团队 leader，先解散团队
    # 2. 删除 session 关联的所有消息
    await sess.execute(delete(MessageRow).where(MessageRow.session_id == session_id))
    # 3. 删除 session 本身
    await sess.execute(delete(SessionRow).where(SessionRow.id == session_id, ...))
```

### 2.4 查询会话

| 方法 | 路径 | 说明 |
|---|---|---|
| `get_session` | `GET /sessions/{sid}` | 按 ID 获取单个会话 |
| `list_sessions` | `GET /sessions/` | 列出用户某 agent 下所有会话 |
| `get_session_by_agent` | 内部方法 | 按 (user_id, agent_id) 查最近会话 |
| `get_session_by_schedule` | 内部方法 | 按 (user_id, schedule_id) 查最近会话 |

---

## 三、messages 表操作流程

### 3.1 写入消息（INSERT / UPSERT）

每条消息的写入发生在两个时机：

**时机 A — 用户发消息时**：`_chat.py:376`，将用户输入的消息存入 messages 表

**时机 B — agent 回复结束时**：`_chat.py:970`，将 agent 的回复消息存入 messages 表

> 存储方法：`agentscope/app/storage/_sql/_storage.py:1319`

```python
# _storage.py:1319
async def upsert_message(self, user_id, session_id, msg):
    now = _utcnow()
    payload = msg.model_dump(mode="json")              # 完整序列化消息
    values = {
        "session_id": session_id,
        "msg_id": msg.id,
        "created_at": now,
        "payload": payload,
    }
    async with self._session() as sess:
        await sess.execute(
            self._upsert_stmt(
                MessageRow,
                values,
                ["session_id", "msg_id"],              # 联合主键作为冲突目标
                ("payload",),                          # 冲突时只更新 payload
            ),
        )
        await sess.commit()
```

> **upsert 语义**：`(session_id, msg_id)` 相同 → 替换 payload（agent 流式回复过程中会多次 upsert 同一条消息，
> 每次追加新的 event 到 payload 中，直到回复完成）。不同 msg_id → 插入新行。

### 3.2 查询消息

| 方法 | 说明 |
|---|---|
| `get_message(user_id, session_id, msg_id)` | 按联合主键获取单条消息 |
| `list_messages(user_id, session_id, limit)` | 按 session 列出最近 N 条消息 |

> 源码：`_storage.py:1357`（get）、`_storage.py:1390`（list）

### 3.3 删除消息

messages 表没有独立的删除接口。消息只在删除 session 时被**级联删除**：

```python
await sess.execute(delete(MessageRow).where(MessageRow.session_id == session_id))
```

---

## 四、一次完整对话的写入时序

```
用户发起对话
  │
  ├─ 1. POST /sessions          ← sessions 表 INSERT 一条（仅首次）
  │
  ├─ 2. POST /chat              ← 用户发消息
  │     │
  │     ├─ upsert_message()     ← messages 表 INSERT 用户消息
  │     │
  │     ├─ agent 运行中...
  │     │   ├─ upsert_message() ← messages 表 UPSERT（流式追加回复，可能多次）
  │     │   └─ ...
  │     │
  │     └─ finally:
  │         ├─ upsert_message()       ← messages 表 UPSERT 最终回复
  │         └─ update_session_state() ← sessions 表 UPDATE state + updated_at
  │
  ├─ 3. POST /chat              ← 第二轮对话
  │     ├─ upsert_message()     ← messages 表 INSERT 新用户消息
  │     ├─ agent 运行...
  │     └─ finally:
  │         ├─ upsert_message()
  │         └─ update_session_state()
  │
  └─ ...持续循环...
```

---

## 五、两个表的对比

| 维度 | sessions | messages |
|---|---|---|
| 主键 | `id`（单主键） | `(session_id, msg_id)`（联合主键） |
| 记录模型 | `_JsonRecordMixin`（索引列 + payload） | 直接映射（payload 全量 JSON） |
| INSERT 时机 | 创建会话时一次 | 每条消息一次 |
| UPDATE 时机 | 每次 chat run 结束 | 流式回复中多次 upsert 同一 msg_id |
| DELETE | 用户主动删除会话 | 级联删除（随 session 一起删除） |
| 写入来源 | `upsert_session()` | `upsert_message()` |
| 更新来源 | `update_session_state()` | `upsert_message()`（同一 msg_id 覆盖） |

---

## 六、messages 表 vs state.context：对话记录为何存两份？

`sessions` 表的 `state` 字段（JSON）中包含 `context: list[Msg]`，存储了和 `messages` 表相同的对话记录。
这不是冗余——两者的职责完全不同。

### 6.1 对比

| 维度 | messages 表 | state.context |
|---|---|---|
| **本质** | 持久化日志 | agent 的工作记忆 |
| **内容** | 所有历史消息（只增不删） | 当前 LLM 能看到的上下文窗口 |
| **谁读** | 前端展示历史记录、回放 | agent 运行时喂给 LLM |
| **是否可变** | 写入后基本不变 | 会被压缩/截断 |
| **数据量** | 完整（可能数百条） | 可能只保留最近几条 + 摘要 |

### 6.2 压缩场景

当对话太长超过 LLM 上下文窗口时，agent 会自动压缩 `context`：

```
压缩前：
  messages 表:  [msg1, msg2, msg3, ..., msg100]   ← 100 条全部保留
  state.context: [msg1, msg2, msg3, ..., msg100]   ← 与 messages 一致

压缩后：
  messages 表:  [msg1, msg2, msg3, ..., msg100]   ← 不变，完整档案
  state.context: [msg98, msg99, msg100]            ← 只保留最近几条
  state.summary: "用户之前在讨论数据库设计..."       ← 压缩摘要
```

压缩后 agent 只"记得"最近的对话 + 摘要，但前端翻聊天记录时仍能看到全部历史。

### 6.3 未压缩时的一致性

未触发压缩时，`state.context` 与 `messages` 表中该 session 的记录是一致的。
每次 chat run 结束时，同一批消息同时写入两个地方：

```
messages 表    ← upsert_message() 逐条写入
state.context ← agent 运行中自然积累，随 update_session_state() 一起持久化
```

### 6.4 总结

- **messages 表** = 完整档案（存历史，服务前端）
- **state.context** = 工作副本（服务 LLM 推理，会被压缩）

一个存历史，一个服务于推理。压缩发生前一致，压缩后 messages 表仍然完整。

---

## 七、关键源码索引

| 文件 | 行号 | 内容 |
|---|---|---|
| `_tables.py` | 57 | `_JsonRecordMixin` 基类定义 |
| `_tables.py` | 136 | `SessionRow` 表定义 |
| `_tables.py` | 338 | `MessageRow` 表定义 |
| `_storage.py` | 261 | `_upsert_stmt()` 方言原生 UPSERT |
| `_storage.py` | 329 | `_write_row()` 通用写入方法 |
| `_storage.py` | 408 | `_delete_session_impl()` 级联删除 |
| `_storage.py` | 1044 | `upsert_session()` 创建/恢复会话 |
| `_storage.py` | 1108 | `update_session_state()` 更新会话状态 |
| `_storage.py` | 1319 | `upsert_message()` 写入消息 |
| `_session.py` | 287 | POST /sessions 路由 |
| `_session.py` | 366 | DELETE /sessions/{sid} 路由 |
| `_chat.py` | 49 | POST /chat 路由 |
| `_chat.py` | 503 | `_run_impl()` 聊天主流程 |
| `_chat.py` | 962 | `finally` 块中的持久化逻辑 |
