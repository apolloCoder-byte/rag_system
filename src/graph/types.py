from langgraph.graph import MessagesState
from typing_extensions import TypedDict
from typing import List, Dict, Any, Optional, Annotated, Union
from pydantic import BaseModel
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

# from src.prompts.planner_model import Plan
# from src.rag import Resource


class RetrievedInfo(BaseModel):
    """检索到的信息"""
    content: str
    source: str
    relevance_score: float
    metadata: Dict[str, Any] = {}


def custom_messages_reducer(
    existing: Optional[List[AnyMessage]], 
    new: Union[List[AnyMessage], AnyMessage, str]
) -> List[AnyMessage]:
    """
    自定义消息合并函数
    - 如果new是"delete"，则清空messages
    - 否则使用add_messages的功能
    """
    if new == "delete":
        return []
    
    if existing is None:
        existing = []
    
    return add_messages(existing, new)


class State(TypedDict):
    """State for the agent system with custom messages handling."""
    
    # 使用自定义的消息合并函数
    messages: Annotated[List[AnyMessage], custom_messages_reducer] = []

    # Runtime Variables
    locale: str = "en-US"
    research_topic: str = ""
    observations: list[str] = []
    # resources: list[Resource] = []
    plan_iterations: int = 0
    # current_plan: Plan | str = None
    final_report: str = ""
    auto_accepted_plan: bool = False
    enable_background_investigation: bool = True
    background_investigation_results: str = None
    
    # Agentic RAG specific fields
    user_query: str = ""
    history_messages: list = []
    memory_threshold: float = 0.65
    memory_info: List[dict] = []
    needs_retrieval: bool = False  # update  memory will use this.
    task_description: List[str] = []
    retrieved_information: List[RetrievedInfo] = []
    max_retrieval_iterations: int = 3
    current_iteration: int = 0
    final_answer: str = ""

    quality_score: float = 0.0
    quality_ok: bool = False

