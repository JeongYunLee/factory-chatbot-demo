"""
실행 결과 저장소
"""
import uuid
import threading
import time
from typing import Optional
from core.utils import serialize_execution_output


class ExecutionResultStore:
    """
    세션별 실행 결과를 저장하는 스토어
    - key: execution_id
    - value: { execution_id, session_id, code, result, created_at }
    - 별도 인덱스로 session_id -> [execution_id, ...] 관리
    """

    def __init__(self, model=None):
        self._store = {}
        self._session_index = {}  # session_id -> set(execution_id)
        self._lock = threading.RLock()
        self.model = model

    def save(self, session_id: str, code: Optional[str], output, question: str = ""):
        execution_id = str(uuid.uuid4())
        payload = {
            "execution_id": execution_id,
            "session_id": session_id,
            "code": code,
            "result": serialize_execution_output(output, question, self.model),
            "created_at": time.time()
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

    def clear_session(self, session_id: Optional[str] = None):
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

