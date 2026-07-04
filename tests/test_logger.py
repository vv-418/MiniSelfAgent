"""
测试文件 - 测试日志和追踪系统
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from src.utils.logger import ToolCallTracer


class TestToolCallTracer(unittest.TestCase):
    """测试工具调用追踪器"""

    def setUp(self):
        self.tracer = ToolCallTracer()

    def test_record_success(self):
        trace = self.tracer.record(
            tool_name="calculator",
            arguments={"expression": "1+1"},
            result="1+1 = 2",
            duration_ms=12.5,
            session_id="test_s1",
        )
        self.assertTrue(trace["success"])
        self.assertEqual(trace["tool_name"], "calculator")

    def test_record_error(self):
        trace = self.tracer.record(
            tool_name="calculator",
            arguments={"expression": "1/0"},
            result="Error: Division by zero",
            duration_ms=1.2,
            error="Division by zero",
            session_id="test_s1",
        )
        self.assertFalse(trace["success"])
        self.assertEqual(trace["error"], "Division by zero")

    def test_get_traces_for_session(self):
        self.tracer.record(
            tool_name="search",
            arguments={"query": "test"},
            result="results",
            duration_ms=50,
            session_id="s1",
        )
        self.tracer.record(
            tool_name="calculator",
            arguments={"expression": "1+1"},
            result="2",
            duration_ms=5,
            session_id="s2",
        )

        s1_traces = self.tracer.get_traces_for_session("s1")
        self.assertEqual(len(s1_traces), 1)
        self.assertEqual(s1_traces[0]["tool_name"], "search")

        s2_traces = self.tracer.get_traces_for_session("s2")
        self.assertEqual(len(s2_traces), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
