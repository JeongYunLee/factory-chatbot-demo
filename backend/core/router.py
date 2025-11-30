"""
Router 노드 모듈
"""
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI
from core.models import GraphState, Router
from core.state import get_session_history


def create_router(model: ChatOpenAI):
    """Router 설정 생성"""
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
        """Router 노드 함수"""
        question = state["question"] 
        chain = router_prompt | model | router_output_parser
        
        router_with_history = RunnableWithMessageHistory(
            chain,
            get_session_history,
            input_messages_key="query",
            history_messages_key="chat_history",
        )
        
        # 콜백 비활성화하여 RootListenersTracer 에러 방지
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

    def router_conditional_edge(state: GraphState) -> str:
        """Router 조건부 엣지 함수"""
        q_type = state["q_type"].strip()
        return q_type

    return router, router_conditional_edge

