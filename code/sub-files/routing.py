from langchain_core.output_parsers import JsonOutputParser
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.runnables import RunnableConfig

from config import model
from state import GraphState, get_session_history


class Router(BaseModel):
    type: str = Field(
        description="type of the query that model choose. Choose from ['general', 'domain_specific']"
    )


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
    """
    질문을 일반/general vs 도메인/domain_specific 으로 라우팅
    """
    chain = router_prompt | model | router_output_parser

    router_with_history = RunnableWithMessageHistory(
        chain,
        get_session_history,
        input_messages_key="query",
        history_messages_key="chat_history",
    )

    # 콜백 비활성화하여 RootListenersTracer 에러 방지
    # router_with_history.invoke()가 딕셔너리를 반환하는데, 
    # LangChain 콜백 시스템이 이를 추적하려고 할 때 에러 발생
    config = RunnableConfig(
        configurable={"session_id": state["session_id"]},
        callbacks=[]  # 콜백 비활성화
    )
    router_result = router_with_history.invoke(
        {"query": state["question"]},
        config,
    )
    state["q_type"] = router_result["type"]
    return state


def router_conditional_edge(state: GraphState) -> str:
    """
    그래프에서 분기(edge) 조건에 사용할 q_type 반환
    """
    q_type = state["q_type"].strip()
    return q_type


__all__ = ["Router", "router", "router_conditional_edge", "router_prompt"]


