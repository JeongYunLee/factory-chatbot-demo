import uuid, os, io, sys, time, json
import asyncio
import threading
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from typing import TypedDict, Annotated
import pandas as pd
import numpy as np
from functools import wraps

from openai import OpenAI
from langchain_openai import ChatOpenAI
# import chromadb
# from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

from langchain_community.tools.tavily_search import TavilySearchResults

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import GraphRecursionError

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.output_parsers.openai_tools import JsonOutputToolsParser
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.prompts import PromptTemplate
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableConfig  
from langchain_core.output_parsers import StrOutputParser

from langchain_community.chat_message_histories import ChatMessageHistory, StreamlitChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langgraph.graph.message import add_messages
from operator import itemgetter

from langchain.agents import tool
from langchain.agents import create_tool_calling_agent
from langchain.agents import AgentExecutor

# from langchain_teddynote import logging
from langsmith import traceable
import threading

# 환경변수 로드
load_dotenv(override=True)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables")

# 모델
model = ChatOpenAI(
    openai_api_key=OPENAI_API_KEY,
    model="gpt-5.1-2025-11-13",
    temperature=0
)

df = pd.read_csv('data/cleaned_전국공장등록현황_preprocessed_seoul.csv')

###################################################################################################

class GraphState(TypedDict):
    question: str  # 질문
    q_type: str  # 질문의 유형
    answer: str | list[str]  # llm이 생성한 답변
    session_id: str  # 세션 ID
    context: str | None  # 검색 컨텍스트
    relevance: str | None  # 검색 적합도

# 🔧 개선 1: 스레드 안전한 저장소
import threading
from collections import defaultdict

class ThreadSafeStore:
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

# 세션 ID를 기반으로 세션 기록을 가져오는 함수
def get_session_history(session_ids):
    return thread_safe_store.get_session_history(session_ids)

# 새로운 세션 ID 생성 함수
def generate_session_id():
    return str(uuid.uuid4())

#######################################################################
############################ nodes: Router ############################
#######################################################################

class Router(BaseModel):
    type: str = Field(description="type of the query that model choose. Choose from ['general', 'domain_specific']")

router_output_parser = JsonOutputParser(pydantic_object=Router)
router_format_instructions = router_output_parser.get_format_instructions()

router_prompt = PromptTemplate(
    template="""
            You are an expert who classifies the type of question. There are two query types: ['general', 'domain_specific']

            [general]
            Questions unrelated to data query, such as translating English to Korean, asking for general knowledge (e.g., "What is the capital of South Korea?"), or queries that can be answered through a web search.

            [domain_specific]
            Questions related to 'factory' domain and data query, such as 'count the unique values of factories in Seoul', or count 'the number of rows in a table'.

            <Output format>: Always respond with either "general" or "domain_specific" and nothing else. {format_instructions}
            <chat_history>: {chat_history}
            
            <Question>: {query} 
            """,
    input_variables=["query", "chat_history"],
    partial_variables={"format_instructions": router_format_instructions},
)

def router(state: GraphState) -> GraphState:
    chain = router_prompt | model | router_output_parser
    
    router_with_history  = RunnableWithMessageHistory(
        chain,
        get_session_history,
        input_messages_key="query",
        history_messages_key="chat_history",
    )
    
    router_result = router_with_history.invoke(
        {"query": state["question"]}, 
        {'configurable': {'session_id': state["session_id"]}}
    )
    state["q_type"] = router_result['type']
    return state

def router_conditional_edge(state: GraphState) -> GraphState:
    q_type = state["q_type"].strip()
    return q_type

##################################################################################
###################### nodes: Generate Python Pandas Code ########################
##################################################################################

class CodeGenerator(BaseModel):
    code: str = Field(description="Python Pandas Code")

code_generator_output_parser = JsonOutputParser(pydantic_object=CodeGenerator)
code_generator_format_instructions = code_generator_output_parser.get_format_instructions()

code_generator_prompt = PromptTemplate(
    template="""
            You are an expert who can generate Python Pandas Code to answer the query.

            Write the code with the following dataset metadata. Do not use any other columns except the ones provided in the metadata. The columns are written in Korean.

            <Dataset Metadata>: 
            # Basic Information
            1. '공장관리번호' (Factory Management Number): Unique factory identification number. [Important] A single factory management number can appear across multiple rows. When counting the number of factories, always use unique/distinct values of this field.

            # Company & Factory Information
            2. '회사명' (Company Name): Name of the company operating the factory. It's not unique. 
            3. '공장구분' (Factory Classification): Type/classification of the factory
            4. '단지명' (Complex Name): Name of the industrial complex (if applicable)
            5. '설립구분' (Establishment Type): Classification of how the factory was established
            6. '입주형태' (Occupancy Type): Type of occupancy arrangement
            7. '등록구분' (Registration Type): Classification of factory registration
            8. '전화번호' (Phone Number): Contact phone number


            # Employee Statistics
            9. '남자종업원' (Male Employees): Number of male employees
            10. '여자종업원' (Female Employees): Number of female employees
            11. '외국인남자종업원' (Foreign Male Employees): Number of foreign male employees
            12. '외국인여자종업원' (Foreign Female Employees): Number of foreign female employees
            13. '종업원합계' (Total Employees): Total number of employees

            # Production Information
            14. '생산품' (Products): Products manufactured at the factory
            15. '원자재' (Raw Materials): Raw materials used in production
            16. '공장규모' (Factory Scale): Size classification of the factory
            
            # Facility Specifications
            17. '용지면적' (Land Area): Total land area in square meters
            18. '제조시설면적' (Manufacturing Facility Area): Area dedicated to manufacturing facilities
            19. '부대시설면적' (Auxiliary Facility Area): Area of auxiliary/support facilities
            20. '건축면적' (Building Area): Total building area
            21. '지식산업센터명' (Knowledge Industry Center Name): Name of knowledge industry center (if applicable)

            # Location & Administrative
            22. '필지수' (Number of Parcels): Number of land parcels
            23. '공장관리번호' (Factory Management Number): Unique factory identification number

            #Standardized Fields (정제_)
            24. '정제_관리기관' (Standardized Management Agency): Standardized name of the management agency 
            25. '정제_보유구분' (Standardized Ownership Type): Standardized ownership classification
            26. '정제_시군구명' (Standardized District Name): Standardized city/county/district name
            27. '정제_시도명' (Standardized Province Name): Standardized province/metropolitan city name
            28. '정제_업종명' (Standardized Industry Name): Standardized industry name. It's not unique, so you need to calculate with '정제_대표업종' and show in '정제_업종명'
            29. '정제_대표업종' (Standardized Primary Industry): Standardized primary industry classification. It's in code, so after use it, you need to show the name using '정제_대표업종'
            29. '정제_용도지역' (Standardized Zoning District): Standardized zoning/land use district
            30. '정제_지목' (Standardized Land Category): Standardized land category classification

            # Date Fields
            31. '정제_최초등록일' (Standardized Initial Registration Date): Standardized date of initial registration (format: YYYY-MM-DD)
            32. '정제_최초승인일' (Standardized Initial Approval Date): Standardized date of initial approval (format: YYYY-MM-DD)

            Write the code with the most efficient way.
            <Output format>: Always respond with Python Pandas code. Always assign the final result to a variable called `return_var`. Do not use print(). {format_instructions}
            <chat_history>: {chat_history}
            
            <Question>: {query} 
            """,
    input_variables=["query", "chat_history"],
    partial_variables={"format_instructions": code_generator_format_instructions},
)

# @tool
# def code_generator(input):
#     '''
#     사용자의 질문에 답하기 위해 CSV에서 쿼리할 수 있는 Python Pandas 코드를 작성하는 도구
#     '''
#     chain = code_generator_prompt | model | code_generator_output_parser
    
#     code_generator_with_history  = RunnableWithMessageHistory(
#         chain,
#         get_session_history,
#         input_messages_key="query",
#         history_messages_key="chat_history",
#     )
    
#     code_generator_result = code_generator_with_history.invoke(
#         {"query": input}, 
#         {'configurable': {'session_id': state["session_id"]}}
#     )
#     return code_generator_result['code']

@tool
def code_generator(input, session_id: str | None = None):
    """
    사용자의 질문에 답하기 위해 CSV에서 쿼리할 수 있는 Python Pandas 코드를 작성하는 도구
    """
    chain = code_generator_prompt | model | code_generator_output_parser

    resolved_session_id = session_id or generate_session_id()

    code_generator_with_history = RunnableWithMessageHistory(
        chain,
        get_session_history,
        input_messages_key="query",
        history_messages_key="chat_history",
    )

    code_generator_result = code_generator_with_history.invoke(
        {"query": input},
        {'configurable': {'session_id': resolved_session_id}}
    )
    return code_generator_result['code']

@tool
def code_executor(input_code: str, max_retries=3):
    """
    LLM이 생성한 Pandas 코드를 안전하게 실행하고 return_var 반환.
    df는 글로벌 변수 사용.
    NA, None, 0 등의 에러 대비.
    """
    global df
    local_vars = {'df': df}

    for attempt in range(max_retries):
        try:
            exec(input_code, local_vars)
            if 'return_var' not in local_vars:
                raise ValueError("Generated code did not assign value to 'return_var'.")
            return local_vars['return_var']
        except Exception as e:
            print(f"⚠️ 코드 실행 실패 (시도 {attempt+1}/{max_retries}): {e}")
            # NA나 boolean 비교 에러 등 재시도 가능
            if attempt == max_retries - 1:
                raise

############################ tools & Agents ############################

# 🔧 개선 3: OpenAI API 레이트 리미팅 및 재시도
import openai
from openai import RateLimitError, APITimeoutError

def retry_on_failure(max_retries=3, delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        print(f"⚠️ 시도 {attempt + 1} 실패, {delay}초 후 재시도: {str(e)[:100]}")
                        time.sleep(delay * (attempt + 1))  # 지수 백오프
                    else:
                        print(f"❌ 모든 재시도 실패: {str(e)}")
            raise last_exception
        return wrapper
    return decorator

@retry_on_failure(max_retries=3, delay=2)
def call_openai_with_retry(client, **kwargs):
    try:
        return client.chat.completions.create(**kwargs)
    except RateLimitError as e:
        print(f"⚠️ OpenAI 레이트 리미트: {e}")
        time.sleep(5)  # 레이트 리미트 시 더 오래 대기
        raise
    except APITimeoutError as e:
        print(f"⚠️ OpenAI 타임아웃: {e}")
        raise
    except Exception as e:
        print(f"⚠️ OpenAI API 오류: {e}")
        raise
    
tools = [code_generator, code_executor]

agent_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful assistant that answers ONLY in Korean. "
            "You must follow these rules:\n"
            "1. If q_type is 'domain_specific', you MUST use tools to generate code and execute it."
            "2. Use the result of code_executor, which is called 'return_var', to answer."
            "3. ONLY if 'return_var' is empty ([], None, or pd.DataFrame with no rows), respond with '참조할 정보가 없어서 답변할 수 없습니다.'"
            "4. Otherwise, ALWAYS use 'return_var' as the basis of your answer."
            "Always answer in Korean, never in English."
        ),
        ("placeholder", "{chat_history}"),
        ("human", "{input}"),
        ("human", "{retrieved_data}"),
        ("placeholder", "{agent_scratchpad}"),
    ]
)

def agent(state: GraphState) -> GraphState:
    """
    Agent 실행 함수
    - domain_specific 질문은 tools(code_generator + safe_code_executor) 사용
    - code 실행 실패 시 재시도 구조 적용
    """
    session_id = state["session_id"]
    # 히스토리에 dict 그대로 넣지 말고 문자열로 변환
    chat_history = get_session_history(session_id)
    chat_history.add_user_message(f"question: {state['question']}, q_type: {state['q_type']}")

    try:
        # Agent 생성
        agent_obj = create_tool_calling_agent(model, tools, agent_prompt)

        agent_executor = AgentExecutor(
            agent=agent_obj,
            tools=tools,
            verbose=False,
            max_iterations=10,
            max_execution_time=120,
            handle_parsing_errors=True,
            return_intermediate_steps=True
        )

        agent_with_history = RunnableWithMessageHistory(
            agent_executor,
            get_session_history,
            history_messages_key="chat_history",
        )

        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                # Agent 실행
                result = agent_with_history.invoke(
                    {
                        "input": state["question"],
                        "retrieved_data": state.get("context"),
                        "relevance": state.get("relevance"),
                        "session_id": session_id  # <-- session_id 명시적 전달
                    },
                    {'configurable': {'session_id': session_id}}
                )

                # 결과에서 코드 실행이 필요하면 tools 내부에서 자동 호출됨
                state['answer'] = result['output']
                return state

            except Exception as e_inner:
                print(f"⚠️ 에이전트 시도 {attempt+1}/{max_attempts} 실패: {e_inner}")
                if attempt == max_attempts - 1:
                    raise

    except Exception as e:
        print(f"❌ 에이전트 실행 최종 실패: {e}")
        state['answer'] = f"죄송합니다. 질문 처리 중 오류가 발생했습니다: {str(e)[:100]}"
        return state

########################################################################
############################ Workflow Graph ############################
########################################################################

workflow = StateGraph(GraphState)

workflow.add_node("Router", router)
workflow.add_node("Agent", agent)

workflow.add_edge("Router", "Agent")
workflow.add_edge("Agent", END)

workflow.set_entry_point("Router")

memory = MemorySaver()
graph = workflow.compile(checkpointer=memory)  


 ##############################################################################################################
################################################Chat Interface################################################
##############################################################################################################

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from functools import lru_cache


# 🔧 개선 4: FastAPI 앱 생성 시 lifespan 이벤트 추가
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시
    print("🚀 서버 시작")
    yield
    # 종료 시
    print("🛑 서버 종료")

app = FastAPI(title="Juso Chatbot API", lifespan=lifespan)

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
    ]

@lru_cache()
def get_settings():
    return Settings() 

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class MessageRequest(BaseModel):
    message: str
    session_id: str = None

class FeedbackRequest(BaseModel):
    score: float
    run_id: str

current_user_id = None

# 🔧 개선 5: 비동기 처리 및 상세한 에러 핸들링
@app.post("/api/")
async def stream_responses(request: Request):
    try:
        data = await request.json()
        message = data.get('message')
        client_session_id = data.get('session_id')
        
        if not message:
            raise HTTPException(status_code=400, detail="Message is required")
        
        if not message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty")

        # 메시지 길이 제한
        if len(message) > 1000:
            raise HTTPException(status_code=400, detail="Message too long (max 1000 characters)")

        # 세션 ID 처리
        if not client_session_id:
            client_session_id = generate_session_id()

        # 🔧 개선 6: 설정 최적화
        config = RunnableConfig(
            recursion_limit=10,  # 재귀 제한 줄임
            configurable={
                "thread_id": f"HIKE-FACTORY-CHATBOT-{client_session_id[:8]}", 
                "user_id": current_user_id, 
                "session_id": client_session_id
            }
        )

        inputs = GraphState(
            question=message,
            session_id=client_session_id,
            q_type='',
            context='',
            answer='',
            relevance='',
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
                "status": "success"
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

@app.post("/api/reset")
async def reset_store(request: Request):
    try:
        data = await request.json()
        session_id_to_reset = data.get('session_id')
        
        if session_id_to_reset:
            # 특정 세션만 초기화
            message_count = thread_safe_store.clear_session(session_id_to_reset)
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

# 🔧 개선 7: 헬스체크 엔드포인트 추가
@app.get("/health")
async def health_check():
    stats = thread_safe_store.get_stats()
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "sessions": stats['total_sessions'],
        "messages": stats['total_messages']
    }

if __name__ == "__main__":
    import uvicorn
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