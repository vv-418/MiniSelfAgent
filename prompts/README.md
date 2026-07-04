# prompts/ — Agent 提示词模板

> ⚠️ **当前状态**：本目录已创建，但提示词尚未从代码中独立出来。  
> 目前所有提示词硬编码在 `src/core/agent.py` 和 `src/tools/*.py` 中。  
> 本目录用于存放未来提取后的独立提示词文件。

---

## 🎯 为什么需要独立的 prompts 目录？

### 问题：提示词硬编码在代码中

```
当前状态：
┌─────────────────────────────────────────┐
│  src/core/agent.py                      │
│    SYSTEM_PROMPT = "你是一个助手..."      │  ← 提示词和代码混在一起
│                                         │
│  src/tools/todo.py                      │
│    description = "管理待办事项..."        │  ← 工具描述也是硬编码
│                                         │
│  修改提示词 = 改代码 = 有风险            │
└─────────────────────────────────────────┘

目标状态：
┌─────────────────────────────────────────┐
│  prompts/                               │
│    system_prompt.md      ← 主系统提示词  │
│    tools/                            │
│      calculator.md       ← 计算器提示词  │
│      search.md           ← 搜索提示词    │
│      todo.md             ← 待办提示词    │
│                                         │
│  src/core/agent.py                      │
│    prompt = load("prompts/system.md")   │  ← 代码只负责加载
│                                         │
│  修改提示词 = 改 .md 文件 = 安全、快速   │
└─────────────────────────────────────────┘
```

### 好处

1. **非技术人员可编辑**：产品经理、运营可直接修改 `.md` 文件优化提示词
2. **版本控制友好**：提示词变更单独提交，可追溯历史
3. **A/B 测试**：可快速切换不同版本的提示词对比效果
4. **多语言支持**：可为不同语言创建不同的提示词文件

---

## 📂 目录结构（规划中）

```
prompts/
├── README.md                 # 本文件
├── system_prompt.md          # Agent 主系统提示词
├── compress_prompt.md        # Context 压缩提示词
└── tools/                    # 各工具的提示词
    ├── calculator.md         # 计算器工具描述
    ├── search.md             # 搜索工具描述
    └── todo.md               # 待办工具描述
```

---

## 📝 提示词内容预览

### `system_prompt.md`（规划中）

```markdown
# System Prompt — MiniSelfAgent

你是 MiniSelfAgent，一个智能助手。你可以使用以下工具帮助用户：

## 可用工具

{{tools_description}}

## 行为规范

1. 优先使用工具获取准确信息
2. 复杂问题可多次调用工具
3. 回答简洁、准确
4. 如遇错误，说明原因并建议替代方案
```

### `tools/todo.md`（规划中）

```markdown
# TodoTool — 待办事项管理

## 功能
管理用户的待办事项列表

## 支持的操作
- **add**: 添加新任务
- **list**: 查看所有任务
- **done**: 标记任务完成
- **delete**: 删除任务

## 使用示例
用户："帮我添加一个任务：明天开会"
→ 调用 todo(action="add", content="明天开会")
```

---

## 🔧 提取提示词的实现方案

### 步骤 1：创建提示词文件

```python
# prompts/system_prompt.md
你是 MiniSelfAgent，一个智能助手...

# prompts/tools/todo.md  
管理用户的待办事项列表，支持 add/list/done/delete 操作...
```

### 步骤 2：修改代码加载提示词

```python
# src/core/agent.py

import os
from pathlib import Path

class AgentRuntime:
    def _build_system_prompt(self):
        # 从文件加载提示词
        prompt_file = Path(__file__).parent.parent.parent / "prompts" / "system_prompt.md"
        with open(prompt_file, "r", encoding="utf-8") as f:
            template = f.read()
        
        # 替换变量
        tools_desc = self._format_tools_for_prompt()
        return template.replace("{{tools_description}}", tools_desc)
```

### 步骤 3：工具描述也从文件加载

```python
# src/tools/todo.py

from pathlib import Path

class TodoTool(BaseTool):
    def __init__(self):
        # 从文件加载描述
        desc_file = Path(__file__).parent.parent.parent / "prompts" / "tools" / "todo.md"
        with open(desc_file, "r", encoding="utf-8") as f:
            self.description = f.read()
```

---

## 📊 提示词管理最佳实践

### 1. 版本管理

```bash
# 每次修改提示词都提交
git add prompts/
git commit -m "优化系统提示词：增加角色定义"
```

### 2. A/B 测试

```python
# 根据环境变量切换提示词版本
prompt_version = os.getenv("PROMPT_VERSION", "v1")
prompt_file = f"prompts/system_prompt_{prompt_version}.md"
```

### 3. 多语言支持

```
prompts/
├── system_prompt_zh.md    # 中文
├── system_prompt_en.md    # 英文
└── tools/
    ├── todo_zh.md
    └── todo_en.md
```

---

## ✅ 当前可操作

虽然提示词还未提取，但你可以：

1. **现在就规划**：参考上面的结构创建 `prompts/` 目录和文件
2. **手动提取**：从 `agent.py` 和 `tools/*.py` 中复制提示词到独立文件
3. **测试加载**：修改代码验证文件加载是否正常工作

---

## 📚 相关文档

- `src/core/agent.py` — 当前系统提示词所在位置
- `src/tools/*.py` — 当前工具描述所在位置
- `docs/architecture.md` — 架构文档（包含提示词流程）

---

**状态**：⏳ 目录已创建，等待提示词提取实现  
**下一步**：从 `agent.py` 提取 `SYSTEM_PROMPT` 到 `prompts/system_prompt.md`
