from langgraph.store.memory import InMemoryStore
from langgraph.checkpoint.memory import MemorySaver

from main_graph.multi_agent import MultiAgentGraph


class Config:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        across_thread_memory = InMemoryStore()
        within_thread_memory = MemorySaver()
        self.agent = MultiAgentGraph(across_thread_memory, within_thread_memory).construct_graph()


configs = Config()
