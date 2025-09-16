from loguru import logger
from pymilvus import MilvusClient, exceptions

from src.config.setting import settings

class MilvusConnector:
    """Milvus 数据库连接管理类"""
    
    def __init__(self):
        self.uri = f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}"
        self.db = settings.MILVUS_DATABASE
        self.client = None  # 客户端实例
        self._init_connection()

    def _init_connection(self):
        """建立与 Milvus 的连接"""
        try:
            self.client = MilvusClient(
                uri=self.uri,
                db_name=self.db
            )
            # 测试连接是否有效
            self.client.list_databases()
            logger.info(f"成功连接到 Milvus: {self.uri}")
        except exceptions.MilvusException as e:
            logger.info(f"Milvus 连接失败: {str(e)}")
            self.client = None
            raise
        except Exception as e:
            logger.info(f"连接过程发生未知错误: {str(e)}")
            self.client = None
            raise
    
    async def insert_data(self, collection_name: str, data: list[dict]) -> bool:
        """
        向指定集合写入数据
        
        Args:
            collection_name: 集合名称
            data: 要写入的数据列表，每个元素为字典
            
        Returns:
            写入成功返回True，失败返回False
        """
        if not data or not isinstance(data, list):
            logger.error("写入数据为空或格式不正确（需为字典列表）")
            return False

        if not all(isinstance(item, dict) for item in data):
            logger.error("数据列表中的元素必须都是字典")
            return False
        
        try:
            # 检查集合是否存在
            if not self.client.has_collection(collection_name=collection_name):
                raise ValueError(f"集合 {collection_name} 不存在")
                
            # 执行插入
            result = self.client.insert(
                collection_name=collection_name,
                data=data
            )

            success_num = result.get("insert_count", 0)
            if success_num > 0:
                logger.info(f"共有 {len(data)} 条数据，成功向 {collection_name} 插入 {success_num} 条数据。")
                return True
            else:
                logger.warning(f"插入操作完成，但未插入任何数据到 {collection_name}")
                return False
                
        except ValueError as e:
            logger.error(f"集合不存在错误: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"插入数据到 {collection_name} 失败: {str(e)}")
            return False

    async def search_data_by_single_vector(
        self, 
        collection_name: str, 
        query_vector: list[float],
        anns_field: str,
        output_fields: list[str],
        limit: int = 3, 
        filter: str = ""
        ) -> list[dict]:
        """
        在指定集合中搜索相似向量
        
        Args:
            collection_name: 集合名称
            query_vector: 查询向量（需与集合中向量维度一致）
            limit: 返回结果数量
            filter: 布尔表达式过滤条件，如 "id > 100"
            output_fields: 需要返回的字段列表，默认返回所有字段
            
        Returns:
            搜索结果列表，每个元素包含匹配数据和距离
        """
        if not query_vector or not isinstance(query_vector, list):
            logger.error("查询向量为空或格式不正确（需为浮点列表）")
            return []
        
        formatted_result = []
        try:
            # 检查集合是否存在
            if not self.client.has_collection(collection_name=collection_name):
                raise ValueError(f"集合 {collection_name} 不存在")
                
            
            state = self.client.get_load_state(collection_name=collection_name)
            if state["state"] != "<LoadState: Loaded>":
                # 加载集合到内存
                self.client.load_collection(collection_name=collection_name)
                logger.info(f"已将 {collection_name} 加载到内存")
            
            result = self.client.search(
                collection_name=collection_name,
                anns_field=anns_field,
                data=[query_vector],
                limit=limit,
                search_params={"metric_type": "COSINE"},
                filter=filter,
                output_fields=output_fields
            )

            for hit in result[0]:
                formatted_result.append({
                    "id": hit["id"],
                    "distance": hit["distance"],
                    "fields": hit["entity"]
                })
                
            logger.info(f"在 {collection_name} 中找到 {len(formatted_result)} 条匹配结果")
            
            
        except ValueError as e:
            logger.error(f"集合不存在错误: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"搜索失败: {str(e)}")
            return []

        self.client.release_collection(
            collection_name=collection_name
        )
        
        if formatted_result:
            return formatted_result
        else:
            return []

milvus_service = MilvusConnector()
