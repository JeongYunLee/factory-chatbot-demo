import threading
import time
import uuid
from typing import TypedDict

from datetime import datetime, date

from langchain_community.chat_message_histories import ChatMessageHistory

from visualization import serialize_execution_output


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
                print(f"🆕 새로운 세션 히스토리 생성: {session_id[:8]}...")
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


class ExecutionResultStore:
    """
    세션별 실행 결과를 저장하는 스토어
    - key: execution_id
    - value: { execution_id, session_id, code, result, created_at }
    - 별도 인덱스로 session_id -> [execution_id, ...] 관리
    """

    def __init__(self):
        self._store: dict[str, dict] = {}
        self._session_index: dict[str, set[str]] = {}  # session_id -> set(execution_id)
        self._lock = threading.RLock()

    def save(self, session_id: str, code: str | None, output, question: str = "") -> str:
        execution_id = str(uuid.uuid4())
        payload = {
            "execution_id": execution_id,
            "session_id": session_id,
            "code": code,
            "result": serialize_execution_output(output, question),
            "created_at": time.time(),
        }
        with self._lock:
            self._store[execution_id] = payload
            # 세션별 인덱스에 execution_id 등록
            if session_id not in self._session_index:
                self._session_index[session_id] = set()
            self._session_index[session_id].add(execution_id)
        return execution_id

    def get(self, execution_id: str):
        with self._lock:
            return self._store.get(execution_id)

    def clear_session(self, session_id: str | None = None):
        """
        특정 session_id에 해당하는 execution 결과만 삭제하거나,
        session_id가 없으면 전체 실행 결과를 삭제.
        """
        with self._lock:
            if session_id is None:
                self._store.clear()
                self._session_index.clear()
                return

            exec_ids = self._session_index.get(session_id)
            if not exec_ids:
                return

            for eid in exec_ids:
                self._store.pop(eid, None)
            self._session_index.pop(session_id, None)


execution_store = ExecutionResultStore()


__all__ = [
    "GraphState",
    "ThreadSafeStore",
    "thread_safe_store",
    "get_session_history",
    "generate_session_id",
    "ExecutionResultStore",
    "execution_store",
]


