import threading
import uuid
from typing import TypedDict

from langchain_community.chat_message_histories import ChatMessageHistory


class GraphState(TypedDict):
    question: str  # 질문
    q_type: str  # 질문의 유형
    answer: str | list[str]  # llm이 생성한 답변
    session_id: str  # 세션 ID
    context: str | None  # 검색 컨텍스트
    relevance: str | None  # 검색 적합도
    execution_id: str | None  # 실행 결과 식별자


class ThreadSafeStore:
    """
    세션별 대화 히스토리를 스레드 안전하게 관리하는 스토어
    """

    def __init__(self):
        self._store: dict[str, ChatMessageHistory] = {}
        self._lock = threading.RLock()  # 재진입 가능한 락

    def get_session_history(self, session_id: str) -> ChatMessageHistory:
        with self._lock:
            if session_id not in self._store:
                self._store[session_id] = ChatMessageHistory()
            return self._store[session_id]

    def clear_session(self, session_id: str | None = None):
        with self._lock:
            if session_id:
                if session_id in self._store:
                    message_count = len(self._store[session_id].messages)
                    del self._store[session_id]
                    return message_count
                return 0
            else:
                total_sessions = len(self._store)
                total_messages = sum(len(history.messages) for history in self._store.values())
                self._store.clear()
                return total_sessions, total_messages

    def get_stats(self):
        with self._lock:
            return {
                "total_sessions": len(self._store),
                "total_messages": sum(len(history.messages) for history in self._store.values()),
            }


# 전역 스레드 안전 저장소
thread_safe_store = ThreadSafeStore()


def get_session_history(session_id: str) -> ChatMessageHistory:
    """
    세션 ID를 기반으로 세션 기록을 가져오는 함수
    """
    return thread_safe_store.get_session_history(session_id)


def generate_session_id() -> str:
    """
    새로운 세션 ID 생성 함수
    """
    return str(uuid.uuid4())


__all__ = [
    "GraphState",
    "ThreadSafeStore",
    "thread_safe_store",
    "get_session_history",
    "generate_session_id",
]


