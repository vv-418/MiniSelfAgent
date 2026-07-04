"""
测试文件 - 测试 LLM 输出解析器
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import unittest
from src.llm.parser import LLMOutputParser, AgentResponse


class TestLLMOutputParser(unittest.TestCase):
    """测试 LLM 输出解析器"""

    def setUp(self):
        self.parser = LLMOutputParser()

    def test_parse_final_answer(self):
        """测试解析纯文本最终回答"""
        response = {
            "role": "assistant",
            "content": "北京今天天气晴朗，温度32度。",
            "tool_calls": None,
            "finish_reason": "stop",
        }
        result = self.parser.parse(response)
        self.assertIsNotNone(result.finish)
        self.assertIn("北京", result.finish.answer)
        self.assertIsNone(result.action)

    def test_parse_tool_call(self):
        """测试解析 OpenAI 格式的 tool_calls"""
        response = {
            "role": "assistant",
            "content": "让我帮你计算一下。",
            "tool_calls": [
                {
                    "id": "call_abc123",
                    "type": "function",
                    "function": {
                        "name": "calculator",
                        "arguments": json.dumps({"expression": "2 + 3"}),
                    }
                }
            ],
            "finish_reason": "tool_calls",
        }
        result = self.parser.parse(response)
        self.assertIsNotNone(result.action)
        self.assertEqual(result.action.tool_name, "calculator")
        self.assertEqual(result.action.tool_arguments["expression"], "2 + 3")
        self.assertIsNone(result.finish)

    def test_parse_thinking(self):
        """测试解析带思考过程的回复"""
        response = {
            "role": "assistant",
            "content": "<thinking>用户想知道天气，我应该搜索一下。</thinking>让我搜索北京天气。",
            "tool_calls": None,
            "finish_reason": "stop",
        }
        result = self.parser.parse(response)
        self.assertIsNotNone(result.finish)
        self.assertIn("搜索", result.thinking_process)
        # 最终答案中不应包含 thinking 标签
        self.assertNotIn("<thinking>", result.finish.answer)

    def test_parse_tool_call_arguments_string(self):
        """测试参数为字符串时的解析"""
        response = {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_xyz",
                    "type": "function",
                    "function": {
                        "name": "search",
                        "arguments": '{"query": "Python tutorial"}',
                    }
                }
            ],
            "finish_reason": "tool_calls",
        }
        result = self.parser.parse(response)
        self.assertIsNotNone(result.action)
        self.assertEqual(result.action.tool_name, "search")

    def test_parse_empty_content(self):
        """测试空内容"""
        response = {
            "role": "assistant",
            "content": "",
            "tool_calls": None,
            "finish_reason": "stop",
        }
        result = self.parser.parse(response)
        self.assertIsNotNone(result.finish)

    def test_parse_text_tool_call_fallback(self):
        """测试从文本中解析 tool_call（fallback 模式）"""
        response = {
            "role": "assistant",
            "content": '我来帮你搜索。\n```tool_call\n{"tool_name": "search", "arguments": {"query": "天气"}}\n```',
            "tool_calls": None,
            "finish_reason": "stop",
        }
        result = self.parser.parse(response)
        self.assertIsNotNone(result.action)
        self.assertEqual(result.action.tool_name, "search")


if __name__ == "__main__":
    unittest.main(verbosity=2)
