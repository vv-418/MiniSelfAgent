"""
测试文件 - 集成测试（使用真实 LLM API）

运行前需设置环境变量:
  LLM_API_KEY=your-key
  LLM_BASE_URL=https://api.openai.com/v1
  LLM_MODEL=gpt-4o-mini

或者使用 mock 来测试。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import patch, MagicMock
import json

from src.core.agent import AgentRuntime


class TestAgentIntegrationMocked(unittest.TestCase):
    """使用 Mock LLM 的集成测试"""

    def setUp(self):
        self.runtime = AgentRuntime()

    @patch("src.llm.client.LLMClient.chat")
    def test_simple_conversation(self, mock_chat):
        """测试简单对话（不调用工具）"""
        # 第一次调用：LLM 直接给出最终答案
        mock_chat.return_value = {
            "role": "assistant",
            "content": "你好！有什么可以帮助你的？",
            "tool_calls": None,
            "finish_reason": "stop",
        }

        session = self.runtime.session_manager.create_session()
        result = self.runtime.chat(session.session_id, "你好")

        self.assertIn("你好", result["response"])
        self.assertEqual(result["iterations"], 1)
        self.assertEqual(len(result["tool_calls"]), 0)

    @patch("src.llm.client.LLMClient.chat")
    def test_tool_call_flow(self, mock_chat):
        """测试工具调用流程"""
        session = self.runtime.session_manager.create_session()

        # 第一次调用：LLM 决定调用计算器
        mock_chat.return_value = {
            "role": "assistant",
            "content": "让我帮你计算。",
            "tool_calls": [
                {
                    "id": "call_0",
                    "type": "function",
                    "function": {
                        "name": "calculator",
                        "arguments": json.dumps({"expression": "2 + 3"}),
                    }
                }
            ],
            "finish_reason": "tool_calls",
        }

        result = self.runtime.chat(session.session_id, "帮我计算 2 + 3")
        # 由于 mock 总是返回 tool_calls，会达到最大轮次
        # 但工具应该被正确调用了
        self.assertGreater(len(result["tool_calls"]), 0)
        self.assertEqual(result["tool_calls"][0]["tool"], "calculator")

    @patch("src.llm.client.LLMClient.chat")
    def test_tool_then_answer(self, mock_chat):
        """测试调用工具后给出最终答案"""
        session = self.runtime.session_manager.create_session()

        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # 第一次：调用搜索工具
                return {
                    "role": "assistant",
                    "content": "搜索一下天气。",
                    "tool_calls": [
                        {
                            "id": "call_0",
                            "type": "function",
                            "function": {
                                "name": "search",
                                "arguments": json.dumps({"query": "北京天气"}),
                            }
                        }
                    ],
                    "finish_reason": "tool_calls",
                }
            else:
                # 第二次：基于搜索结果给出答案
                return {
                    "role": "assistant",
                    "content": "根据搜索结果，北京今天晴，32度。",
                    "tool_calls": None,
                    "finish_reason": "stop",
                }

        mock_chat.side_effect = side_effect

        result = self.runtime.chat(session.session_id, "北京今天天气怎么样？")
        self.assertIn("北京", result["response"])
        self.assertEqual(len(result["tool_calls"]), 1)
        self.assertEqual(result["iterations"], 2)

    @patch("src.llm.client.LLMClient.chat")
    def test_context_preserved(self, mock_chat):
        """测试上下文保持（追问能力）"""
        session = self.runtime.session_manager.create_session()

        # 所有调用都直接回复
        mock_chat.return_value = {
            "role": "assistant",
            "content": "收到！",
            "tool_calls": None,
            "finish_reason": "stop",
        }

        # 第一次对话
        self.runtime.chat(session.session_id, "我叫小明")
        # 第二次对话
        self.runtime.chat(session.session_id, "我叫什么名字？")

        # 验证 context 中有之前的消息
        s = self.runtime.session_manager.get_session(session.session_id)
        self.assertGreater(s.context.get_message_count(), 2)  # user + assistant * 2


class TestAgentIntegrationReal(unittest.TestCase):
    """
    使用真实 LLM API 的集成测试
    运行前需设置环境变量 LLM_API_KEY
    """

    @unittest.skipUnless(
        os.environ.get("LLM_API_KEY"),
        "需要设置 LLM_API_KEY 环境变量"
    )
    def test_real_simple_chat(self):
        """真实 API - 简单对话"""
        runtime = AgentRuntime()
        session = runtime.session_manager.create_session()
        result = runtime.chat(session.session_id, "你好，你能做什么？")
        self.assertIn("response", result)
        self.assertGreater(len(result["response"]), 0)
        print(f"\n[Real API Test] Response: {result['response'][:200]}")

    @unittest.skipUnless(
        os.environ.get("LLM_API_KEY"),
        "需要设置 LLM_API_KEY 环境变量"
    )
    def test_real_calculator(self):
        """真实 API - 计算器工具"""
        runtime = AgentRuntime()
        session = runtime.session_manager.create_session()
        result = runtime.chat(session.session_id, "请帮我计算 (15 + 25) * 3")
        self.assertIn("response", result)
        print(f"\n[Real API Test] Calculator: {result['response'][:200]}")
        print(f"Tool calls: {result['tool_calls']}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
