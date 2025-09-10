from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .node import chat_node
from .types import State

def _build_base_graph():
    """Build and return the base state graph with all nodes and edges."""
    builder = StateGraph(State)
    builder.add_edge(START, "chat")
    builder.add_node("chat", chat_node)
    builder.add_edge("chat", END)
    return builder

def build_graph_with_memory():
    """Build and return the agent workflow graph with memory."""
    # use persistent memory to save conversation history
    # TODO: be compatible with SQLite / PostgreSQL
    memory = MemorySaver()

    # build state graph
    builder = _build_base_graph()
    return builder.compile(checkpointer=memory)
