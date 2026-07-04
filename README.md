# MiniSelfAgent — 运行方式、系统设计与 Memory 机制说明

---

## 一、项目运行方式

### 1.1 环境准备

```bash
# 安装依赖（仅 3 个）
pip install -r requirements.txt
```

| 依赖包 | 用途 |
|--------|------|
| `openai>=1.0.0` | 调用 LLM API（支持 OpenAI 兼容接口） |
| `python-dotenv>=1.0.0` | 自动加载 `.env` 配置 |
| `requests>=2.28.0` | 天气 API 调用（wttr.in） |

### 1.2 配置环境变量

将 `.env.example` 复制为 `.env` 并填入真实值：

```env
LLM_API_KEY=your-api-key-here
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

支持任意 OpenAI 兼容接口（OpenAI / DeepSeek / Moonshot / 火山引擎豆包等），只需修改 `LLM_BASE_URL` 和 `LLM_MODEL`。

配置优先级：**命令行参数 > `.env` 文件 > 系统环境变量**。

### 1.3 启动方式

#### 基本启动（交互式 CLI）

```bash
python main.py
```
有python环境用自己的，我的是"D:\Users\vv\Anaconda3\envs\litcraft\python.exe"
```bash
D:\Users\vv\Anaconda3\envs\litcraft\python.exe main.py -v
```


#### 支持的命令行参数

| 参数 | 缩写 | 说明 | 示例 |
|------|------|------|------|
| `--verbose` | `-v` | 显示 Agent 思考过程等详细信息 | `python main.py -v` |
| `--model` | — | 覆盖 LLM 模型名称 | `python main.py --model deepseek-chat` |
| `--api-key` | — | 覆盖 API Key | `python main.py --api-key sk-xxx` |
| `--base-url` | — | 覆盖 API Base URL | `python main.py --base-url https://api.deepseek.com/v1` |
| `--session` | — | 恢复指定 Session（续接之前对话） | `python main.py --session a1b2c3d4` |

#### 交互式命令（在 CLI 中输入）

| 命令 | 说明 |
|------|------|
| `quit` / `exit` / `q` | 退出程序 |
| `new` | 创建一个新的 Session（新对话） |
| `switch <session_id>` | 切换到已有 Session |
| `sessions` | 列出所有 Session 及最近话题摘要 |

### 1.4 启动流程

```
python main.py
│
├── 1. 解析命令行参数（argparse）
│      ↓
├── 2. 覆盖 config 配置（如有 --model/--api-key/--base-url）
│      ↓
├── 3. 进入 cli_mode()
│      ├── 创建 AgentRuntime（初始化 LLMClient + ToolRegistry + SessionManager）
│      ├── 如果指定了 --session → 恢复已有 Session
│      ├── 否则 → 创建新 Session
│      └── 进入 while True 交互循环
│             ↓
│      4. 等待用户输入
│         ├── 特殊命令（quit/new/switch/sessions）→ 执行对应逻辑
│         └── 普通文本 → 调用 runtime.chat(session_id, user_input)
│                ↓
│         5. runtime.chat() 内部流程：
│            ├── SessionManager 获取/创建 Session
│            ├── 设置 System Prompt（含工具列表 + 当前时间 + Session ID）
│            ├── ContextManager 追加 user 消息
│            ├── 执行 _run_agent_loop()（ReAct 循环）
│            └── 保存 Session 持久化到 JSON 文件
```

---

## 二、系统设计

### 2.1 项目结构

```
MiniSelfAgent/
├── main.py                         # 入口：CLI 模式 + 命令行参数解析
├── config.py                       # 全局配置（LLM / Agent / Session / 天气 API / 日志）
├── .env                            # 环境变量（API Key 等，不提交 git）
├── requirements.txt                # 依赖清单
├── src/
│   ├── core/
│   │   └── agent.py                # 🔑 AgentRuntime：ReAct 循环引擎
│   ├── llm/
│   │   ├── client.py               # LLMClient：封装 OpenAI 兼容 API 调用
│   │   └── parser.py               # LLMOutputParser：三级输出解析策略
│   ├── tools/
│   │   ├── base.py                 # BaseTool 基类 + ToolRegistry（@tool 装饰器）
│   │   ├── calculator.py           # CalculatorTool（eval 安全计算）
│   │   ├── search.py               # SearchTool（天气 API + Mock 搜索）
│   │   └── todo.py                 # TodoTool（待办 CRUD）
│   ├── session/
│   │   └── manager.py              # SessionManager + Session：多会话隔离与持久化
│   └── utils/
│       ├── context_manager.py      # ContextManager：消息历史管理 + 压缩
│       └── logger.py               # 日志系统（info/debug + tool trace）
├── data/
│   ├── sessions/                   # Session JSON 持久化存储
│   └── logs/                       # 运行日志
├── prompts/                        # Prompt 模板（预留）
├── tests/                          # 单元测试（54 个）
└── .copilot-hub/                   # 任务记录与 Memory 知识库
```

### 2.2 核心模块交互图

```
┌──────────────────────────────────────────────────────────────────┐
│                         main.py (入口)                           │
│                     argparse → cli_mode()                        │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                     AgentRuntime (核心循环)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │ LLMClient    │  │ LLMOutput    │  │ ToolRegistry           │  │
│  │              │  │ Parser       │  │                        │  │
│  │ chat()       │  │ parse()      │  │ CalculatorTool         │  │
│  │ → API 调用   │  │ → 三级策略   │  │ SearchTool (天气API)    │  │
│  └──────┬───────┘  └──────┬───────┘  │ TodoTool               │  │
│         │                 │          └────────────────────────┘  │
│         │                 │                                      │
│         ▼                 ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │            ReAct Loop (最多 MAX_LOOP_ITERATIONS=10 轮)   │    │
│  │                                                         │    │
│  │  1. context.get_messages_for_llm() → 发送消息给 LLM     │    │
│  │  2. parser.parse(response) → 解析输出                   │    │
│  │  3a. 有 tool_calls → 执行工具 → 结果写入 context → 继续 │    │
│  │  3b. 无 tool_calls → 返回最终答案                       │    │
│  │  4. 达到最大轮次 → 强制返回兜底回答                      │    │
│  └─────────────────────────────────────────────────────────┘    │
│                           │                                      │
│                           ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │           SessionManager + ContextManager                │    │
│  │  Session: session_id / context / todo_tool / metadata   │    │
│  │  Context: messages[] / system_prompt / total_turns      │    │
│  └─────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
                           │
                           ▼
              ┌─────────────────────┐
              │  data/sessions/     │
              │  session_*.json     │  ← 持久化存储
              └─────────────────────┘
```

### 2.3 数据流详解

一次完整的用户交互数据流：

```
用户输入 "北京天气怎么样"
│
├── ① ContextManager.add_user_message("北京天气怎么样")
│      messages: [..., {role: "user", content: "北京天气怎么样"}]
│
├── ② context.get_messages_for_llm()
│      → 首次：[system_prompt, user_msg]（2条消息）
│      → 多轮：自动压缩旧消息，保留最近 6 条
│
├── ③ LLMClient.chat(messages, tools=tool_schemas)
│      → 调用 OpenAI 兼容 API，传入工具 Schema
│
├── ④ LLM 返回：{role: "assistant", tool_calls: [{id, function: {name: "search", arguments: '{"city":"北京"}'}}]}
│
├── ⑤ LLMOutputParser.parse(response) → AgentResponse(action=AgentAction(tool_name="search", ...))
│
├── ⑥ tool_registry.execute("search", city="北京") → 真实调用 wttr.in API
│      返回天气 JSON: {city: "北京", source: "wttr.in", result: {...}}
│
├── ⑦ ContextManager.add_tool_message(tool_call_id, result_json)
│      messages: [..., assistant_msg, tool_msg]
│
├── ⑧ 再次调用 LLM（携带 tool 结果） → LLM 生成最终自然语言回答
│
├── ⑨ context.add_assistant_message(final_response)
│
└── ⑩ SessionManager.save_session() → 持久化到 data/sessions/session_xxx.json
```

### 2.4 各模块职责一览

| 模块 | 文件 | 核心职责 | 关键参数 |
|------|------|----------|----------|
| **AgentRuntime** | `src/core/agent.py` | ReAct 循环引擎，协调所有模块 | `MAX_LOOP_ITERATIONS=10` |
| **LLMClient** | `src/llm/client.py` | 封装 OpenAI 兼容 API 调用 | `LLM_TEMPERATURE=0.7`, `LLM_MAX_TOKENS=2048` |
| **LLMOutputParser** | `src/llm/parser.py` | 三级解析：tool_calls → thinking 标签 → 文本 | 支持结构化 tool_call JSON |
| **ToolRegistry** | `src/tools/base.py` | 工具注册表，`@tool` 装饰器自动收集 Schema | — |
| **ContextManager** | `src/utils/context_manager.py` | 消息历史管理、压缩 | `keep_recent=6`, `THRESHOLD=15` |
| **SessionManager** | `src/session/manager.py` | 多会话隔离、持久化、恢复 | `SESSION_EXPIRY=24h` |

---

## 三、Memory 召回时机与放置方式

> 这里的 "Memory" 指 Agent 在多轮对话中**记住并复用历史信息**的机制。
> 本项目通过三层机制实现 Memory 功能。

### 3.1 三层 Memory 架构

```
┌─────────────────────────────────────────────────────────┐
│  第一层：Session 内消息历史（ContextManager）              │
│  作用：记住当前会话的对话上下文                            │
│  范围：单个 Session 生命周期内                             │
│  持久化：随 Session JSON 文件保存到磁盘                   │
├─────────────────────────────────────────────────────────┤
│  第二层：历史压缩摘要（ContextManager._compress_old）      │
│  作用：当消息过多时，用压缩摘要"回忆"早期话题               │
│  触发条件：消息数 > CONTEXT_COMPRESS_THRESHOLD(15)        │
│  保留：最近 6 条消息 + 压缩摘要                           │
├─────────────────────────────────────────────────────────┤
│  第三层：Session 恢复（SessionManager）                    │
│  作用：跨进程恢复之前的对话状态                             │
│  触发条件：启动时 --session 参数                           │
│  范围：跨进程/跨时间                                       │
└─────────────────────────────────────────────────────────┘
```

### 3.2 第一层：Session 内消息历史

**放置方式**：消息按时间顺序存储在 `ContextManager.messages` 列表中，每次用户输入和 LLM 回复都追加到列表末尾。

**召回时机**：每次 Agent 调用 LLM 时，通过 `context.get_messages_for_llm()` 将完整消息历史发送给 LLM，LLM 自此获得上下文记忆。

**消息类型**：

| role | 来源 | 内容 |
|------|------|------|
| `system` | `_build_system_prompt()` | 工具描述 + 回答规范 + 当前时间 + Session ID |
| `user` | 用户输入 | 用户的自然语言请求 |
| `assistant` | LLM 回复 | LLM 的回答（可能包含 tool_calls） |
| `tool` | 工具执行结果 | 工具返回的 JSON 结果（带 tool_call_id） |

**示例**（3 轮对话后的 messages 结构）：

```python
messages = [
    {"role": "system",    "content": "你是一个智能助手..."},      # System Prompt
    {"role": "user",      "content": "北京天气怎么样"},            # 第 1 轮
    {"role": "assistant", "content": "", "tool_calls": [...]},    # LLM 决定查天气
    {"role": "tool",      "content": "{city: 北京, ...}", "tool_call_id": "call_xxx"},
    {"role": "assistant", "content": "北京今天晴，25°C..."},       # 最终回答
    {"role": "user",      "content": "那上海呢"},                 # 第 2 轮
    {"role": "assistant", "content": "", "tool_calls": [...]},
    {"role": "tool",      "content": "{city: 上海, ...}", "tool_call_id": "call_yyy"},
    {"role": "assistant", "content": "上海今天多云，22°C..."},
    {"role": "user",      "content": "帮我记个待办"},             # 第 3 轮
    {"role": "assistant", "content": "好的，已添加待办：..."},
]
```

### 3.3 第二层：历史压缩摘要（核心 Memory 机制）

这是本项目**最关键的 Memory 召回机制** —— 当对话变长时，自动压缩早期历史，让 LLM 能"回忆"起之前的话题。

#### 召回时机

```python
# context_manager.py 内部逻辑
if len(self.messages) > config.CONTEXT_COMPRESS_THRESHOLD:  # > 15 条
    self._compress_old_messages()
```

**触发条件**：`messages` 列表长度超过 **15** 条时，在 `get_messages_for_llm()` 中自动触发压缩。

#### 放置方式

压缩后的摘要作为 **system 消息** 注入到消息列表的**最前面**：

```
压缩前（16条消息）：
  [system] [user_1] [assistant_1] [tool_1] [assistant_1_回复]
           [user_2] [assistant_2] [tool_2] [assistant_2_回复]
           [user_3] ... [user_8] [assistant_8]

                    ↓ 压缩触发（>15条）

压缩后（7条消息）：
  [system: 摘要] + [最近 6 条消息]
```

#### 压缩策略

压缩**不调用 LLM**，直接从历史消息中提取结构化摘要：

```python
def _summarize_messages(self, messages):
    user_topics = []    # 用户讨论了什么（取每条 user 消息前 100 字符）
    tool_uses = []      # 使用了哪些工具
    key_decisions = []  # 关键回复内容

    # 摘要示例输出：
    # "用户讨论了: 北京天气怎么样; 那上海呢; 帮我记个待办
    #  | 使用了工具: search, todo
    #  | 关键回复: 北京今天晴 25°C; 已添加待办：买牛奶"
```

#### 保留策略

| 部分 | 数量 | 说明 |
|------|------|------|
| 摘要消息 | 1 条 | `role: system`，内容为 `[对话历史摘要] ...` |
| 最近消息 | 6 条 | 保留最近 3 轮完整对话，保证连贯性 |

#### 多轮压缩效果

```
第 1 次压缩（消息数 15→7）：
  [摘要_1] [user_5] [assistant_5] [user_6] [assistant_6] [user_7] [assistant_7]

第 2 次压缩（消息数再次超过 15）：
  [摘要_2: 摘要_1 + 第5-7轮摘要] [user_N...] [assistant_N...]
```

### 3.4 第三层：Session 恢复

#### 召回时机

启动时通过 `--session <id>` 参数恢复历史 Session：

```bash
python main.py --session a1b2c3d4
```

内部流程：

```python
# SessionManager.get_or_create_session()
if session_id and session_id in self._sessions:
    session = self._sessions[session_id]  # 从内存/磁盘恢复
    session.touch()  # 更新 last_active 时间
    return session
```

#### 持久化方式

Session 数据以 JSON 格式存储在 `data/sessions/` 目录下：

```
data/sessions/
├── a1b2c3d4.json      # Session: {session_id, messages[], todo_list, metadata}
├── e5f6g7h8.json
└── ...
```

#### Session 过期

```python
SESSION_EXPIRY_SECONDS = 3600 * 24  # 24 小时过期
```

过期的 Session 会被自动清理，不再出现在可恢复列表中。

### 3.5 Memory 流程总结图

```
用户输入 "帮我查下北京天气"
        │
        ▼
┌─ ContextManager ────────────────────────────────────────┐
│                                                         │
│  messages 数量 <= 15 ?                                   │
│  ├── YES → 直接用全部 messages                           │
│  │         get_messages_for_llm() 返回所有消息            │
│  │         ↓                                            │
│  │         LLM 通过完整上下文获得"记忆"                   │
│  │                                                      │
│  └── NO (>15) → 触发压缩                                 │
│              _compress_old_messages()                   │
│              ├── 提取摘要: "用户讨论了X; 用了工具Y"       │
│              ├── 保留最近 6 条消息                        │
│              └── 结果: [摘要 + 6条最近消息]               │
│                   ↓                                     │
│              LLM 通过摘要"回忆"早期话题                   │
│              + 通过最近消息保持连贯                        │
│                                                         │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
              LLM 生成回答（具备上下文记忆）
```

### 3.6 关键参数速查表

| 参数 | 值 | 作用 | 文件位置 |
|------|-----|------|----------|
| `keep_recent` | 6 | 压缩时保留最近消息数 | `context_manager.py` |
| `CONTEXT_COMPRESS_THRESHOLD` | 15 | 触发压缩的消息数阈值 | `config.py` |
| `CONTEXT_MAX_MESSAGES` | 20 | context 中最大消息数上限 | `config.py` |
| `CONTEXT_SUMMARY_MAX_TOKENS` | 512 | 摘要最大 token 数 | `config.py` |
| `MAX_LOOP_ITERATIONS` | 10 | 单次输入最大 Agent 循环次数 | `config.py` |
| `SESSION_EXPIRY_SECONDS` | 86400 | Session 过期时间（秒） | `config.py` |
| `SESSION_STORAGE_DIR` | `data/sessions/` | Session 持久化目录 | `config.py` |

---

## 四、总结

| 维度 | 机制 | 说明 |
|------|------|------|
| **运行方式** | CLI 交互式 | `python main.py` 启动，支持参数覆盖和 Session 恢复 |
| **系统设计** | ReAct Loop | 用户输入 → LLM 判断 → 工具调用 → 结果回传 → 循环/终止 |
| **Memory 召回** | 三层架构 | Session 内历史 → 压缩摘要 → 跨进程恢复 |
| **Memory 放置** | 压缩摘要 → system 消息 | 摘要注入消息列表最前面，LLM 首先读取 |
| **Memory 持久化** | JSON 文件 | `data/sessions/*.json`，支持跨进程恢复 |
