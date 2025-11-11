from loguru import logger
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from src.config.setting import settings

from .node import (
    query_node,
    route_node,
    get_memory_node,
    supervisor_node,
    retrieval_agent_node,
    deal_with_results_node,
    update_memory_node,
    generate_answer
)
from .types import State

class LangGraphAgent:
    def __init__(self):
        self.graph = None
        self.connection_pool = None

    async def _get_connection_pool_postgres(self):
        """创建数据库连接池 postgres 连接池 异步"""
        if self.connection_pool is None:
            try:
                logger.info("create postgres connection pool")
                self.connection_pool = AsyncConnectionPool(
                    settings.POSTGRES_URL,
                    open=False,
                    min_size=10,
                    max_size=20,
                    kwargs={
                        "autocommit": True
                    }
                )
                await self.connection_pool.open()
                logger.info("postgres connection pool create sucessful")
            except Exception as e:
                logger.error(f"connection pool creation failed, error messages: {str(e)}")
                raise
        return self.connection_pool
    
    async def create_graph(self):
        if self.graph is None:
            try:
                logger.info("begin to ceate graph")
                builder = StateGraph(State)
                builder.add_edge(START, "query")
                builder.add_node("query", query_node)
                builder.add_node("route", route_node)
                builder.add_node("answer", generate_answer)
                builder.add_node("get_memory", get_memory_node)
                builder.add_node("supervisor", supervisor_node)
                builder.add_node("retrieval_agent", retrieval_agent_node)
                builder.add_node("deal_with_results", deal_with_results_node)
                builder.add_node("update_memory", update_memory_node)

                # # 创建数据库连接池，准备checkpointer
                connection_pool = await self._get_connection_pool_postgres()

                if connection_pool:
                    checkpointer = AsyncPostgresSaver(connection_pool)
                    await checkpointer.setup()
                else:
                    raise Exception("Connection pool initialization failed")
                # checkpointer = MemorySaver()
                
                self.graph = builder.compile(checkpointer=checkpointer)
                logger.info("graph created!")
            except Exception as e:
                logger.error(f"graph creation failed, error messages: str{e}")
                raise
        return self.graph
