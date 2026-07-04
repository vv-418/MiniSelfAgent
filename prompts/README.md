# prompts/ — Agent 提示词模板

> ✅ **已完成**：提示词已从代码中独立出来，由 `src/utils/prompt_loader.py` 统一加载。  
> 修改提示词只需编辑 `.md` 文件，无需改动 Python 代码。

---

## 📂 目录结构

```
prompts/
├── README.md                 # 本文件
├── system_prompt.md          # Agent 主系统提示词（已实现 ✅）
└── compress_prompt.md        # Context 压缩摘要模板（已实现 ✅）
```

---

## 📝 已实现的提示词文件

### `system_prompt.md`

Agent 的主系统提示词，包含角色定义、工具列表占位符、回答规范、时间与 Session ID 变量。

**模板变量**：

| 变量 | 说明 | 注入时机 |
|------|------|----------|
| `{tools_description}` | 工具注册表自动注入的工具描述列表 | `agent.py` `_build_system_prompt()` |
| `{current_time}` | 当前时间 | `agent.py` `_build_system_prompt()` |
| `{session_id}` | 当前 Session ID | `agent.py` `_build_system_prompt()` |

### `compress_prompt.md`

Context 压缩时使用的摘要格式模板。当消息数超过阈值（15 条）时，将早期消息按此模板格式压缩为摘要，注入消息列表最前面。

**模板变量**：

| 变量 | 说明 |
|------|------|
| `{threshold}` | 压缩触发阈值（15） |
| `{user_topics}` | 用户讨论的话题摘要 |
| `{tool_uses}` | 工具使用记录 |
| `{key_decisions}` | 关键信息与结论 |
| `{topic_max_chars}` | 用户话题截取长度 |
| `{keep_recent}` | 保留的最近消息数（6） |

---

## 🔧 加载机制

### prompt_loader.py 提供两个核心函数

```python
from src.utils.prompt_loader import load_prompt, render_prompt

# 1. 直接加载（无变量替换）
content = load_prompt("system_prompt.md")

# 2. 加载 + 变量替换
content = render_prompt(
    "system_prompt.md",
    variables={
        "tools_description": "...",
        "current_time": "2026-07-04 22:00:00",
        "session_id": "abc-123",
    },
    fallback="默认提示词..."
)
```

### agent.py 中的调用方式

```python
# src/core/agent.py
from src.utils.prompt_loader import render_prompt

class AgentRuntime:
    def _build_system_prompt(self, session):
        tools_desc = "\n".join([
            f"- **{t.name}**: {t.description}"
            for t in self.tool_registry._tools.values()
        ])
        return render_prompt(
            "system_prompt.md",
            variables={
                "tools_description": tools_desc,
                "current_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "session_id": session.session_id,
            },
            fallback=_DEFAULT_SYSTEM_PROMPT.format(...)  # 保底内置默认值
        )
```

### 安全回退机制

如果 `prompts/` 下的 `.md` 文件缺失或损坏，`load_prompt()` 返回 `fallback` 参数指定的默认值，`agent.py` 中硬编码的 `_DEFAULT_SYSTEM_PROMPT` 确保系统不会因文件缺失而崩溃。

---

## 📊 如何修改提示词

1. **修改系统提示词** → 编辑 `prompts/system_prompt.md`
2. **修改压缩格式** → 编辑 `prompts/compress_prompt.md`
3. **运行测试** → `python -m unittest discover` 验证无回归

不需要改动任何 Python 代码。

---

## 🚀 未来扩展计划

如需为每个工具单独创建提示词描述文件（如 `tools/todo.md`），可按以下方式扩展：

1. 在 `prompts/tools/` 下创建 `.md` 文件
2. 修改 `BaseTool` 子类的 `__init__` 方法，从文件加载 `self.description`
3. 在 `prompt_loader.py` 中添加对应的加载函数

---

**状态**：✅ 已完成实现  
**相关代码**：`src/utils/prompt_loader.py`、`src/core/agent.py`（`_build_system_prompt` 方法）
