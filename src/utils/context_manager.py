"""
Context 管理器 - 负责消息历史的维护、轮次控制和基础压缩
"""
import json
import copy
from typing import List, Dict, Any, Optional

import config
from src.utils.logger import logger


class ContextManager:
    """
    管理 Agent 的对话上下文 (message list)
    
    核心职责：
    1. 维护完整的消息历史 (user/assistant/tool)
    2. 超过阈值时进行基础压缩 (截断 + 摘要)
    3. 提供 context 给 LLM 调用
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.messages: List[Dict[str, str]] = []
        self.system_prompt: Optional[str] = None
        self.total_turns: int = 0  # 用户输入轮次数

    def set_system_prompt(self, prompt: str):
        """设置系统提示词"""
        self.system_prompt = prompt

    def add_user_message(self, content: str):
        """添加用户消息"""
        self.messages.append({"role": "user", "content": content})
        self.total_turns += 1

    def add_assistant_message(self, content: str, tool_calls: Optional[List[Dict[str, Any]]] = None):
        """
        添加助手消息

        Args:
            content: 文本内容
            tool_calls: OpenAI 格式的 tool_calls 列表 (top-level field)
        """
        msg: Dict[str, Any] = {"role": "assistant", "content": content}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        self.messages.append(msg)

    def add_tool_result(self, tool_call_id: str, tool_name: str, result: str):
        """
        添加工具调用结果（作为 tool 角色消息）

        OpenAI API 要求 tool_call_id 作为消息的 top-level 字段，
        而不是嵌套在 content JSON 中。
        """
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": result,
        })

    @staticmethod
    def _sanitize_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        自动迁移旧格式消息，修复 tool_calls / tool_call_id 嵌套在 content JSON 字符串中的问题。

        旧格式（错误）:
          assistant: {"role": "assistant", "content": "{\\"content\\": \\"\\", \\"tool_calls\\": [...]} "}
          tool:      {"role": "tool", "content": "{\\"tool_call_id\\": \\"call_0\\", ...}"}

        新格式（正确）:
          assistant: {"role": "assistant", "content": "...", "tool_calls": [...]}
          tool:      {"role": "tool", "content": "...", "tool_call_id": "call_0"}
        """
        sanitized = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "tool" and isinstance(content, str):
                # 尝试从 content JSON 中提取 tool_call_id
                if "tool_call_id" in content and "tool_call_id" not in msg:
                    try:
                        parsed = json.loads(content)
                        if isinstance(parsed, dict) and "tool_call_id" in parsed:
                            new_msg = {
                                "role": "tool",
                                "tool_call_id": parsed["tool_call_id"],
                                "content": parsed.get("result", content),
                            }
                            logger.debug(
                                f"[ContextManager] Migrated old-format tool message "
                                f"(tool_call_id={parsed['tool_call_id']})"
                            )
                            sanitized.append(new_msg)
                            continue
                    except (json.JSONDecodeError, TypeError):
                        pass

            elif role == "assistant" and isinstance(content, str):
                # 尝试从 content JSON 中提取 tool_calls
                if '"tool_calls"' in content and "tool_calls" not in msg:
                    try:
                        parsed = json.loads(content)
                        if isinstance(parsed, dict) and "tool_calls" in parsed:
                            new_msg = {
                                "role": "assistant",
                                "content": parsed.get("content", ""),
                                "tool_calls": parsed["tool_calls"],
                            }
                            logger.debug(
                                f"[ContextManager] Migrated old-format assistant message "
                                f"with {len(parsed['tool_calls'])} tool_calls"
                            )
                            sanitized.append(new_msg)
                            continue
                    except (json.JSONDecodeError, TypeError):
                        pass

            sanitized.append(msg)
        return sanitized

    def get_messages_for_llm(self) -> List[Dict[str, str]]:
        """
        获取发送给 LLM 的完整消息列表
        会自动检查是否需要压缩，并迁移旧格式消息
        """
        self._maybe_compress()

        messages = []
        # 添加 system prompt
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})

        # 添加历史消息
        messages.extend(self.messages)

        # 自动迁移旧格式消息
        messages = self._sanitize_messages(messages)

        return messages

    def get_message_count(self) -> int:
        """获取当前消息数量"""
        return len(self.messages)

    def _maybe_compress(self):
        """
        基础压缩策略：
        当消息数超过阈值时，保留最近 N 条消息，
        将较早的消息压缩为一条摘要。
        """
        if len(self.messages) <= config.CONTEXT_COMPRESS_THRESHOLD:
            return

        logger.info(
            f"[ContextManager] Session {self.session_id}: "
            f"Messages count ({len(self.messages)}) exceeds threshold "
            f"({config.CONTEXT_COMPRESS_THRESHOLD}), compressing..."
        )

        # 保留最近的几条消息
        keep_recent = 6  # 保留最近 6 条（3 轮对话）
        messages_to_compress = self.messages[:-keep_recent]
        messages_to_keep = self.messages[-keep_recent:]

        # 将旧消息压缩为摘要
        summary = self._summarize_messages(messages_to_compress)
        
        # 用一条 system 消息替代旧消息
        self.messages = [
            {"role": "system", "content": f"[对话历史摘要] {summary}"}
        ] + messages_to_keep

        logger.info(
            f"[ContextManager] Compressed {len(messages_to_compress)} messages into summary. "
            f"Current messages: {len(self.messages)}"
        )

    def _summarize_messages(self, messages: List[Dict[str, str]]) -> str:
        """
        基础压缩 - 从消息中提取关键信息
        不调用 LLM，直接提取结构化摘要
        """
        user_topics = []
        tool_uses = []
        key_decisions = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "user":
                # 截取前 100 字符作为用户意图
                user_topics.append(content[:100])

            elif role == "tool":
                # 提取工具使用信息
                try:
                    tool_info = json.loads(content)
                    tool_uses.append(
                        f"{tool_info.get('tool_name', 'unknown')}"
                    )
                except (json.JSONDecodeError, TypeError):
                    pass

            elif role == "assistant":
                # 提取助手的关键回复
                if content and len(content) > 10:
                    key_decisions.append(content[:150])

        summary_parts = []
        if user_topics:
            summary_parts.append(f"用户讨论了: {'; '.join(user_topics[:5])}")
        if tool_uses:
            summary_parts.append(f"使用了工具: {', '.join(tool_uses)}")
        if key_decisions:
            summary_parts.append(f"关键回复: {'; '.join(key_decisions[:3])}")

        return " | ".join(summary_parts) if summary_parts else "之前的对话历史"

    def clear(self):
        """清空上下文"""
        self.messages = []
        self.total_turns = 0

    def get_context_stats(self) -> Dict[str, Any]:
        """获取上下文统计信息"""
        return {
            "session_id": self.session_id,
            "message_count": len(self.messages),
            "total_turns": self.total_turns,
            "needs_compression": len(self.messages) > config.CONTEXT_COMPRESS_THRESHOLD,
        }
