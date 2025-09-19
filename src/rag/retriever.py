from langchain_milvus import Milvus
from langchain_community.embeddings import DashScopeEmbeddings
from langchain.retrievers import EnsembleRetriever
from langchain_community.document_compressors.dashscope_rerank import DashScopeRerank
from langchain.retrievers.contextual_compression import ContextualCompressionRetriever
from src.config.setting import settings
from langchain.tools.retriever import create_retriever_tool

class milvus_retriever:
    def __init__(self) -> None:
        embedding_fn = DashScopeEmbeddings(
            model=settings.EMBEDDING_MODEL,
            dashscope_api_key=settings.EMBEDDING_API_KEY
        )

        self.vector_db = Milvus(
            embedding_function=embedding_fn,
            collection_name="knowledge",
            connection_args={
                "uri": "http://localhost:19530",
                "db_name": "finance"
            }
        )

        self.rerank_model = DashScopeRerank(
            dashscope_api_key=settings.EMBEDDING_API_KEY
        )

        self.top_k = 4

    def _create_retriever(self, search_type, search_kwargs):
        return self.vector_db.as_retriever(
            search_type=search_type,
            search_kwargs=search_kwargs
        )

    def get_retriever(self):
        try:
            retriever_similarity = self._create_retriever("similarity", {"k": self.top_k})

            retriever_mmr = self._create_retriever("mmr", {"k": self.top_k})

            ensemble_retriever = EnsembleRetriever(
                retrievers=[retriever_similarity, retriever_mmr]
            )        

            compression_retriever = ContextualCompressionRetriever(
                base_compressor=self.rerank_model,
                base_retriever=ensemble_retriever,
            )

            return compression_retriever
        except Exception as e:
            raise ValueError(f"创建工具时出错：{e}")
    
    def create_retriever_tool(self, retriever):
        retriever_tool = create_retriever_tool(
            retriever, 
            "政策文件内容检索器", 
            "搜索和返回关于中央及银保监会金融监管政策文件的内容"
        )
        return retriever_tool

client = milvus_retriever()
retriever_instance = client.get_retriever()
retriever_tool = client.create_retriever_tool(retriever_instance)


if __name__ == "__main__":
    from src.agents.agents import get_react_agent

    client = milvus_retriever()
    retriever_instance = client.get_retriever()
    retriever_tool = client.create_retriever_tool(retriever_instance)
    # results = retriever_tool.invoke("资本工具合作标准是什么？")
    
    agent = get_react_agent([retriever_tool], "research")
    query = "资本工具合作标准是什么？"
    message = agent.invoke({"messages": [("human", query)]})
    print(
        {
            "input": query,
            "output": message["messages"][-1].content,
        }
    )
