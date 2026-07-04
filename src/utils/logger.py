"""
日志系统 - 支持文件日志和控制台日志，记录工具调用 trace
"""
import os
import logging
import json
from datetime import datetime
from typing import Any, Dict, Optional

import config


def setup_logger(name: str = "MiniSelfAgent") -> logging.Logger:
    """创建并配置 logger"""
    os.makedirs(config.LOG_DIR, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, config.LOG_LEVEL))

    # 控制台 handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_fmt)
    logger.addHandler(console_handler)

    # 文件 handler
    log_file = os.path.join(config.LOG_DIR, f"agent_{datetime.now().strftime('%Y%m%d')}.log")
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)s [%(name)s:%(funcName)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_fmt)
    logger.addHandler(file_handler)

    return logger


# 全局 logger
logger = setup_logger()


class ToolCallTracer:
    """
    工具调用追踪器 - 记录每次工具调用的完整信息
    """

    def __init__(self):
        self.traces: list[Dict[str, Any]] = []

    def record(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Any,
        duration_ms: float,
        error: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """记录一次工具调用"""
        trace = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "tool_name": tool_name,
            "arguments": arguments,
            "result_summary": str(result)[:500] if result else None,
            "duration_ms": round(duration_ms, 2),
            "success": error is None,
            "error": error,
        }
        self.traces.append(trace)

        # 同时写入文件
        trace_file = os.path.join(config.LOG_DIR, "tool_traces.jsonl")
        os.makedirs(config.LOG_DIR, exist_ok=True)
        with open(trace_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(trace, ensure_ascii=False) + "\n")

        if error:
            logger.error(f"Tool call FAILED: {tool_name} | error={error} | duration={duration_ms:.1f}ms")
        else:
            logger.info(f"Tool call OK: {tool_name} | duration={duration_ms:.1f}ms")

        return trace

    def get_traces_for_session(self, session_id: str) -> list[Dict[str, Any]]:
        """获取指定 session 的所有 trace"""
        return [t for t in self.traces if t.get("session_id") == session_id]


# 全局 tracer
tool_tracer = ToolCallTracer()
