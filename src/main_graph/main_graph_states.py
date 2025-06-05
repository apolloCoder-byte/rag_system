from typing import Annotated, Literal, Optional, Any, Union

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel


class Router(BaseModel):
    """
    there are two field
    1.small problem
    2.router type used in send mechanism, conditional edge
    """
    sub_message: str
    router_type: Literal["search", "user_profile", "user_todo", "user_instructions", "default"] = "default"


def reduce_str(
        existing: Optional[list[str]] | Optional[list[dict[str, Any]]] | list[Router] | list[AnyMessage],
        new: Union[str, list[str], list[dict[str, Any]], list[Router], list[AnyMessage]],
):
    if new == "delete":
        return []
    if existing is None:
        existing = []
    if isinstance(new, list):
        return existing + new
        # return temp
    return existing


class InputState(BaseModel):
    messages: Annotated[list[AnyMessage], reduce_str]


class AgentState(InputState):
    # sub_messages: list[Router]
    error_messages: Annotated[Optional[list[str]], reduce_str]
    search_result: Annotated[Optional[list[dict[str, Any]]], reduce_str]
    response: str


class OutputState(BaseModel):
    response: str


class GeneralState(BaseModel):
    pass
