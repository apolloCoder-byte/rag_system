"""This file contains the session model for the application."""

from datetime import datetime
from sqlmodel import Field, Index
from src.schema.base import BaseModel


class Session(BaseModel, table=True):
    """Session model for storing chat sessions.

    Attributes:
        id: The primary key
        user_id: 用户ID（逻辑外键，不建立物理约束）
        name: Name of the session (defaults to empty string)
        created_at: When the session was created
    """

    __tablename__ = "session"
    
    id: str = Field(primary_key=True)
    user_id: int = Field(index=True)  # 逻辑外键，只建索引
    name: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # 添加索引提升查询性能
    __table_args__ = (
        Index('idx_user_created', 'user_id', 'created_at'),
    )
