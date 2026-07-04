"""
测试文件 - 测试 Context 管理和 Session 管理
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from src.utils.context_manager import ContextManager
from src.session.manager import SessionManager


class TestContextManager(unittest.TestCase):
    """测试上下文管理器"""

    def setUp(self):
        self.ctx = ContextManager(session_id="test_ctx")

    def test_initial_state(self):
        self.assertEqual(self.ctx.get_message_count(), 0)
        self.assertEqual(self.ctx.total_turns, 0)

    def test_add_messages(self):
        self.ctx.add_user_message("你好")
        self.assertEqual(self.ctx.get_message_count(), 1)
        self.ctx.add_assistant_message("你好！有什么可以帮助你的？")
        self.assertEqual(self.ctx.get_message_count(), 2)

    def test_get_messages_for_llm(self):
        self.ctx.set_system_prompt("你是一个助手")
        self.ctx.add_user_message("测试")
        messages = self.ctx.get_messages_for_llm()
        # 应包含 system + user
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")

    def test_tool_result(self):
        self.ctx.add_tool_result("call_0", "calculator", "2+2=4")
        messages = self.ctx.get_messages_for_llm()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "tool")

    def test_clear(self):
        self.ctx.add_user_message("test")
        self.ctx.clear()
        self.assertEqual(self.ctx.get_message_count(), 0)

    def test_context_stats(self):
        self.ctx.add_user_message("test1")
        self.ctx.add_user_message("test2")
        stats = self.ctx.get_context_stats()
        self.assertEqual(stats["message_count"], 2)
        self.assertEqual(stats["total_turns"], 2)


class TestSessionManager(unittest.TestCase):
    """测试 Session 管理器"""

    def setUp(self):
        self.manager = SessionManager()
        # 清理测试 session
        self.test_sessions = []

    def tearDown(self):
        for sid in self.test_sessions:
            self.manager.delete_session(sid)

    def test_create_session(self):
        session = self.manager.create_session(user_id="user_A")
        self.test_sessions.append(session.session_id)
        self.assertIsNotNone(session.session_id)
        self.assertEqual(session.user_id, "user_A")
        self.assertIsNotNone(session.context)

    def test_get_session(self):
        session = self.manager.create_session()
        self.test_sessions.append(session.session_id)
        retrieved = self.manager.get_session(session.session_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.session_id, session.session_id)

    def test_get_nonexistent_session(self):
        result = self.manager.get_session("nonexistent")
        self.assertIsNone(result)

    def test_independent_sessions(self):
        """测试两个 Session 互相独立"""
        s1 = self.manager.create_session(user_id="user_A")
        s2 = self.manager.create_session(user_id="user_A")
        self.test_sessions.extend([s1.session_id, s2.session_id])

        # 在 s1 中添加消息
        s1.context.add_user_message("查天气")
        s1.context.add_assistant_message("北京今天32度")

        # s2 应该没有这些消息
        self.assertEqual(s2.context.get_message_count(), 0)
        self.assertEqual(s1.context.get_message_count(), 2)

    def test_list_sessions(self):
        s1 = self.manager.create_session(user_id="user_A")
        s2 = self.manager.create_session(user_id="user_B")
        self.test_sessions.extend([s1.session_id, s2.session_id])

        all_sessions = self.manager.list_sessions()
        self.assertGreaterEqual(len(all_sessions), 2)

        # 过滤 user_A
        user_a_sessions = self.manager.list_sessions(user_id="user_A")
        self.assertEqual(len(user_a_sessions), 1)

    def test_delete_session(self):
        session = self.manager.create_session()
        self.test_sessions.append(session.session_id)
        result = self.manager.delete_session(session.session_id)
        self.assertTrue(result)
        self.assertIsNone(self.manager.get_session(session.session_id))


if __name__ == "__main__":
    unittest.main(verbosity=2)
