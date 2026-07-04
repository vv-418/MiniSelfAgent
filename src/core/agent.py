"""
Core Agent Runtime - 从零实现的 Agent 循环引擎

基本循环步骤:
  Step 1: 接收用户输入
  Step 2: 判断是直接回复，还是调用工具
  Step 3: 调用工具
  Step 4: 根据工具结果判断是继续 loop，还是返回结果给用户

不依赖任何现有 agent 框架，核心运行时完全自行实现。
"""
import time
import json
from typing import Optional, Dict, Any, List

import config
from src.utils.logger import logger, tool_tracer
from src.utils.context_manager import ContextManager
from src.utils.prompt_loader import render_prompt, load_prompt
from src.llm.client import LLMClient
from src.llm.parser import LLMOutputParser, AgentResponse
from src.tools.base import ToolRegistry
from src.tools.calculator import CalculatorTool
from src.tools.search import SearchTool
from src.tools.todo import TodoTool
from src.session.manager import Session, SessionManager


# ============================================================
# System Prompt — 从 prompts/system_prompt.md 加载
# ============================================================
# 硬编码的默认值，仅在 prompts/system_prompt.md 缺失时使用
_DEFAULT_SYSTEM_PROMPT = """你是一个智能助手 (MiniSelfAgent)，能够使用工具帮助用户完成任务。

## 你可以使用的工具:
{tools_description}

## 工具使用规则:
1. 当你需要计算、搜索信息、或管理待办事项时，请调用相应的工具。
2. 调用工具后，你会收到工具的执行结果，请根据结果继续回答用户。
3. 如果一次工具调用不能完全解决问题，你可以多次调用工具。
4. 当你已经获得了足够的信息，可以直接给出最终答案，不需要再调用工具。

## 回答规范:
- 如果你需要调用工具，请直接使用 function calling 机制。
- 如果你已经有足够的信息可以直接回答，请直接输出答案。
- 回答请简洁、清晰、有帮助。
- 使用中文回答。

当前时间: {current_time}
当前 Session ID: {session_id}
"""


class AgentRuntime:
    """
    Agent 核心运行时

    职责:
    - 协调 LLM、工具系统、上下文管理
    - 执行 ReAct 循环 (Reasoning + Acting)
    - 管理 Session 和 Context
    """

    def __init__(self):
        # 初始化组件
        self.llm_client = LLMClient()
        self.parser = LLMOutputParser()
        self.session_manager = SessionManager()
        self.tool_registry = self._init_tools()

        # 当前活跃的 session_id -> TodoTool 映射（每个 session 独立的 todo）
        self._session_todos: Dict[str, TodoTool] = {}

        logger.info("Agent Runtime initialized successfully")

    def _init_tools(self) -> ToolRegistry:
        """初始化并注册所有工具"""
        registry = ToolRegistry()
        registry.register(CalculatorTool())
        registry.register(SearchTool())
        # TodoTool 需要 session_id，这里注册一个默认的，实际执行时会替换
        registry.register(TodoTool(session_id="default"))
        logger.info(f"Registered tools: {registry.list_tools()}")
        return registry

    def _get_session_todo_tool(self, session_id: str) -> TodoTool:
        """获取指定 session 的 TodoTool 实例"""
        if session_id not in self._session_todos:
            self._session_todos[session_id] = TodoTool(session_id=session_id)
        return self._session_todos[session_id]

    def _build_system_prompt(self, session: Session) -> str:
        """构建系统提示词 — 优先从 prompts/system_prompt.md 加载"""
        tools_desc = "\n".join([
            f"- **{t.name}**: {t.description}"
            for t in self.tool_registry._tools.values()
        ])

        return render_prompt(
            "system_prompt.md",
            variables={
                "tools_description": tools_desc,
                "current_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "session_id": session.session_id,
            },
            fallback=_DEFAULT_SYSTEM_PROMPT.format(
                tools_description=tools_desc,
                current_time=time.strftime("%Y-%m-%d %H:%M:%S"),
                session_id=session.session_id,
            ),
        )

    def chat(self, session_id: str, user_input: str) -> Dict[str, Any]:
        """
        主入口 - 处理用户输入并返回 Agent 响应

        Args:
            session_id: 会话 ID
            user_input: 用户输入文本

        Returns:
            {
                "session_id": str,
                "response": str,          # 最终回答
                "thinking": str,          # 思考过程
                "tool_calls": [...],      # 工具调用记录
                "iterations": int,        # 循环次数
            }
        """
        # 1. 获取或创建 session
        session = self.session_manager.get_session(session_id)
        if session is None:
            logger.error(f"Session {session_id} not found or expired")
            return {
                "session_id": session_id,
                "response": f"Error: Session {session_id} not found. Please create a new session.",
                "thinking": "",
                "tool_calls": [],
                "iterations": 0,
            }

        # 2. 设置系统提示词
        system_prompt = self._build_system_prompt(session)
        session.context.set_system_prompt(system_prompt)

        # 3. 添加用户消息到 context
        session.context.add_user_message(user_input)

        # 4. 执行 Agent 循环
        result = self._run_agent_loop(session)

        # 5. 持久化 session
        self.session_manager.save_session(session)

        return result

    def _run_agent_loop(self, session: Session) -> Dict[str, Any]:
        """
        Agent 核心循环 (ReAct Loop)

        循环步骤:
        1. 将 context 发送给 LLM
        2. 解析 LLM 输出
        3. 如果是工具调用 -> 执行工具 -> 将结果加入 context -> 继续循环
        4. 如果是最终回答 -> 返回结果

        最大循环次数由 config.MAX_LOOP_ITERATIONS 控制
        """
        tool_call_history = []
        thinking_parts = []
        final_response = ""
        iterations = 0

        for i in range(config.MAX_LOOP_ITERATIONS):
            iterations = i + 1
            logger.info(f"[AgentLoop] Iteration {iterations}/{config.MAX_LOOP_ITERATIONS}")

            # 获取当前 context
            messages = session.context.get_messages_for_llm()

            # 获取工具 schemas
            tool_schemas = self.tool_registry.get_schemas()

            # 调用 LLM
            start_time = time.time()
            try:
                llm_response = self.llm_client.chat(
                    messages=messages,
                    tools=tool_schemas,
                )
            except Exception as e:
                logger.error(f"LLM call failed: {e}")
                final_response = f"抱歉，AI 服务暂时不可用，请稍后重试。错误: {str(e)}"
                break

            llm_duration = (time.time() - start_time) * 1000
            logger.info(f"[AgentLoop] LLM responded in {llm_duration:.0f}ms")

            # 解析 LLM 输出
            parsed: AgentResponse = self.parser.parse(llm_response)

            # 记录思考过程
            if parsed.thinking_process:
                thinking_parts.append(parsed.thinking_process)

            # === 情况 A: LLM 决定调用工具 ===
            if parsed.action:
                tool_name = parsed.action.tool_name
                tool_args = parsed.action.tool_arguments
                tool_call_id = f"call_{i}"

                logger.info(f"[AgentLoop] Tool call: {tool_name}({json.dumps(tool_args, ensure_ascii=False)})")

                # --- 特殊处理：TodoTool 需要 session 独立 ---
                if tool_name == "todo":
                    todo_tool = self._get_session_todo_tool(session.session_id)
                    trace_start = time.time()
                    try:
                        result_str = todo_tool.execute(**tool_args)
                        error = None
                    except Exception as e:
                        result_str = f"Error: {e}"
                        error = str(e)
                    duration_ms = (time.time() - trace_start) * 1000
                else:
                    # 通用工具执行
                    trace_start = time.time()
                    result_str = self.tool_registry.execute(tool_name, tool_args)
                    duration_ms = (time.time() - trace_start) * 1000
                    error = None if not result_str.startswith("Error:") else result_str

                # 记录 trace
                tool_tracer.record(
                    tool_name=tool_name,
                    arguments=tool_args,
                    result=result_str,
                    duration_ms=duration_ms,
                    error=error,
                    session_id=session.session_id,
                )

                # 构建 assistant 消息（tool_calls 作为顶层字段）
                assistant_tool_calls = [{
                    "id": tool_call_id,
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": json.dumps(tool_args, ensure_ascii=False),
                    }
                }]
                session.context.add_assistant_message(
                    content=parsed.raw_content or "",
                    tool_calls=assistant_tool_calls,
                )

                # 将工具结果加入 context
                session.context.add_tool_result(
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    result=result_str,
                )

                tool_call_history.append({
                    "tool": tool_name,
                    "arguments": tool_args,
                    "result": result_str[:500],
                    "duration_ms": round(duration_ms, 2),
                })

                # 继续循环 —— LLM 将基于工具结果决定下一步

            # === 情况 B: LLM 给出最终回答 ===
            elif parsed.finish:
                final_response = parsed.finish.answer
                # 将最终回答加入 context
                session.context.add_assistant_message(final_response)
                logger.info(f"[AgentLoop] Final answer reached after {iterations} iterations")
                break

            # === 情况 C: 异常状态 ===
            else:
                final_response = parsed.raw_content or "抱歉，我无法处理这个请求。"
                session.context.add_assistant_message(final_response)
                logger.warning(f"[AgentLoop] Unexpected state at iteration {iterations}")
                break

        else:
            # 达到最大循环次数
            final_response = (
                f"已达到最大处理轮次 ({config.MAX_LOOP_ITERATIONS})，"
                f"以下是目前的处理结果。\n{final_response or '未能得出最终答案。'}"
            )
            logger.warning(f"[AgentLoop] Max iterations ({config.MAX_LOOP_ITERATIONS}) reached")
            session.context.add_assistant_message(final_response)

        return {
            "session_id": session.session_id,
            "response": final_response,
            "thinking": "\n".join(thinking_parts),
            "tool_calls": tool_call_history,
            "iterations": iterations,
        }
