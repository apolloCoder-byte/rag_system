from pydantic import BaseModel


class ConversationRequest(BaseModel):
    thread_id: str  # 当前线程 ID
    content: str  # 消息内容
