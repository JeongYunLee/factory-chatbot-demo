"""
Factory Chatbot Main Entry Point
모든 모듈을 통합하여 실행하는 메인 파일
"""
import os
import pandas as pd
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import uvicorn

# 환경변수 로드
load_dotenv(override=True)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables")

# 모델 초기화
model = ChatOpenAI(
    openai_api_key=OPENAI_API_KEY,
    model="gpt-5.1-2025-11-13",
    temperature=0
)

# 데이터 로드
df = pd.read_csv('data/cleaned_전국공장등록현황_preprocessed_seoul.csv')

# 모듈 import
from core.router import create_router
from core.code_executor import create_code_tools
from core.agent import create_agent
from core.workflow import create_workflow
from core.execution_store import ExecutionResultStore
from core.api import create_app

# Router 생성
router, router_conditional_edge = create_router(model)

# 코드 도구 생성
tools = create_code_tools(model, df)

# 실행 결과 저장소 생성 (model 전달)
execution_store = ExecutionResultStore(model=model)

# Agent 생성
agent = create_agent(model, tools, execution_store)

# 워크플로우 그래프 생성
graph = create_workflow(router, agent)

# FastAPI 앱 생성
app = create_app(graph, execution_store)

if __name__ == "__main__":
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        workers=1,  # 단일 워커로 메모리 공유 문제 방지
        timeout_keep_alive=30,
        limit_concurrency=100,  # 동시 연결 제한
        limit_max_requests=1000  # 최대 요청 수 제한
    )
