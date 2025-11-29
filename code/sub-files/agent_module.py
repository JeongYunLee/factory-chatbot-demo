from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.history import RunnableWithMessageHistory

from config import model
from state import GraphState, get_session_history
from tools_module import tools


def capture_execution_snapshot(session_id: str, intermediate_steps, question: str = "") -> str | None:
    """
    Agent 실행 중 code_generator/code_executor의 코드와 결과를 모아서 저장
    (현재는 execution_id만 반환, 실제 저장은 필요시 구현)
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

    # execution_output이 있으면 간단히 None 반환 (필요시 나중에 저장 로직 추가 가능)
    if execution_output is None:
        return None

    # 간단히 None 반환 (실제 저장이 필요하면 나중에 구현)
    return None


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
            "5. After collect the data results, describe the data specifically and explain about the results for the user."
            "Always answer in Korean, never in English.",
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
    - domain_specific 질문은 tools(code_generator + code_executor) 사용
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
                result = agent_with_history.invoke(
                    {
                        "input": state["question"],
                        "retrieved_data": state.get("context"),
                        "relevance": state.get("relevance"),
                        "session_id": session_id,  # <-- session_id 명시적 전달
                    },
                    {"configurable": {"session_id": session_id}},
                )

                # 결과에서 코드 실행이 필요하면 tools 내부에서 자동 호출됨
                state["answer"] = result["output"]
                state["execution_id"] = capture_execution_snapshot(
                    session_id, result.get("intermediate_steps"), state["question"]
                )
                return state

            except Exception as e_inner:  # pylint: disable=broad-except
                print(f"⚠️ 에이전트 시도 {attempt+1}/{max_attempts} 실패: {e_inner}")
                if attempt == max_attempts - 1:
                    raise

    except Exception as e:  # pylint: disable=broad-except
        print(f"❌ 에이전트 실행 최종 실패: {e}")
        state[
            "answer"
        ] = "죄송합니다. 질문 처리 중 오류가 발생했습니다. 새로운 창에서 질문해주세요."
        return state


__all__ = ["agent", "agent_prompt", "capture_execution_snapshot"]


