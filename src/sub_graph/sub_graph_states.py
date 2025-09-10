from typing import Optional, Literal, Any, Union, Annotated
from datetime import datetime

from pydantic import BaseModel, Field

from src.main_graph.main_graph_states import Router


class Profile(BaseModel):
    """This is the profile of the user you are chatting with"""
    name: Optional[str] = Field(description="The user's name", default=None)
    location: Optional[str] = Field(description="The user's location", default=None)
    job: Optional[str] = Field(description="The user's job", default=None)
    connections: list[str] = Field(
        description="Personal connection of the user, such as family members, friends, or coworkers",
        default_factory=list
    )
    interests: list[str] = Field(
        description="Interests that the user has",
        default_factory=list
    )


class ToDo(BaseModel):
    task: str = Field(description="The task to be completed.")
    time_to_complete: Optional[int] = Field(description="Estimated time to complete the task (minutes).")
    deadline: Optional[datetime] = Field(
        description="When the task needs to be completed by (if applicable)",
        default=None
    )
    solutions: list[str] = Field(
        description="List of specific, actionable solutions (e.g., specific ideas, service providers, or concrete options relevant to completing the task)",
        default_factory=list
    )
    status: Literal["not started", "in progress", "done", "archived"] = Field(
        description="Current status of the task",
        default="not started"
    )


class InputSchema(BaseModel):
    update_object: Router


class ToDOListSchema(InputSchema):
    updated_status: str
    error_messages: Optional[str]


# search agent schema

def reduce_str(
        existing: list[dict[str, Any]],
        new: Union[str, list[dict[str, Any]]],
):
    if new == "delete":
        return []
    if existing is None:
        existing = []
    if isinstance(new, list):
        return existing + new
    return existing


class SearchInputSchema(BaseModel):
    question: str
    tool_name: str


class SearchSchema(SearchInputSchema):
    retrieved_information: Annotated[list[dict[str, Any]], reduce_str]


class OutputSchema(BaseModel):
    search_result: list[dict[str, Any]]
