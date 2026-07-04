"""
测试文件 - 测试工具系统
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import unittest
from src.tools.base import ToolRegistry, BaseTool
from src.tools.calculator import CalculatorTool
from src.tools.search import SearchTool
from src.tools.todo import TodoTool


class TestCalculatorTool(unittest.TestCase):
    """测试计算器工具"""

    def setUp(self):
        self.tool = CalculatorTool()

    def test_basic_addition(self):
        result = self.tool.execute(expression="2 + 3")
        self.assertEqual(result, "2 + 3 = 5")

    def test_basic_multiplication(self):
        result = self.tool.execute(expression="15 * 4")
        self.assertEqual(result, "15 * 4 = 60")

    def test_complex_expression(self):
        result = self.tool.execute(expression="(3 + 5) / 2")
        self.assertEqual(result, "(3 + 5) / 2 = 4.0")

    def test_power(self):
        result = self.tool.execute(expression="2 ** 10")
        self.assertEqual(result, "2 ** 10 = 1024")

    def test_sqrt(self):
        result = self.tool.execute(expression="sqrt(144)")
        self.assertIn("12", result)

    def test_division_by_zero(self):
        result = self.tool.execute(expression="1 / 0")
        self.assertIn("Error", result)

    def test_empty_expression(self):
        result = self.tool.execute(expression="")
        self.assertIn("Error", result)

    def test_invalid_expression(self):
        result = self.tool.execute(expression="import os; os.system('rm -rf /')")
        self.assertIn("Error", result)

    def test_tool_schema(self):
        schema = self.tool.to_openai_tool()
        self.assertEqual(schema["type"], "function")
        self.assertEqual(schema["function"]["name"], "calculator")
        self.assertIn("expression", schema["function"]["parameters"]["properties"])


class TestSearchTool(unittest.TestCase):
    """测试搜索工具"""

    def setUp(self):
        self.tool = SearchTool()

    def test_search_weather(self):
        result = self.tool.execute(query="北京天气")
        data = json.loads(result)
        # 天气查询返回真实API结果
        self.assertIn("result", data)
        self.assertIn("city", data)
        self.assertIn("source", data)
        self.assertEqual(data["source"], "wttr.in (real-time)")

    def test_search_python(self):
        result = self.tool.execute(query="Python async programming")
        data = json.loads(result)
        self.assertGreater(len(data["results"]), 0)

    def test_search_empty_query(self):
        result = self.tool.execute(query="")
        data = json.loads(result)
        self.assertEqual(len(data["results"]), 0)

    def test_search_no_match(self):
        result = self.tool.execute(query="quantum physics 量子物理")
        data = json.loads(result)
        self.assertGreater(len(data["results"]), 0)  # 返回默认结果

    def test_tool_schema(self):
        schema = self.tool.to_openai_tool()
        self.assertEqual(schema["function"]["name"], "search")
        self.assertIn("query", schema["function"]["parameters"]["properties"])


class TestTodoTool(unittest.TestCase):
    """测试待办事项工具"""

    def setUp(self):
        import tempfile
        self.test_session_id = "test_session_" + str(id(self))
        self.tool = TodoTool(session_id=self.test_session_id)
        # 清理测试文件
        if os.path.exists(self.tool._storage_file):
            os.remove(self.tool._storage_file)

    def tearDown(self):
        # 清理测试文件
        if os.path.exists(self.tool._storage_file):
            os.remove(self.tool._storage_file)

    def test_add_todo(self):
        result = self.tool.execute(action="add", content="买菜")
        self.assertIn("Added todo", result)
        self.assertIn("买菜", result)

    def test_list_empty(self):
        result = self.tool.execute(action="list")
        self.assertIn("empty", result.lower())

    def test_list_with_items(self):
        self.tool.execute(action="add", content="任务1")
        self.tool.execute(action="add", content="任务2")
        result = self.tool.execute(action="list")
        self.assertIn("任务1", result)
        self.assertIn("任务2", result)

    def test_done_todo(self):
        self.tool.execute(action="add", content="完成测试")
        result = self.tool.execute(action="done", index=1)
        self.assertIn("done", result.lower())
        # 验证状态
        list_result = self.tool.execute(action="list")
        self.assertIn("✅", list_result)

    def test_delete_todo(self):
        self.tool.execute(action="add", content="待删除")
        result = self.tool.execute(action="delete", index=1)
        self.assertIn("Deleted", result)
        # 验证已删除
        list_result = self.tool.execute(action="list")
        self.assertNotIn("待删除", list_result)

    def test_invalid_index(self):
        result = self.tool.execute(action="delete", index=999)
        self.assertIn("Error", result)

    def test_add_requires_content(self):
        result = self.tool.execute(action="add", content="")
        self.assertIn("Error", result)


class TestToolRegistry(unittest.TestCase):
    """测试工具注册机制"""

    def setUp(self):
        self.registry = ToolRegistry()
        self.registry.register(CalculatorTool())
        self.registry.register(SearchTool())

    def test_list_tools(self):
        tools = self.registry.list_tools()
        self.assertIn("calculator", tools)
        self.assertIn("search", tools)

    def test_get_tool(self):
        calc = self.registry.get("calculator")
        self.assertIsNotNone(calc)
        self.assertIsInstance(calc, CalculatorTool)

    def test_get_nonexistent_tool(self):
        result = self.registry.get("nonexistent")
        self.assertIsNone(result)

    def test_execute_tool(self):
        result = self.registry.execute("calculator", {"expression": "1+1"})
        self.assertEqual(result, "1+1 = 2")

    def test_execute_unknown_tool(self):
        result = self.registry.execute("nonexistent", {})
        self.assertIn("Error", result)

    def test_get_schemas(self):
        schemas = self.registry.get_schemas()
        self.assertEqual(len(schemas), 2)
        names = [s["function"]["name"] for s in schemas]
        self.assertIn("calculator", names)
        self.assertIn("search", names)


if __name__ == "__main__":
    unittest.main(verbosity=2)
