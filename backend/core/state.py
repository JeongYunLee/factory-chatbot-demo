"""
상태 관리 및 세션 관리
"""
import uuid
import threading
from langchain_community.chat_message_histories import ChatMessageHistory


class ThreadSafeStore:
    """스레드 안전한 세션 히스토리 저장소"""
    def __init__(self):
        self._store = {}
        self._lock = threading.RLock()  # 재진입 가능한 락
    
    def get_session_history(self, session_id: str):
        with self._lock:
            if session_id not in self._store:
                self._store[session_id] = ChatMessageHistory()
                print(f"🆕 새로운 세션 히스토리 생성: {session_id[:8]}...")
            return self._store[session_id]
    
    def clear_session(self, session_id: str = None):
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
                'total_sessions': len(self._store),
                'total_messages': sum(len(history.messages) for history in self._store.values())
            }


# 전역 스레드 안전 저장소
thread_safe_store = ThreadSafeStore()


def get_session_history(session_ids):
    """세션 ID를 기반으로 세션 기록을 가져오는 함수"""
    return thread_safe_store.get_session_history(session_ids)


def generate_session_id():
    """새로운 세션 ID 생성 함수"""
    return str(uuid.uuid4())

