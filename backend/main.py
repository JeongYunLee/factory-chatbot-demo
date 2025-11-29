import uuid, os, io, sys, time, json
from datetime import datetime, date
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
    execution_id: str | None  # 실행 결과 식별자

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


class ExecutionResultStore:
    """
    세션별 실행 결과를 저장하는 스토어
    - key: execution_id
    - value: { execution_id, session_id, code, result, created_at }
    - 별도 인덱스로 session_id -> [execution_id, ...] 관리
    """

    def __init__(self):
        self._store = {}
        self._session_index = {}  # session_id -> set(execution_id)
        self._lock = threading.RLock()

    def save(self, session_id: str, code: str | None, output, question: str = ""):
        execution_id = str(uuid.uuid4())
        payload = {
            "execution_id": execution_id,
            "session_id": session_id,
            "code": code,
            "result": serialize_execution_output(output, question),
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


def ensure_json_serializable(value):
    if isinstance(value, (np.integer, np.int32, np.int64)):
        return int(value)
    if isinstance(value, (np.floating, np.float32, np.float64)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (list, tuple)):
        return [ensure_json_serializable(v) for v in value]
    if isinstance(value, dict):
        return {k: ensure_json_serializable(v) for k, v in value.items()}
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, np.datetime64):
        return pd.Timestamp(value).isoformat()
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def dataframe_to_rows(df: pd.DataFrame, limit: int = 50):
    preview_df = df.head(limit).copy()
    preview_df = preview_df.where(pd.notnull(preview_df), None)
    records = preview_df.to_dict(orient="records")
    return [ensure_json_serializable(record) for record in records]


class VisualizationRecommendation(BaseModel):
    chart_type: str = Field(description="Recommended chart type. Choose from ['bar_chart', 'line_chart', 'pie_chart', 'map', 'heatmap', 'scatter_plot', 'none']")
    x_axis: str | None = Field(default=None, description="Column name for x-axis")
    y_axis: str | None = Field(default=None, description="Column name for y-axis")
    orientation: str | None = Field(default=None, description="For bar chart: 'horizontal' or 'vertical'")
    has_location: bool = Field(default=False, description="Whether the data contains location information suitable for map visualization")
    group_by: str | None = Field(default=None, description="Column name for grouping data")
    time_series: bool = Field(default=False, description="Whether the data is time-series data")

visualization_output_parser = JsonOutputParser(pydantic_object=VisualizationRecommendation)
visualization_format_instructions = visualization_output_parser.get_format_instructions()

visualization_prompt = PromptTemplate(
    template="""
    You are an expert data visualization analyst. Analyze the user's question and the data structure to recommend the best visualization type.

    Available chart types:
    - 'bar_chart': For comparing categories (e.g., "구별 공장 수", "업종별 직원 수")
    - 'line_chart': For showing trends over time (e.g., "연도별 등록 건수 추이", "최근 5년간 변화")
    - 'pie_chart': For showing proportions/percentages (e.g., "업종별 비율", "규모별 분포")
    - 'map': For location-based data (e.g., "구별 공장 분포", "지역별 분석")
    - 'heatmap': For 2D cross-tabulation (e.g., "구별 업종별 공장 수")
    - 'scatter_plot': For correlation between two numeric variables (e.g., "면적 대비 직원 수")
    - 'none': When visualization is not suitable or data is too complex

    Data columns available: {columns}
    User question: {question}
    Data sample (first 3 rows): {sample_data}

    Consider:
    1. If the question mentions location (구, 시군구, 지역, 지도), recommend 'map' if location columns exist
    2. If the question mentions time/trend (추이, 변화, 연도, 년도), recommend 'line_chart'
    3. If the question asks for comparison (비교, 상위, 많다), recommend 'bar_chart'
    4. If the question asks for proportion/ratio (비율, 분포), recommend 'pie_chart'
    5. If data has 2 categorical dimensions, consider 'heatmap'
    6. If data has 2 numeric variables for correlation, consider 'scatter_plot'

    {format_instructions}
    """,
    input_variables=["question", "columns", "sample_data"],
    partial_variables={"format_instructions": visualization_format_instructions},
)


def infer_visualization_type(question: str, output) -> dict | None:
    """
    질문과 결과 데이터를 분석하여 적절한 시각화 타입을 추론합니다.
    """
    try:
        # DataFrame 또는 Series인 경우에만 시각화 추론
        if not isinstance(output, (pd.DataFrame, pd.Series)):
            return None
        
        # Series를 DataFrame으로 변환
        if isinstance(output, pd.Series):
            df_for_analysis = output.reset_index()
        else:
            df_for_analysis = output.copy()
        
        # 데이터가 비어있으면 None 반환
        if len(df_for_analysis) == 0:
            return None
        
        # 컬럼이 너무 많으면 시각화 비추천
        if len(df_for_analysis.columns) > 10:
            return {"chart_type": "none"}
        
        # 샘플 데이터 준비 (최대 3행)
        sample_df = df_for_analysis.head(3)
        sample_data = sample_df.to_dict(orient="records")
        
        # 컬럼 목록
        columns = list(df_for_analysis.columns)
        
        # LLM을 사용하여 시각화 타입 추론
        chain = visualization_prompt | model | visualization_output_parser
        
        # 콜백 비활성화하여 RootListenersTracer 에러 방지
        config = RunnableConfig(callbacks=[])
        result = chain.invoke(
            {
                "question": question,
                "columns": str(columns),
                "sample_data": str(sample_data)
            },
            config=config
        )
        
        # 결과를 딕셔너리로 변환
        visualization_meta = {
            "chart_type": result.get("chart_type", "none"),
            "x_axis": result.get("x_axis"),
            "y_axis": result.get("y_axis"),
            "orientation": result.get("orientation", "vertical"),
            "has_location": result.get("has_location", False),
            "group_by": result.get("group_by"),
            "time_series": result.get("time_series", False)
        }
        
        # 실제 데이터 구조에 맞게 축 정보 보정
        if visualization_meta["chart_type"] != "none":
            # x_axis가 지정되지 않았고 DataFrame인 경우 첫 번째 컬럼 사용
            if not visualization_meta["x_axis"] and len(columns) > 0:
                if isinstance(output, pd.Series):
                    visualization_meta["x_axis"] = "index"
                    visualization_meta["y_axis"] = "value"
                else:
                    # 첫 번째 컬럼이 인덱스 컬럼인 경우
                    if columns[0] in ["index", "정제_시군구명", "정제_업종명"]:
                        visualization_meta["x_axis"] = columns[0]
                    # 수치형 컬럼 찾기
                    numeric_cols = df_for_analysis.select_dtypes(include=[np.number]).columns.tolist()
                    if numeric_cols:
                        visualization_meta["y_axis"] = numeric_cols[0]
            
            # 위치 정보 확인
            location_cols = [col for col in columns if any(keyword in col for keyword in ["시군구", "시도", "구", "지역", "주소"])]
            if location_cols:
                visualization_meta["has_location"] = True
                if not visualization_meta["x_axis"]:
                    visualization_meta["x_axis"] = location_cols[0]
        
        return visualization_meta
        
    except Exception as e:
        print(f"⚠️ 시각화 타입 추론 실패: {e}")
        return None


def serialize_execution_output(output, question: str = ""):
    # 시각화 메타데이터 추론
    visualization_meta = infer_visualization_type(question, output) if question else None
    
    if isinstance(output, pd.DataFrame):
        result = {
            "type": "table",
            "columns": list(output.columns),
            "rows": dataframe_to_rows(output),
            "row_count": int(len(output))
        }
        if visualization_meta:
            result["visualization"] = visualization_meta
        return result
    if isinstance(output, pd.Series):
        series_df = output.reset_index()
        series_df.columns = ["index", "value"]
        result = {
            "type": "table",
            "columns": list(series_df.columns),
            "rows": dataframe_to_rows(series_df),
            "row_count": int(len(output))
        }
        if visualization_meta:
            result["visualization"] = visualization_meta
        return result
    if isinstance(output, (list, tuple)):
        return {
            "type": "list",
            "rows": [ensure_json_serializable(item) for item in output],
            "row_count": len(output)
        }
    if isinstance(output, dict):
        return {
            "type": "object",
            "data": ensure_json_serializable(output)
        }
    if output is None:
        return {
            "type": "text",
            "value": None
        }
    return {
        "type": "text",
        "value": str(output)
    }


execution_store = ExecutionResultStore()

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
            Questions related to 'factory' or 'company' domain and data query, such as 'count the unique values of factories in Seoul', or count 'the number of rows in a table'.

            <Output format>: Always respond with either "general" or "domain_specific" and nothing else. {format_instructions}
            <chat_history>: {chat_history}
            
            <Question>: {query} 
            """,
    input_variables=["query", "chat_history"],
    partial_variables={"format_instructions": router_format_instructions},
)

def router(state: GraphState) -> GraphState:
    # 디버깅: Router에서 받은 질문 확인
    question = state["question"]
    print(f"🔀 Router 입력 질문 길이: {len(question)}, 끝 5자: {repr(question[-5:]) if len(question) >= 5 else repr(question)}")
    
    chain = router_prompt | model | router_output_parser
    
    router_with_history  = RunnableWithMessageHistory(
        chain,
        get_session_history,
        input_messages_key="query",
        history_messages_key="chat_history",
    )
    
    # 콜백 비활성화하여 RootListenersTracer 에러 방지
    # router_with_history.invoke()가 딕셔너리를 반환하는데, 
    # LangChain 콜백 시스템이 이를 추적하려고 할 때 에러 발생
    config = RunnableConfig(
        configurable={'session_id': state["session_id"]},
        callbacks=[]  # 콜백 비활성화
    )
    router_result = router_with_history.invoke(
        {"query": question}, 
        config
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
            3. '공장구분' (Factory Classification): Type/classification of the factory. categorized by 
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
            14. '생산품' (Products): Products manufactured at the factory. It's not categorized and normalized, so you need use 'str.contains' to filter the products.
            15. '원자재' (Raw Materials): Raw materials used in production. It's not categorized and normalized, so you need use 'str.contains' to filter the products.
            16. '공장규모' (Factory Scale): Size classification of the factory. e.g. ['소기업', '중기업', '대기업', '중견기업']
            
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
            29. '정제_대표업종' (Standardized Primary Industry): Standardized primary industry classification. It's in code, so after use it, you need to show the name using '정제_업종명' column. For example, if '정제_대표업종' is 'a11', you need to show the name using '제조업' column.
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

@tool
def code_generator(input, session_id: str | None = None):
    """
    사용자의 질문에 답하기 위해 CSV에서 쿼리할 수 있는 Python Pandas 코드를 작성하는 도구
    """
    # 디버깅: code_generator에 전달된 입력 확인
    print(f"📝 code_generator 입력 길이: {len(input)}, 끝 5자: {repr(input[-5:]) if len(input) >= 5 else repr(input)}")
    
    chain = code_generator_prompt | model | code_generator_output_parser

    resolved_session_id = session_id or generate_session_id()

    code_generator_with_history = RunnableWithMessageHistory(
        chain,
        get_session_history,
        input_messages_key="query",
        history_messages_key="chat_history",
    )

    # 콜백 비활성화하여 RootListenersTracer 에러 방지
    config = RunnableConfig(
        configurable={'session_id': resolved_session_id},
        callbacks=[]  # 콜백 비활성화
    )
    code_generator_result = code_generator_with_history.invoke(
        {"query": input},  # 원본 input 그대로 전달
        config
    )
    return code_generator_result['code']

@tool
def code_executor(input_code: str, max_retries=5):
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

def capture_execution_snapshot(session_id: str, intermediate_steps, question: str = "") -> str | None:
    if not intermediate_steps:
        return None

    code_snippet = None
    execution_output = None

    for step in intermediate_steps:
        try:
            action, observation = step
        except (TypeError, ValueError):
            continue

        tool_name = getattr(action, "tool", None)

        if tool_name == "code_generator" and isinstance(observation, str):
            code_snippet = observation
        elif tool_name == "code_executor":
            execution_output = observation

    if execution_output is None:
        return None

    return execution_store.save(session_id, code_snippet, execution_output, question)

agent_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful assistant that answers ONLY in Korean. "
            "You must follow these rules:\n"
            "1. If q_type is 'domain_specific', you MUST use tools to generate code and execute it."
            "2. Use the result of code_executor, which is called 'return_var', to answer."
            "3. ONLY if 'return_var' is empty ([], None, or pd.DataFrame with no rows), respond with '참조할 정보가 없어서 답변할 수 없습니다.'"
            "4. Otherwise, ALWAYS use 'return_var' as the basis of your answer, and you MUST ADD '[DATA]' prefix at the beginning of the answer."
            "5. When you use Koean text, be careful about the encoding and code(e.g. '(주)' & '㈜' --> '(주)' is correct.)"
            "6. When you use number, be careful about the type (e.g. 114, '114') When you can't get the result, retry with other type."
            "7. After collect the data results, describe the data specifically and explain about the results for the user."
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
    question = state["question"]
    
    # 디버깅: Agent에서 받은 질문 확인
    # print(f"🤖 Agent 입력 질문 길이: {len(question)}, 끝 5자: {repr(question[-5:]) if len(question) >= 5 else repr(question)}")
    
    # chat_history = get_session_history(session_id)
    # chat_history.add_user_message(f"question: {question}, q_type: {state['q_type']}")

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

        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                # Agent 실행 - 원본 질문 그대로 전달
                input_data = {
                    "input": question,  # state["question"] 대신 변수 사용
                    "retrieved_data": state.get("context"),
                    "relevance": state.get("relevance"),
                    "session_id": session_id  # <-- session_id 명시적 전달
                }
                print(f"🚀 Agent invoke 입력 데이터의 input 길이: {len(input_data['input'])}, 끝 5자: {repr(input_data['input'][-5:]) if len(input_data['input']) >= 5 else repr(input_data['input'])}")
                
                # 콜백 비활성화하여 RootListenersTracer 에러 방지
                config = RunnableConfig(
                    configurable={'session_id': session_id},
                    callbacks=[]  # 콜백 비활성화
                )
                result = agent_with_history.invoke(
                    input_data,
                    config
                )

                # 결과에서 코드 실행이 필요하면 tools 내부에서 자동 호출됨
                state['answer'] = result['output']
                state['execution_id'] = capture_execution_snapshot(session_id, result.get('intermediate_steps'), state['question'])
                return state

            except Exception as e_inner:
                print(f"⚠️ 에이전트 시도 {attempt+1}/{max_attempts} 실패: {e_inner}")
                if attempt == max_attempts - 1:
                    raise

    except Exception as e:
        print(f"❌ 에이전트 실행 최종 실패: {e}")
        state['answer'] = f"죄송합니다. 질문 처리 중 오류가 발생했습니다. 새로운 창에서 질문해주세요."
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

app = FastAPI(
    title="Data Chatbot API",
    lifespan=lifespan,
    root_path="/projects/data-chatbot"
)

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
        
        # 검증만 strip()으로 체크하고, 실제 사용할 메시지는 원본 사용 (끝의 빈 스페이스 보존)
        if not message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty")

        # 메시지 길이 제한
        if len(message) > 1000:
            raise HTTPException(status_code=400, detail="Message too long (max 1000 characters)")

        # 디버깅: 메시지 원본 길이 및 끝 문자 확인
        print(f"📝 수신 메시지 길이: {len(message)}, 끝 문자: {repr(message[-5:]) if len(message) >= 5 else repr(message)}")
        print(f"📝 전체 메시지: {repr(message)}")
        
        # 메시지 끝에 빈 스페이스가 없으면 추가 (마지막 글자 보호)
        if not message.endswith(' '):
            message = message + ' '
            print(f"🔒 메시지 끝에 보호 스페이스 추가: {repr(message[-5:])}")

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