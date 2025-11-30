"""
에이전트 모듈
"""
from functools import wraps
import time
from langchain.agents import create_tool_calling_agent
from langchain.agents import AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI
from core.models import GraphState
from core.state import get_session_history
from core.execution_store import ExecutionResultStore


def retry_on_failure(max_retries=3, delay=1):
    """재시도 데코레이터"""
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


from typing import Optional

def capture_execution_snapshot(session_id: str, intermediate_steps, question: str, execution_store: ExecutionResultStore) -> Optional[str]:
    """실행 스냅샷 캡처"""
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


def create_agent_prompt():
    """에이전트 프롬프트 생성"""
    return ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a helpful assistant that answers ONLY in Korean. "
                "You must follow these rules:\n"
                "1. If q_type is 'domain_specific', you MUST use tools to generate code and execute it."
                "2. Use the result of code_executor, which is called 'return_var', to answer."
                "3. ONLY if 'return_var' is empty ([], None, or pd.DataFrame with no rows), respond with '참조할 정보가 없어서 답변할 수 없습니다.'"
                "4. Otherwise, ALWAYS use 'return_var' as the basis of your answer, and you MUST ADD '[DATA]' prefix at the beginning of the answer."
                "5. When you use Korean text, be careful about the encoding and code(e.g. '(주)' & '㈜' --> '(주)' is correct.)"
                "6. When you use numbers, be careful about the type (e.g. 114, '114'). When you can't get the result, retry with another type."
                "7. After collecting the data results, describe the data specifically and explain the results for the user."
                "8. If the executed code fails with an error, you MUST modify the code and try again. NEVER submit the same code again. "
                "   Analyze the error and generate an improved version of the code (e.g., fix dtype errors, NA comparisons, boolean mask issues, missing columns, etc.)."
                "Always answer in Korean, never in English."
            ),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ]
    )


def create_agent(model: ChatOpenAI, tools, execution_store: ExecutionResultStore):
    """에이전트 생성 함수"""
    agent_prompt = create_agent_prompt()

    def agent(state: GraphState) -> GraphState:
        """
        Agent 실행 함수
        - domain_specific 질문은 tools(code_generator + safe_code_executor) 사용
        - code 실행 실패 시 재시도 구조 적용
        """
        session_id = state["session_id"]
        question = state["question"]
        
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
                        "session_id": session_id  
                    }

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
                    state['execution_id'] = capture_execution_snapshot(session_id, result.get('intermediate_steps'), state['question'], execution_store)
                    return state

                except Exception as e_inner:
                    print(f"⚠️ 에이전트 시도 {attempt+1}/{max_attempts} 실패: {e_inner}")
                    if attempt == max_attempts - 1:
                        raise

        except Exception as e:
            print(f"❌ 에이전트 실행 최종 실패: {e}")
            state['answer'] = f"죄송합니다. 질문 처리 중 오류가 발생했습니다. 새로운 창에서 질문해주세요."
            return state

    return agent

