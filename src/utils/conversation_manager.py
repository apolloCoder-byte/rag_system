"""多轮对话管理器 - 基于 PostgreSQL + Redis"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger

import redis
from sqlmodel import Session as SQLSession, select

from src.config.redis import get_redis_client
from src.services.database import database_service
from src.schema.history import History, MessageRole
from src.schema.redis import RedisMessage, RedisKeyBuilder


class ConversationManager:
    """多轮对话管理器"""

    def __init__(self):
        self.redis_client = get_redis_client()
        self.MESSAGE_EXPIRE_SECONDS = 30 * 60  # 30分钟过期时间
    
    def add_message(
        self, 
        session_id: str, 
        user_id: int, 
        message_role: MessageRole, 
        message: str
    ) -> bool:
        """添加消息到 Redis 和 PostgreSQL"""
        try:
            now = datetime.utcnow()
            
            # 1. 存储到 Redis（实时存储）
            self._store_to_redis(session_id, user_id, message_role, message, now)
            
            # 2. 存储到 PostgreSQL（持久化存储）
            self._store_to_postgres(session_id, user_id, message_role, message, now)
            
            # 3. 如果是用户消息，刷新整个会话的过期时间
            if message_role == MessageRole.USER:
                self._refresh_session_expire_time(user_id, session_id)
            
            logger.info(f"Added {message_role.value} message to session {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to add message: {e}")
            return False
    
    def _store_to_redis(
        self, 
        session_id: str, 
        user_id: int, 
        message_role: MessageRole, 
        message: str, 
        created_at: datetime
    ) -> None:
        """存储消息到 Redis"""
        try:
            # 创建 Redis 消息对象
            redis_message = RedisMessage(
                session_id=session_id,
                user_id=user_id,
                message_role=message_role,
                message=message,
                created_at=created_at.isoformat()
            )
            
            # 构建键
            message_key = RedisKeyBuilder.message_key(user_id, session_id, created_at)
            session_messages_key = RedisKeyBuilder.session_messages_key(user_id, session_id)
            
            # 存储消息内容（设置过期时间）
            self.redis_client.setex(
                message_key, 
                self.MESSAGE_EXPIRE_SECONDS, 
                redis_message.to_json()
            )
            
            # 添加到会话消息列表（按时间排序）
            self.redis_client.zadd(
                session_messages_key, 
                {message_key: created_at.timestamp()}
            )
            
            # 设置会话消息列表的过期时间
            self.redis_client.expire(session_messages_key, self.MESSAGE_EXPIRE_SECONDS)
            
        except Exception as e:
            logger.error(f"Failed to store message to Redis: {e}")
            raise
    
    def _refresh_session_expire_time(self, user_id: int, session_id: str) -> None:
        """刷新会话的过期时间（当收到用户消息时调用）"""
        try:
            session_messages_key = RedisKeyBuilder.session_messages_key(user_id, session_id)
            
            # 获取所有消息键
            message_keys = self.redis_client.zrange(session_messages_key, 0, -1)
            
            # 刷新每个消息的过期时间
            for key in message_keys:
                self.redis_client.expire(key, self.MESSAGE_EXPIRE_SECONDS)
            
            # 刷新会话消息列表的过期时间
            self.redis_client.expire(session_messages_key, self.MESSAGE_EXPIRE_SECONDS)
            
            logger.info(f"Refreshed expire time for session {session_id}")
            
        except Exception as e:
            logger.error(f"Failed to refresh session expire time: {e}")
    
    def _store_to_postgres(
        self, 
        session_id: str, 
        user_id: int, 
        message_role: MessageRole, 
        message: str, 
        created_at: datetime
    ) -> None:
        """存储消息到 PostgreSQL（使用逻辑外键）"""
        try:
            # 修正：使用正确的数据库会话方法
            with database_service.get_session_maker() as session:
                history = History(
                    session_id=session_id,
                    user_id=user_id,
                    message_role=message_role,
                    message=message,
                    created_at=created_at
                )
                session.add(history)
                session.commit()
        except Exception as e:
            logger.error(f"Failed to store message to PostgreSQL: {e}")
            raise
    
    def get_messages(
        self, 
        session_id: str, 
        user_id: int, 
        limit: int = 50
    ) -> List[RedisMessage]:
        """从 Redis 获取消息列表"""
        try:
            session_messages_key = RedisKeyBuilder.session_messages_key(user_id, session_id)
            
            # 检查会话是否存在
            if not self.redis_client.exists(session_messages_key):
                logger.info(f"Session {session_id} not found in Redis or expired")
                return []
            
            # 获取消息键列表（按时间倒序）
            message_keys = self.redis_client.zrevrange(
                session_messages_key, 
                0, 
                limit - 1
            )
            
            messages = []
            valid_keys = []
            
            for key in message_keys:
                # 检查消息是否还存在（可能已过期）
                if self.redis_client.exists(key):
                    message_json = self.redis_client.get(key)
                    if message_json:
                        try:
                            message = RedisMessage.from_json(message_json)
                            messages.append(message)
                            valid_keys.append(key)
                        except Exception as e:
                            logger.error(f"Failed to parse message from Redis: {e}")
                else:
                    # 消息已过期，从有序集合中移除
                    self.redis_client.zrem(session_messages_key, key)
            
            # 如果所有消息都过期了，删除会话
            if not valid_keys:
                self.redis_client.delete(session_messages_key)
                logger.info(f"All messages expired for session {session_id}, session deleted")
                return []
            
            # 按时间正序返回
            return list(reversed(messages))
            
        except Exception as e:
            logger.error(f"Failed to get messages from Redis: {e}")
            return []
    
    def get_messages_from_postgres(
        self, 
        session_id: str, 
        limit: int = 50
    ) -> List[History]:
        """从 PostgreSQL 获取消息列表（备用方案）"""
        try:
            # 修正：使用正确的数据库会话方法
            with database_service.get_session_maker() as session:
                statement = select(History).where(
                    History.session_id == session_id
                ).order_by(History.created_at.desc()).limit(limit)
                
                histories = session.exec(statement).all()
                return list(reversed(histories))
        except Exception as e:
            logger.error(f"Failed to get messages from PostgreSQL: {e}")
            return []
    
    def warmup_session_from_postgres(
        self, 
        session_id: str, 
        user_id: int, 
        limit: int = 50
    ) -> bool:
        """从 PostgreSQL 预热会话数据到 Redis"""
        try:
            # 检查 Redis 中是否已有数据
            session_messages_key = RedisKeyBuilder.session_messages_key(user_id, session_id)
            if self.redis_client.exists(session_messages_key):
                logger.info(f"Session {session_id} already exists in Redis, skipping warmup")
                return True
            
            # 从 PostgreSQL 获取历史数据
            history_messages = self.get_messages_from_postgres(session_id, limit)
            
            if not history_messages:
                logger.info(f"No history data found for session {session_id}")
                return True
            
            # 将历史数据存储到 Redis
            for history in history_messages:
                self._store_to_redis(
                    session_id=history.session_id,
                    user_id=history.user_id,
                    message_role=history.message_role,
                    message=history.message,
                    created_at=history.created_at
                )
            
            logger.info(f"Warmed up {len(history_messages)} messages for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to warm up session {session_id}: {e}")
            return False
    
    def clear_session(self, session_id: str, user_id: int) -> bool:
        """清空会话消息"""
        try:
            # 清空 Redis
            session_messages_key = RedisKeyBuilder.session_messages_key(user_id, session_id)
            message_keys = self.redis_client.zrange(session_messages_key, 0, -1)
            
            if message_keys:
                self.redis_client.delete(*message_keys)
            self.redis_client.delete(session_messages_key)
            
            # 清空 PostgreSQL
            # 修正：使用正确的数据库会话方法
            with database_service.get_session_maker() as session:
                statement = select(History).where(History.session_id == session_id)
                histories = session.exec(statement).all()
                for history in histories:
                    session.delete(history)
                session.commit()
            
            logger.info(f"Cleared session {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear session {session_id}: {e}")
        return False

    def get_session_ttl(self, user_id: int, session_id: str) -> int:
        """获取会话剩余过期时间（秒）"""
        try:
            session_messages_key = RedisKeyBuilder.session_messages_key(user_id, session_id)
            ttl = self.redis_client.ttl(session_messages_key)
            return ttl if ttl > 0 else 0
        except Exception as e:
            logger.error(f"Failed to get session TTL: {e}")
            return 0
    
    def cleanup_expired_messages(self) -> int:
        """清理过期的消息（可以定期调用）"""
        try:
            # 查找所有会话消息列表键
            pattern = "*:*:messages"  # 匹配所有会话消息列表键
            session_keys = self.redis_client.keys(pattern)
            
            cleaned_count = 0
            for session_key in session_keys:
                # 获取该会话的所有消息键
                message_keys = self.redis_client.zrange(session_key, 0, -1)
                
                # 检查每个消息是否过期
                valid_keys = []
                for key in message_keys:
                    if self.redis_client.exists(key):
                        valid_keys.append(key)
                    else:
                        cleaned_count += 1
                
                # 如果所有消息都过期了，删除会话
                if not valid_keys:
                    self.redis_client.delete(session_key)
                    logger.info(f"Deleted expired session: {session_key}")
                else:
                    # 更新有序集合，只保留有效消息
                    self.redis_client.delete(session_key)
                    if valid_keys:
                        for key in valid_keys:
                            score = self.redis_client.zscore(session_key, key) or 0
                            self.redis_client.zadd(session_key, {key: score})
            
            logger.info(f"Cleaned up {cleaned_count} expired messages")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired messages: {e}")
            return 0


# 全局实例
conversation_manager = ConversationManager()
