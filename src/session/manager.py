"""
Session 管理器 - 实现多窗口独立会话

每个窗口（会话）拥有独立的:
  - session_id
  - context (消息历史)
  - todo 待办列表
  - tool 执行历史
"""
import os
import json
import uuid
import time
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field

import config
from src.utils.logger import logger
from src.utils.context_manager import ContextManager
from src.tools.todo import TodoTool


@dataclass
class Session:
    """一个独立的会话"""
    session_id: str
    user_id: str
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    context: Optional[ContextManager] = None
    todo_tool: Optional[TodoTool] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        return (time.time() - self.last_active) > config.SESSION_EXPIRY_SECONDS

    def touch(self):
        """更新最后活跃时间"""
        self.last_active = time.time()


class SessionManager:
    """
    Session 管理器 - 管理所有活跃会话

    - 每个窗口创建时分配唯一 session_id
    - 支持按 session_id 获取/创建/删除会话
    - 支持持久化到磁盘
    """

    def __init__(self):
        self._sessions: Dict[str, Session] = {}
        os.makedirs(config.SESSION_STORAGE_DIR, exist_ok=True)
        # 启动时恢复持久化的 session
        self._load_all_sessions()

    def create_session(self, user_id: str = "default") -> Session:
        """
        创建新会话

        Args:
            user_id: 用户标识

        Returns:
            新创建的 Session 对象
        """
        session_id = str(uuid.uuid4())[:8]  # 短 ID，便于展示
        context = ContextManager(session_id=session_id)
        todo_tool = TodoTool(session_id=session_id)

        session = Session(
            session_id=session_id,
            user_id=user_id,
            context=context,
            todo_tool=todo_tool,
        )

        self._sessions[session_id] = session
        logger.info(f"Session created: {session_id} (user={user_id})")
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """获取指定 session，如果过期则返回 None"""
        session = self._sessions.get(session_id)
        if session is None:
            logger.warning(f"Session not found: {session_id}")
            return None
        if session.is_expired():
            logger.warning(f"Session expired: {session_id}")
            self.delete_session(session_id)
            return None
        session.touch()
        return session

    def list_sessions(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出所有活跃会话"""
        sessions = []
        for s in self._sessions.values():
            if user_id and s.user_id != user_id:
                continue
            if s.is_expired():
                continue
            # 提取最后一条用户消息作为话题摘要
            last_topic = ""
            if s.context and s.context.messages:
                for msg in reversed(s.context.messages):
                    if msg.get("role") == "user":
                        last_topic = msg["content"][:50]
                        break

            sessions.append({
                "session_id": s.session_id,
                "user_id": s.user_id,
                "created_at": s.created_at,
                "last_active": s.last_active,
                "message_count": s.context.get_message_count() if s.context else 0,
                "last_topic": last_topic,
            })
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """删除指定 session"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            # 同时删除磁盘上的持久化文件
            persistence_file = os.path.join(
                config.SESSION_STORAGE_DIR, f"{session_id}.json"
            )
            if os.path.exists(persistence_file):
                os.remove(persistence_file)
            logger.info(f"Session deleted: {session_id}")
            return True
        return False

    def save_session(self, session: Session):
        """将 session 持久化到磁盘"""
        persistence_file = os.path.join(
            config.SESSION_STORAGE_DIR, f"{session.session_id}.json"
        )
        data = {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "created_at": session.created_at,
            "last_active": session.last_active,
            "metadata": session.metadata,
            "messages": session.context.messages if session.context else [],
        }
        with open(persistence_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_all_sessions(self):
        """从磁盘恢复所有未过期的 session"""
        if not os.path.exists(config.SESSION_STORAGE_DIR):
            return

        for filename in os.listdir(config.SESSION_STORAGE_DIR):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(config.SESSION_STORAGE_DIR, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                session = Session(
                    session_id=data["session_id"],
                    user_id=data.get("user_id", "default"),
                    created_at=data.get("created_at", 0),
                    last_active=data.get("last_active", 0),
                    context=ContextManager(session_id=data["session_id"]),
                    todo_tool=TodoTool(session_id=data["session_id"]),
                    metadata=data.get("metadata", {}),
                )

                # 恢复消息历史
                if session.context and data.get("messages"):
                    session.context.messages = data["messages"]

                if not session.is_expired():
                    self._sessions[session.session_id] = session
                    logger.info(f"Session restored: {session.session_id}")
                else:
                    os.remove(filepath)  # 清理过期 session 文件
            except Exception as e:
                logger.error(f"Failed to load session {filename}: {e}")
