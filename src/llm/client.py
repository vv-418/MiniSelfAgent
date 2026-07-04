"""
LLM 客户端 - 封装 OpenAI 兼容接口调用
"""
import json
from typing import List, Dict, Any, Optional
import openai

import config
from src.utils.logger import logger


class LLMClient:
    """
    LLM API 客户端
    使用 openai 库调用 OpenAI 兼容接口
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or config.LLM_API_KEY
        self.base_url = base_url or config.LLM_BASE_URL
        self.model = model or config.LLM_MODEL

        self.client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )
        logger.info(f"LLM Client initialized: model={self.model}, base_url={self.base_url}")

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        调用 LLM chat completions API
        
        Args:
            messages: 消息列表
            temperature: 温度
            max_tokens: 最大 token 数
            tools: 工具定义列表 (OpenAI function calling 格式)
        
        Returns:
            LLM 的原始响应字典
        """
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or config.LLM_TEMPERATURE,
            "max_tokens": max_tokens or config.LLM_MAX_TOKENS,
        }

        if tools:
            kwargs["tools"] = tools

        try:
            response = self.client.chat.completions.create(**kwargs)
            # 转换为字典格式
            return self._parse_response(response)
        except openai.AuthenticationError as e:
            logger.error(f"LLM API Authentication Error: {e}")
            raise
        except openai.RateLimitError as e:
            logger.error(f"LLM API Rate Limit Error: {e}")
            raise
        except Exception as e:
            logger.error(f"LLM API Error: {e}")
            raise

    def _parse_response(self, response) -> Dict[str, Any]:
        """将 openai response 对象解析为字典"""
        choice = response.choices[0]
        message = choice.message

        result = {
            "role": "assistant",
            "content": message.content or "",
            "finish_reason": choice.finish_reason,
            "tool_calls": None,
        }

        # 解析 tool calls
        if message.tool_calls:
            result["tool_calls"] = []
            for tc in message.tool_calls:
                result["tool_calls"].append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                })

        return result
