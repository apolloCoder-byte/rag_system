"""Redis 数据库配置"""

import redis
from typing import Optional
from loguru import logger

from src.config.setting import settings


class RedisConfig:
    """Redis 配置类"""
    
    def __init__(self):
        self.host = settings.REDIS_HOST
        self.port = settings.REDIS_PORT
        self.password = settings.REDIS_PASSWORD
        self.db = settings.REDIS_DB
        self.decode_responses = True
        self.socket_connect_timeout = 5
        self.socket_timeout = 5
        self.retry_on_timeout = True
        self.max_connections = 20
        
    def get_connection(self) -> redis.Redis:
        """获取 Redis 连接"""
        try:
            client = redis.Redis(
                host=self.host,
                port=self.port,
                password=self.password,
                db=self.db,
                decode_responses=self.decode_responses,
                socket_connect_timeout=self.socket_connect_timeout,
                socket_timeout=self.socket_timeout,
                retry_on_timeout=self.retry_on_timeout,
                max_connections=self.max_connections
            )
            
            # 测试连接
            client.ping()
            logger.info(f"Redis connected successfully to {self.host}:{self.port}")
            return client
            
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
        except Exception as e:
            logger.error(f"Redis connection error: {e}")
            raise
    
    def test_connection(self) -> bool:
        """测试 Redis 连接"""
        try:
            client = self.get_connection()
            client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis connection test failed: {e}")
            return False


# 全局 Redis 配置实例
redis_config = RedisConfig()

# 全局 Redis 客户端实例
def get_redis_client() -> redis.Redis:
    """获取 Redis 客户端"""
    return redis_config.get_connection()
