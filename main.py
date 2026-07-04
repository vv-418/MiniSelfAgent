"""
MiniSelfAgent - 主入口

支持两种模式:
1. CLI 模式 (交互式终端)
2. 模块模式 (供外部调用)

从零实现的最小可用 Agent，不依赖任何现有 Agent 框架。
"""
import sys
import os
import argparse

# 将项目根目录添加到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.agent import AgentRuntime
from src.session.manager import SessionManager
from src.utils.logger import logger


def print_banner():
    """打印欢迎信息"""
    print("=" * 60)
    print("  🤖 MiniSelfAgent - 从零实现的最小可用 Agent")
    print("=" * 60)
    print("  支持工具: calculator / search / todo")
    print("  输入 'quit' 或 'exit' 退出")
    print("  输入 'new' 创建新 Session")
    print("  输入 'switch <id>' 切换到已有 Session")
    print("  输入 'sessions' 查看所有 Session")
    print("=" * 60)
    print()


def print_result(result: dict, verbose: bool = False):
    """格式化输出 Agent 结果"""
    print()
    print("-" * 50)

    if verbose and result.get("thinking"):
        print("💭 思考过程:")
        print(f"   {result['thinking'][:200]}")
        print()

    if result.get("tool_calls"):
        print(f"🔧 使用了 {len(result['tool_calls'])} 个工具:")
        for tc in result["tool_calls"]:
            print(f"   - {tc['tool']}({tc['arguments']})")
        print()

    print(f"🤖 Agent 回答:")
    print(f"   {result['response']}")
    print(f"\n   [Session: {result['session_id']} | 轮次: {result['iterations']}]")
    print("-" * 50)
    print()


def cli_mode(verbose: bool = False, initial_session_id: str = None):
    """交互式 CLI 模式"""
    print_banner()

    runtime = AgentRuntime()
    current_session = None

    while True:
        try:
            user_input = input("\n👤 You: ").strip()

            if not user_input:
                continue

            # 特殊命令
            cmd = user_input.lower()

            if cmd in ("quit", "exit", "q"):
                print("\n👋 再见！")
                break

            if cmd == "new":
                session = runtime.session_manager.create_session()
                current_session = session.session_id
                print(f"\n✅ 新 Session 已创建: {current_session}")
                continue

            if cmd == "sessions":
                sessions = runtime.session_manager.list_sessions()
                if not sessions:
                    print("\n📭 没有活跃的 Session")
                else:
                    print("\n📋 活跃 Sessions:")
                    for s in sessions:
                        marker = " ← 当前" if s["session_id"] == current_session else ""
                        topic = s.get("last_topic", "")
                        topic_display = f" | 💬 {topic}" if topic else ""
                        print(
                            f"   [{s['session_id']}] msgs={s['message_count']}{topic_display}{marker}"
                        )
                continue

            # switch <id> - 切换到指定 session
            if cmd.startswith("switch "):
                target_id = cmd.split(" ", 1)[1].strip()
                session_obj = runtime.session_manager.get_session(target_id)
                if session_obj is None:
                    print(f"\n❌ Session {target_id} 不存在或已过期")
                    sessions = runtime.session_manager.list_sessions()
                    if sessions:
                        print("   可用 Session:")
                        for s in sessions:
                            print(f"     [{s['session_id']}]")
                else:
                    current_session = target_id
                    msg_count = session_obj.context.get_message_count() if session_obj.context else 0
                    print(f"\n✅ 已切换到 Session: {target_id} (共 {msg_count} 条消息)")
                continue

            # 如果还没有 session，尝试恢复或自动创建
            if current_session is None:
                if initial_session_id:
                    # 尝试恢复指定 session
                    session_obj = runtime.session_manager.get_session(initial_session_id)
                    if session_obj:
                        current_session = initial_session_id
                        msg_count = session_obj.context.get_message_count() if session_obj.context else 0
                        print(f"   (已恢复 Session: {current_session}, 共 {msg_count} 条消息)")
                    else:
                        print(f"   ⚠️ Session {initial_session_id} 不存在或已过期，将创建新 Session")
                        session = runtime.session_manager.create_session()
                        current_session = session.session_id
                        print(f"   (已创建新 Session: {current_session})")
                    initial_session_id = None  # 只在首次尝试恢复
                else:
                    session = runtime.session_manager.create_session()
                    current_session = session.session_id
                    print(f"   (已自动创建 Session: {current_session})")

            # 调用 Agent
            result = runtime.chat(current_session, user_input)
            print_result(result, verbose=verbose)

        except KeyboardInterrupt:
            print("\n\n👋 再见！")
            break
        except Exception as e:
            logger.error(f"CLI error: {e}")
            print(f"\n❌ 错误: {e}")


def main():
    """主入口"""
    parser = argparse.ArgumentParser(description="MiniSelfAgent - 从零实现的最小可用 Agent")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示详细信息（思考过程等）")
    parser.add_argument("--model", type=str, default=None, help="指定 LLM 模型")
    parser.add_argument("--api-key", type=str, default=None, help="指定 API Key")
    parser.add_argument("--base-url", type=str, default=None, help="指定 API Base URL")
    parser.add_argument("--session", type=str, default=None, help="恢复指定 Session ID")

    args = parser.parse_args()

    # 覆盖配置
    if args.model:
        import config
        config.LLM_MODEL = args.model
    if args.api_key:
        import config
        config.LLM_API_KEY = args.api_key
    if args.base_url:
        import config
        config.LLM_BASE_URL = args.base_url

    cli_mode(verbose=args.verbose, initial_session_id=args.session)


if __name__ == "__main__":
    main()
