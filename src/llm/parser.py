"""
LLM 输出解析器 - 从 LLM 响应中提取思考过程、工具调用或最终答案

解析策略:
1. 检查是否有 tool_calls -> 工具调用模式
2. 检查 content 中是否有结构化思考标记 -> 提取思考过程
3. 否则视为最终答案
"""
import json
import re
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from src.utils.logger import logger


@dataclass
class AgentAction:
    """表示一次工具调用决策"""
    tool_name: str
    tool_arguments: Dict[str, Any]
    thought: str = ""  # Agent 的思考过程


@dataclass
class AgentFinish:
    """表示 Agent 决定直接给出最终答案"""
    answer: str
    thought: str = ""  # Agent 的思考过程


@dataclass
class AgentResponse:
    """Agent 一次循环的完整响应"""
    action: Optional[AgentAction] = None
    finish: Optional[AgentFinish] = None
    raw_content: str = ""
    raw_tool_calls: Optional[List[Dict[str, Any]]] = None
    thinking_process: str = ""  # 记录思考过程


class LLMOutputParser:
    """
    解析 LLM 的输出，判断是工具调用还是最终回复
    
    主要策略:
    - 优先解析 OpenAI 格式的 tool_calls
    - Fallback: 解析文本中的 JSON 工具调用
    - 最后 fallback: 视为最终答案
    """

    def __init__(self):
        # 用于 fallback 解析的正则模式
        self._tool_call_pattern = re.compile(
            r'```tool_call\s*\n(.*?)\n```',
            re.DOTALL
        )
        self._thinking_pattern = re.compile(
            r'<thinking>(.*?)</thinking>',
            re.DOTALL
        )

    def parse(self, llm_response: Dict[str, Any]) -> AgentResponse:
        """
        解析 LLM 响应

        Args:
            llm_response: LLM 返回的字典，格式:
                {
                    "role": "assistant",
                    "content": "...",
                    "tool_calls": [...] or None,
                    "finish_reason": "stop" | "tool_calls",
                }

        Returns:
            AgentResponse 对象
        """
        content = llm_response.get("content", "") or ""
        tool_calls = llm_response.get("tool_calls")
        finish_reason = llm_response.get("finish_reason", "stop")

        response = AgentResponse(
            raw_content=content,
            raw_tool_calls=tool_calls,
        )

        # 1. 提取思考过程
        thinking = self._extract_thinking(content)
        response.thinking_process = thinking

        # 2. 优先解析 tool_calls (OpenAI 格式)
        if tool_calls and len(tool_calls) > 0:
            return self._parse_tool_calls(tool_calls, thinking, response)

        # 3. Fallback: 尝试从文本中解析工具调用
        if self._tool_call_pattern.search(content):
            return self._parse_text_tool_call(content, thinking, response)

        # 4. 视为最终答案
        clean_answer = self._remove_thinking_tags(content)
        response.finish = AgentFinish(
            answer=clean_answer.strip() if clean_answer.strip() else content,
            thought=thinking,
        )
        return response

    def _extract_thinking(self, content: str) -> str:
        """从内容中提取思考过程"""
        match = self._thinking_pattern.search(content)
        return match.group(1).strip() if match else ""

    def _remove_thinking_tags(self, content: str) -> str:
        """移除 <thinking> 标签及其内容"""
        return self._thinking_pattern.sub("", content).strip()

    def _parse_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
        thinking: str,
        response: AgentResponse,
    ) -> AgentResponse:
        """解析 OpenAI 格式的 tool_calls"""
        # 取第一个 tool call
        tc = tool_calls[0]
        func = tc.get("function", {})
        tool_name = func.get("name", "")
        arguments_raw = func.get("arguments", "{}")

        # 解析参数 JSON
        try:
            if isinstance(arguments_raw, str):
                arguments = json.loads(arguments_raw)
            else:
                arguments = arguments_raw
        except json.JSONDecodeError:
            arguments = {}
            logger.warning(f"Failed to parse tool arguments: {arguments_raw}")

        response.action = AgentAction(
            tool_name=tool_name,
            tool_arguments=arguments,
            thought=thinking,
        )
        return response

    def _parse_text_tool_call(
        self,
        content: str,
        thinking: str,
        response: AgentResponse,
    ) -> AgentResponse:
        """从文本中解析 ```tool_call``` 块（fallback）"""
        match = self._tool_call_pattern.search(content)
        if not match:
            # 没有找到，视为最终答案
            response.finish = AgentFinish(answer=content, thought=thinking)
            return response

        try:
            call_data = json.loads(match.group(1).strip())
            response.action = AgentAction(
                tool_name=call_data.get("tool_name", ""),
                tool_arguments=call_data.get("arguments", {}),
                thought=thinking,
            )
        except json.JSONDecodeError:
            # 解析失败，视为最终答案
            response.finish = AgentFinish(answer=content, thought=thinking)

        return response
