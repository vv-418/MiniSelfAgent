"""
工具基类和注册机制
每个工具需要包含: 名称、描述、参数 Schema
LLM 基于 Schema 自主决策调用
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import inspect


class BaseTool(ABC):
    """
    工具基类 —— 所有工具必须继承此类

    子类必须定义:
        name: str          工具名称
        description: str   工具描述（给 LLM 看）
        parameters: dict   JSON Schema 格式的参数定义
    """

    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """
        执行工具逻辑，返回字符串结果
        """
        ...

    def to_openai_tool(self) -> Dict[str, Any]:
        """
        转换为 OpenAI function calling 格式的 tool 定义
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }


class ToolRegistry:
    """
    工具注册表 —— 管理所有可用工具

    - 注册工具
    - 根据名称查找工具
    - 生成 tool schemas 列表供 LLM 使用
    - 执行工具调用
    """

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        """注册一个工具"""
        if not tool.name:
            raise ValueError(f"Tool {tool.__class__.__name__} must define a 'name'")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        """根据名称获取工具"""
        return self._tools.get(name)

    def list_tools(self) -> List[str]:
        """列出所有已注册工具的名称"""
        return list(self._tools.keys())

    def get_schemas(self) -> List[Dict[str, Any]]:
        """获取所有工具的 OpenAI function calling schema"""
        return [tool.to_openai_tool() for tool in self._tools.values()]

    def execute(self, name: str, arguments: Dict[str, Any]) -> str:
        """
        执行指定工具

        Args:
            name: 工具名称
            arguments: 工具参数（从 LLM 输出解析得到的 JSON 字典）

        Returns:
            工具执行结果字符串
        """
        tool = self._tools.get(name)
        if not tool:
            return f"Error: Unknown tool '{name}'. Available tools: {self.list_tools()}"

        try:
            result = tool.execute(**arguments)
            return result
        except TypeError as e:
            return f"Error: Invalid arguments for tool '{name}': {e}"
        except Exception as e:
            return f"Error: Tool '{name}' execution failed: {e}"
