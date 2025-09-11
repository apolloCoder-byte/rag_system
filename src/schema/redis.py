"""Redis 数据模型和配置"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import json


class MessageRole(str, Enum):
    """消息角色枚举"""
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class RedisMessage:
    """Redis 消息模型"""
    session_id: str
    user_id: int
    message_role: MessageRole
    message: str
    created_at: str  # ISO 格式字符串
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "RedisMessage":
        """从字典创建实例"""
        return cls(**data)
    
    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> "RedisMessage":
        """从 JSON 字符串创建实例"""
        data = json.loads(json_str)
        return cls.from_dict(data)


class RedisKeyBuilder:
    """Redis 键构建器"""
    
    @staticmethod
    def message_key(user_id: int, session_id: str, created_at: datetime) -> str:
        """构建消息键: {user_id}:{session_id}:{timestamp}"""
        timestamp = int(created_at.timestamp())  # 秒级时间戳
        return f"{user_id}:{session_id}:{timestamp}"
    
    @staticmethod
    def session_messages_key(user_id: int, session_id: str) -> str:
        """构建会话消息列表键: {user_id}:{session_id}"""
        return f"{user_id}:{session_id}"
    
    @staticmethod
    def parse_message_key(key: str) -> Dict[str, str]:
        """解析消息键: 123:abc:1234567890"""
        parts = key.split(":")
        return {
            "user_id": parts[0],
            "session_id": parts[1], 
            "timestamp": parts[2]
        }
