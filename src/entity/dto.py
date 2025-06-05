from pydantic import BaseModel


class Message(BaseModel):
    role: str  # "user" 或 "assistant"
    content: str  # 消息内容


class ConversationRequest(BaseModel):
    thread_id: str  # 当前线程 ID
    message: Message  # 消息对象
