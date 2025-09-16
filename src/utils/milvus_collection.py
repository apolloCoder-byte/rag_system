from pymilvus import MilvusClient, DataType
from datetime import datetime
from src.config.setting import settings

def create_milvus_collections():
    # 初始化Milvus客户端
    client = MilvusClient(
        uri=f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}",
        db_name=settings.MILVUS_DATABASE
        )
    
    # --------------------------
    # 1. 创建memory（存储QA对）
    # --------------------------
    memory_collection_name = "memory"
    
    if client.has_collection(collection_name=memory_collection_name):
        client.drop_collection(collection_name=memory_collection_name)
    
    # 定义memory_collection的schema
    memory_schema = client.create_schema(
        description="存储QA问答历史"
    )
    
    # 添加字段
    memory_schema.add_field(
        field_name="id",
        datatype=DataType.INT64,
        is_primary=True,
        auto_id=True,
        description="QA对的唯一标识"
    )
    memory_schema.add_field(
        field_name="question",
        datatype=DataType.VARCHAR,
        max_length=100,
        description="原始问题文本"
    )
    memory_schema.add_field(
        field_name="question_embedding",
        datatype=DataType.FLOAT_VECTOR,
        dim=1024,
        description="问题的向量表示"
    )
    memory_schema.add_field(
        field_name="answer",
        datatype=DataType.VARCHAR,
        max_length=200,
        description="问题的回答文本"
    )
    
    # 创建索引
    memory_index_params = client.prepare_index_params()
    memory_index_params.add_index(
        field_name="question_embedding",
        index_type="IVF_FLAT",  # 基础向量索引，适合中小规模数据
        index_name="question",
        metric_type="COSINE",  # 使用余弦相似度
        params={"nlist": 128}  # 索引参数，nlist为聚类数量
    )
    
    # 创建集合
    client.create_collection(
        collection_name=memory_collection_name,
        schema=memory_schema,
        index_params=memory_index_params
    )
    print(f"已创建集合: {memory_collection_name}")
    
    # --------------------------
    # 2. 创建knowledge（RAG知识库）
    # --------------------------
    # kb_collection_name = "knowledge"
    
    # if client.has_collection(collection_name=kb_collection_name):
    #     client.drop_collection(collection_name=kb_collection_name)
    
    # # 定义knowledge_base的schema
    # kb_schema = client.create_schema(
    #     description="RAG知识库，存储文档片段及向量"
    # )
    
    # # 添加字段
    # kb_schema.add_field(
    #     field_name="id",
    #     datatype=DataType.INT64,
    #     is_primary=True,
    #     auto_id=True,
    #     description="文档片段的唯一标识"
    # )
    # kb_schema.add_field(
    #     field_name="content",
    #     datatype=DataType.VARCHAR,
    #     max_length=300,
    #     description="文档片段内容"
    # )
    # kb_schema.add_field(
    #     field_name="content_embedding",
    #     datatype=DataType.FLOAT_VECTOR,
    #     dim=1024,
    #     description="文档片段的向量表示"
    # )
    # kb_schema.add_field(
    #     field_name="source",
    #     datatype=DataType.VARCHAR,
    #     max_length=100,
    #     description="文档来源（如文件名、URL）"
    # )
    
    # # 创建向量索引
    # kb_index_params = client.prepare_index_params()
    # kb_index_params.add_index(
    #     field_name="content_embedding",
    #     index_type="IVF_FLAT",
    #     metric_type="L2",
    #     params={"nlist": 128}
    # )
    
    # # 创建集合
    # client.create_collection(
    #     collection_name=kb_collection_name,
    #     schema=kb_schema,
    #     index_params=kb_index_params
    # )
    # print(f"已创建集合: {kb_collection_name}")

if __name__ == "__main__":
    # 执行创建集合的函数
    create_milvus_collections()
