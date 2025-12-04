import threading
import uuid

from langchain_community.chat_message_histories import ChatMessageHistory


class ThreadSafeStore:
    """
    세션별 대화 히스토리를 스레드 안전하게 관리하는 스토어
    """

    def __init__(self):
        self._store: dict[str, ChatMessageHistory] = {}
        self._lock = threading.RLock()  

    def get_session_history(self, session_id: str) -> ChatMessageHistory:
        with self._lock:
            if session_id not in self._store:
                self._store[session_id] = ChatMessageHistory()
            return self._store[session_id]


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
    "get_session_history",
    "generate_session_id",
]


