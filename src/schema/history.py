"""History model for storing chat messages."""

from datetime import datetime
from sqlmodel import Field, Index
from src.schema.base import BaseModel
from src.schema.redis import MessageRole  # 从 redis.py 导入


class History(BaseModel, table=True):
    """History model for storing chat messages.

    Attributes:
        id: The primary key
        session_id: 会话ID（逻辑外键，不建立物理约束）
        user_id: 用户ID（逻辑外键，不建立物理约束）
        message_role: Role of the message (user or assistant)
        message: The actual message content
        created_at: When the message was created
    """

    __tablename__ = "history"
    
    id: int = Field(default=None, primary_key=True)
    session_id: str = Field(index=True)  # 逻辑外键，只建索引
    user_id: int = Field(index=True)     # 逻辑外键，只建索引
    message_role: MessageRole = Field(index=True)
    message: str = Field(max_length=10000)  # 限制消息长度
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    
    # 添加复合索引提升查询性能
    __table_args__ = (
        Index('idx_session_created', 'session_id', 'created_at'),
        Index('idx_user_session', 'user_id', 'session_id'),
    )
    