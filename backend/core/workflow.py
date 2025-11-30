"""
워크플로우 그래프 모듈
"""
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from core.models import GraphState


def create_workflow(router, agent):
    """워크플로우 그래프 생성"""
    workflow = StateGraph(GraphState)

    workflow.add_node("Router", router)
    workflow.add_node("Agent", agent)

    workflow.add_edge("Router", "Agent")
    workflow.add_edge("Agent", END)

    workflow.set_entry_point("Router")

    memory = MemorySaver()
    graph = workflow.compile(checkpointer=memory)
    
    return graph

