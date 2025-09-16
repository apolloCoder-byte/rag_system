from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .node import (
    query_node,
    route_node,
    get_memory_node,
    supervisor_node,
    retrieval_agent_node,
    deal_with_results_node,
    update_memory_node,
    generate_answer
)
from .types import State

def _build_agentic_rag_graph():
    """Build and return the agentic RAG workflow graph."""
    builder = StateGraph(State)
    builder.add_edge(START, "query")
    builder.add_node("query", query_node)
    builder.add_node("route", route_node)
    builder.add_node("answer", generate_answer)
    builder.add_node("get_memory", get_memory_node)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("retrieval_agent", retrieval_agent_node)
    builder.add_node("deal_with_results", deal_with_results_node)
    builder.add_node("update_memory", update_memory_node)
    
    return builder

def build_agentic_rag_graph():
    """Build and return the agentic RAG workflow graph with memory."""
    memory = MemorySaver()
    builder = _build_agentic_rag_graph()
    return builder.compile(checkpointer=memory)
