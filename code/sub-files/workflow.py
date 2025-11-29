from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from agent_module import agent
from routing import router
from state import GraphState


workflow = StateGraph(GraphState)

workflow.add_node("Router", router)
workflow.add_node("Agent", agent)

workflow.add_edge("Router", "Agent")
workflow.add_edge("Agent", END)

workflow.set_entry_point("Router")

memory = MemorySaver()
graph = workflow.compile(checkpointer=memory)


__all__ = ["workflow", "graph", "memory"]


