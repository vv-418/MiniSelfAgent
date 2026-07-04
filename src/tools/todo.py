"""
待办事项工具 - 支持添加、查看、删除待办
"""
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from src.tools.base import BaseTool

# 待办数据存储路径
TODO_STORAGE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "todos")


class TodoTool(BaseTool):
    """
    Todo - 管理待办事项

    支持操作:
      - add:    添加新待办
      - list:   查看所有待办
      - delete: 删除指定待办（按序号）
      - done:   标记待办为完成
    """

    name = "todo"
    description = (
        "A todo list manager. Use this tool to manage personal tasks and reminders. "
        "Supported actions: "
        "'add' - add a new todo item; "
        "'list' - view all todo items; "
        "'delete' - remove a todo item by index; "
        "'done' - mark a todo item as completed."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "list", "delete", "done"],
                "description": "The action to perform: add, list, delete, or done"
            },
            "content": {
                "type": "string",
                "description": "The todo item content (required for 'add')"
            },
            "index": {
                "type": "integer",
                "description": "The index of the todo item (required for 'delete' and 'done', 1-based)"
            }
        },
        "required": ["action"]
    }

    def __init__(self, session_id: str = "default"):
        super().__init__()
        self.session_id = session_id
        self._storage_file = os.path.join(
            TODO_STORAGE_DIR, f"{session_id}.json"
        )
        os.makedirs(TODO_STORAGE_DIR, exist_ok=True)

    def _load_todos(self) -> List[Dict[str, Any]]:
        """从文件加载待办列表"""
        if not os.path.exists(self._storage_file):
            return []
        try:
            with open(self._storage_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def _save_todos(self, todos: List[Dict[str, Any]]):
        """保存待办列表到文件"""
        with open(self._storage_file, "w", encoding="utf-8") as f:
            json.dump(todos, f, ensure_ascii=False, indent=2)

    def execute(
        self,
        action: str = "list",
        content: Optional[str] = None,
        index: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        执行待办操作
        """
        todos = self._load_todos()

        if action == "add":
            if not content or not content.strip():
                return "Error: 'content' is required for add action"
            new_item = {
                "content": content.strip(),
                "done": False,
                "created_at": datetime.now().isoformat(),
            }
            todos.append(new_item)
            self._save_todos(todos)
            return f"Added todo #{len(todos)}: {content.strip()}"

        elif action == "list":
            if not todos:
                return "Todo list is empty. No items yet."
            items = []
            for i, item in enumerate(todos, 1):
                status = "✅" if item.get("done") else "⬜"
                items.append(f"  {i}. {status} {item['content']}")
            return "Todo List:\n" + "\n".join(items)

        elif action == "delete":
            if index is None:
                return "Error: 'index' is required for delete action"
            idx = index - 1  # 转为 0-based
            if idx < 0 or idx >= len(todos):
                return f"Error: Invalid index {index}. Valid range: 1-{len(todos)}"
            removed = todos.pop(idx)
            self._save_todos(todos)
            return f"Deleted todo: {removed['content']}"

        elif action == "done":
            if index is None:
                return "Error: 'index' is required for done action"
            idx = index - 1
            if idx < 0 or idx >= len(todos):
                return f"Error: Invalid index {index}. Valid range: 1-{len(todos)}"
            todos[idx]["done"] = True
            self._save_todos(todos)
            return f"Marked as done: {todos[idx]['content']}"

        else:
            return f"Error: Unknown action '{action}'. Supported: add, list, delete, done"

    def execute_for_session(self, action: str = "list", **kwargs) -> str:
        """
        为指定 session 执行待办操作（重新加载数据）
        """
        todos = self._load_todos()
        return self.execute(action=action, **kwargs)
