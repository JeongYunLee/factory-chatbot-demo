"""
FastAPI 앱 및 엔드포인트 모듈
"""
import os
import time
import asyncio
from typing import Optional
from contextlib import asynccontextmanager
from functools import lru_cache
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from langgraph.errors import GraphRecursionError
from core.models import GraphState
from core.state import get_session_history, generate_session_id, thread_safe_store
from core.execution_store import ExecutionResultStore


class MessageRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class FeedbackRequest(BaseModel):
    score: float
    run_id: str


class Settings(BaseSettings):
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    ALLOWED_ORIGINS: list = [
        "http://localhost:3000",
        "http://localhost:3001", 
        "https://localhost:3000",
        "https://localhost:3001",
        "http://labs.datahub.kr",
        "https://labs.datahub.kr",
        "http://localhost:8000",
        "https://localhost:8000",
        "http://localhost:86",
        "https://localhost:86",
    ]


@lru_cache()
def get_settings():
    return Settings()


def create_app(graph, execution_store):
    """FastAPI 앱 생성"""
    settings = get_settings()
    current_user_id = None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 시작 시
        print("🚀 서버 시작")
        yield
        # 종료 시
        print("🛑 서버 종료")

    app = FastAPI(
        title="Data Chatbot API",
        lifespan=lifespan,
        root_path="/projects/data-chatbot"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.post("/api/")
    async def stream_responses(request: Request):
        try:
            data = await request.json()
            message = data.get('message')
            client_session_id = data.get('session_id')
            
            if not message:
                raise HTTPException(status_code=400, detail="Message is required")
            
            # 검증만 strip()으로 체크하고, 실제 사용할 메시지는 원본 사용 (끝의 빈 스페이스 보존)
            if not message.strip():
                raise HTTPException(status_code=400, detail="Message cannot be empty")

            # 메시지 길이 제한
            if len(message) > 1000:
                raise HTTPException(status_code=400, detail="Message too long (max 1000 characters)")

            
            # 메시지 끝에 빈 스페이스가 없으면 추가 (마지막 글자 보호)
            if not message.endswith(' '):
                message = message + ' '
                print(f"🔒 메시지 끝에 보호 스페이스 추가: {repr(message[-5:])}")

            # 세션 ID 처리
            if not client_session_id:
                client_session_id = generate_session_id()

            # 설정 최적화
            from langchain_core.runnables import RunnableConfig
            config = RunnableConfig(
                recursion_limit=10,  # 재귀 제한 줄임
                configurable={
                    "thread_id": f"HIKE-FACTORY-CHATBOT-{client_session_id[:8]}", 
                    "user_id": current_user_id, 
                    "session_id": client_session_id
                }
            )

            # 원본 메시지 사용 (끝의 빈 스페이스 포함하여 마지막 글자 누락 방지)
            inputs = GraphState(
                question=message,  # 보호 스페이스가 추가된 메시지
                session_id=client_session_id,
                q_type='',
                context='',
                answer='',
                relevance='',
                execution_id=None,
            )

            try:
                # 타임아웃 설정으로 무한 대기 방지
                final_state = await asyncio.wait_for(
                    asyncio.to_thread(graph.invoke, inputs, config),
                    timeout=180  # 3분 타임아웃
                )
                
                answer_text = final_state["answer"]
                
                # 응답 검증
                if not answer_text or not isinstance(answer_text, str):
                    answer_text = "죄송합니다. 응답을 생성할 수 없습니다."
                
                # 세션 통계
                current_history = get_session_history(client_session_id)
                message_count = len(current_history.messages)
                
                print(f"✅ 세션 {client_session_id[:8]}... 응답 완료 (총 {message_count}개 메시지)")
                
                return {
                    "answer": answer_text,
                    "session_id": client_session_id,
                    "message_count": message_count,
                    "status": "success",
                    "execution_id": final_state.get("execution_id")
                }
                
            except asyncio.TimeoutError:
                print(f"⏰ 타임아웃: {client_session_id[:8]}...")
                return {
                    "answer": "죄송합니다. 응답 시간이 초과되었습니다. 다시 시도해 주세요.",
                    "session_id": client_session_id,
                    "status": "timeout"
                }
            except GraphRecursionError as e:
                print(f"🔄 재귀 제한 초과: {e}")
                return {
                    "answer": "죄송합니다. 질문이 너무 복잡합니다. 더 간단한 질문으로 다시 시도해 주세요.",
                    "session_id": client_session_id,
                    "status": "recursion_error"
                }
            except Exception as e:
                print(f"❌ 그래프 실행 오류: {type(e).__name__}: {str(e)[:200]}")
                return {
                    "answer": "죄송합니다. 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
                    "session_id": client_session_id,
                    "status": "error",
                    "error_type": type(e).__name__
                }

        except HTTPException:
            raise
        except Exception as e:
            print(f"❌ API 오류: {type(e).__name__}: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @app.get("/api/execution/{execution_id}")
    async def get_execution_result(execution_id: str):
        record = execution_store.get(execution_id)
        if not record:
            raise HTTPException(status_code=404, detail="Execution result not found")
        return record

    @app.post("/api/reset")
    async def reset_store(request: Request):
        try:
            data = await request.json()
            session_id_to_reset = data.get('session_id')

            if session_id_to_reset:
                # 특정 세션만 초기화
                message_count = thread_safe_store.clear_session(session_id_to_reset)
                # 해당 세션의 실행 결과도 함께 삭제
                execution_store.clear_session(session_id_to_reset)
                new_session_id = generate_session_id()

                print(f"🗑️ 세션 삭제: {session_id_to_reset[:8]}... ({message_count}개 메시지)")

                return {
                    "status": "Session reset successfully",
                    "session_id": new_session_id,
                    "cleared_messages": message_count
                }
            else:
                # 모든 세션 초기화
                total_sessions, total_messages = thread_safe_store.clear_session()
                # 모든 실행 결과 초기화
                execution_store.clear_session()
                new_session_id = generate_session_id()

                print(f"🧹 전체 초기화: {total_sessions}개 세션, {total_messages}개 메시지 삭제")

                return {
                    "status": "All sessions reset successfully",
                    "session_id": new_session_id,
                    "cleared_sessions": total_sessions,
                    "cleared_messages": total_messages
                }
                
        except Exception as e:
            print(f"❌ 리셋 오류: {e}")
            # 오류 발생시에도 새 세션 ID 반환
            new_session_id = generate_session_id()
            
            return {
                "status": "Sessions reset due to error",
                "session_id": new_session_id,
                "error": str(e)
            }

    @app.get("/health")
    async def health_check():
        stats = thread_safe_store.get_stats()
        return {
            "status": "healthy",
            "timestamp": time.time(),
            "sessions": stats['total_sessions'],
            "messages": stats['total_messages']
        }

    return app

