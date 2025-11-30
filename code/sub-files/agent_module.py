import threading
import time
import uuid
import pandas as pd
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.tools import StructuredTool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.runnables import RunnableConfig
from langchain_core.pydantic_v1 import BaseModel, Field

from config import model
from state import get_session_history, generate_session_id
from tools_module import _query_router_impl, _code_generator_impl, code_executor


class ExecutionResultStore:
    """
    간단한 실행 결과 저장소 (메모리 기반)
    - execution_id를 키로 코드와 실행 결과 저장
    """
    
    def __init__(self):
        self._store = {}
        self._lock = threading.RLock()
    
    def save(self, session_id: str, code: str | None, result, question: str = "") -> str:
        """코드와 실행 결과를 저장하고 execution_id 반환"""
        execution_id = str(uuid.uuid4())
        
        # 결과를 JSON 직렬화 가능한 형태로 변환
        serialized_result = self._serialize_result(result)
        
        payload = {
            "execution_id": execution_id,
            "session_id": session_id,
            "code": code,
            "result": serialized_result,
            "question": question,
            "created_at": time.time(),
        }
        
        with self._lock:
            self._store[execution_id] = payload
        
        return execution_id
    
    def get(self, execution_id: str):
        """execution_id로 저장된 결과 조회"""
        with self._lock:
            return self._store.get(execution_id)
    
    def _serialize_result(self, result):
        """결과를 JSON 직렬화 가능한 형태로 변환"""
        if result is None:
            return None
        
        # pandas DataFrame 처리
        if isinstance(result, pd.DataFrame):
            if result.empty:
                return {"type": "empty_dataframe", "data": []}
            return {
                "type": "dataframe",
                "shape": list(result.shape),
                "columns": result.columns.tolist(),
                "data": result.head(100).to_dict(orient="records"),  # 상위 100개만 저장
            }
        
        # 리스트 처리
        if isinstance(result, (list, tuple)):
            if len(result) > 100:
                return {"type": "list", "length": len(result), "data": result[:100]}
            return {"type": "list", "data": result}
        
        # 딕셔너리 처리
        if isinstance(result, dict):
            return {"type": "dict", "data": result}
        
        # 기본 타입 (str, int, float, bool 등)
        return {"type": "primitive", "data": str(result)}


# 전역 저장소 인스턴스
execution_store = ExecutionResultStore()


def capture_execution_snapshot(session_id: str, intermediate_steps, question: str = "") -> str | None:
    """
    Agent 실행 중 code_generator/code_executor의 코드와 결과를 모아서 저장
    """
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

    # execution_output이 없으면 저장하지 않음
    if execution_output is None:
        return None

    # 저장소에 저장하고 execution_id 반환
    return execution_store.save(session_id, code_snippet, execution_output, question)


agent_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful assistant that answers ONLY in Korean. "
            "You must follow these rules:\n"
            "1. First, use the 'query_router' tool to classify the question as 'general' or 'domain_specific'.\n"
            "2. If the query type is 'domain_specific', you MUST use 'code_generator' and 'code_executor' tools to generate and execute code.\n"
            "3. If the query type is 'general', answer directly without using code generation tools.\n"
            "4. Use the result of code_executor, which is called 'return_var', to answer."
            "5. ONLY if 'return_var' is empty ([], None, or pd.DataFrame with no rows), respond with '참조할 정보가 없어서 답변할 수 없습니다.'"
            "6. Otherwise, ALWAYS use 'return_var' as the basis of your answer."
            "7. When you use Korean text, be careful about the encoding and code(e.g. '(주)' & '㈜' --> '(주)' is correct.)"
            "8. When you use numbers, be careful about the type (e.g. 114, '114'). When you can't get the result, retry with another type."
            "9. After collecting the data results, describe the data specifically and explain the results for the user."
            "10. If the executed code fails with an error, you MUST modify the code and try again. NEVER submit the same code again. "
            "   Analyze the error and generate an improved version of the code (e.g., fix dtype errors, NA comparisons, boolean mask issues, missing columns, etc.)."
            "Always answer in Korean, never in English."
        ),
        ("placeholder", "{chat_history}"),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ]
)


def run_agent(
    question: str,
    session_id: str | None = None,
    context: str | None = None,
    relevance: str | None = None,
) -> dict:
    """
    Agent 실행 함수
    - query_router 도구로 질문 분류
    - domain_specific 질문은 code_generator + code_executor 사용
    - code 실행 실패 시 재시도 구조 적용
    
    Args:
        question: 사용자 질문
        session_id: 세션 ID (없으면 자동 생성)
        context: 검색 컨텍스트 (선택사항)
        relevance: 검색 적합도 (선택사항)
    
    Returns:
        dict: {
            "answer": str,  # 답변
            "execution_id": str | None,  # 실행 결과 식별자
            "session_id": str  # 세션 ID
        }
    """
    resolved_session_id = session_id or generate_session_id()

    try:
        # session_id를 바인딩한 도구들 생성
        # 도구들이 같은 세션을 사용하도록 래핑
        def create_session_bound_tools(session_id: str):
            """session_id를 바인딩한 도구들을 생성"""
            def query_router_wrapper(query: str):
                return _query_router_impl(query, session_id)
            
            def code_generator_wrapper(input: str):
                return _code_generator_impl(input, session_id)
            
            # StructuredTool을 사용하여 명시적 입력 스키마 정의
            class QueryRouterInput(BaseModel):
                query: str = Field(description="분류할 질문")
            
            class CodeGeneratorInput(BaseModel):
                input: str = Field(description="코드를 생성할 질문")
            
            query_router_tool = StructuredTool.from_function(
                func=query_router_wrapper,
                name="query_router",
                description="질문을 일반(general) 또는 도메인 특화(domain_specific)로 분류하는 도구. 'general': 데이터 쿼리와 무관한 일반적인 질문 (번역, 일반 상식 등). 'domain_specific': 공장이나 회사 도메인과 관련된 데이터 쿼리 질문",
                args_schema=QueryRouterInput,
            )
            
            code_generator_tool = StructuredTool.from_function(
                func=code_generator_wrapper,
                name="code_generator",
                description="사용자의 질문에 답하기 위해 CSV에서 쿼리할 수 있는 Python Pandas 코드를 작성하는 도구",
                args_schema=CodeGeneratorInput,
            )
            
            return [query_router_tool, code_generator_tool, code_executor]
        
        session_tools = create_session_bound_tools(resolved_session_id)
        
        # Agent 생성
        agent_obj = create_tool_calling_agent(model, session_tools, agent_prompt)

        agent_executor = AgentExecutor(
            agent=agent_obj,
            tools=session_tools,
            verbose=False,
            max_iterations=10,
            max_execution_time=120,
            handle_parsing_errors=True,
            return_intermediate_steps=True,
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
                # 콜백 비활성화하여 RootListenersTracer 에러 방지
                config = RunnableConfig(
                    configurable={"session_id": resolved_session_id},
                    callbacks=[]  # 콜백 비활성화
                )
                
                # 입력 구성 (context가 있으면 포함)
                input_data = {"input": question}
                if context:
                    input_data["context"] = context
                if relevance:
                    input_data["relevance"] = relevance
                
                result = agent_with_history.invoke(
                    input_data,
                    config,
                )

                # 결과 반환
                execution_id = capture_execution_snapshot(
                    resolved_session_id, result.get("intermediate_steps"), question
                )
                
                return {
                    "answer": result["output"],
                    "execution_id": execution_id,
                    "session_id": resolved_session_id,
                }

            except Exception as e_inner:  # pylint: disable=broad-except
                print(f"⚠️ 에이전트 시도 {attempt+1}/{max_attempts} 실패: {e_inner}")
                if attempt == max_attempts - 1:
                    raise

    except Exception as e:  # pylint: disable=broad-except
        print(f"❌ 에이전트 실행 최종 실패: {e}")
        return {
            "answer": "죄송합니다. 질문 처리 중 오류가 발생했습니다. 다시 질문해주세요.",
            "execution_id": None,
            "session_id": resolved_session_id,
        }


__all__ = ["run_agent", "agent_prompt", "capture_execution_snapshot", "execution_store"]


