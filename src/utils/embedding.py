from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import DashScopeEmbeddings
from typing import List, Union, overload
from loguru import logger
import numpy as np


from src.config.setting import settings

@overload
def get_text_embeddings(texts: str) -> List[float]:
    ...

@overload
def get_text_embeddings(texts: List[str]) -> List[List[float]]:
    ...

def get_text_embeddings(
    texts: Union[List[str], str]
    ) -> Union[List[List[float]], List[float]]:
    """对文本列表进行向量化"""
    try:
        embeddings = DashScopeEmbeddings(
            model=settings.EMBEDDING_MODEL,
            dashscope_api_key=settings.EMBEDDING_API_KEY
        )

        if isinstance(texts, str):
            logger.info(f"向量化单个文本")
            result = embeddings.embed_query(texts)
        else:
            logger.info(f"正在向量化 {len(texts)} 个文本")
            result = embeddings.embed_documents(texts)
        
        logger.info(f"文本向量化完成")
        return result
        
    except Exception as e:
        logger.error(f"文本向量化失败: {e}")
        raise RuntimeError(f"文本向量化失败: {e}")
