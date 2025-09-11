"""Redis 连接测试"""

from src.config.redis import get_redis_client
from loguru import logger


def test_redis_connection():
    """测试 Redis 连接"""
    try:
        client = get_redis_client()
        
        # 测试基本操作
        client.set("test_key", "test_value")
        value = client.get("test_key")
        
        if value == "test_value":
            logger.info("✅ Redis 连接测试成功")
            
            # 清理测试数据
            client.delete("test_key")
            return True
        else:
            logger.error("❌ Redis 数据读写测试失败")
            return False
            
    except Exception as e:
        logger.error(f"❌ Redis 连接测试失败: {e}")
        return False


if __name__ == "__main__":
    test_redis_connection()
    