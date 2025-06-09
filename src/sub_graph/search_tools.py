import asyncio
from anyio import Semaphore
import json

from dotenv import load_dotenv

from langgraph.graph import END, START, StateGraph
from fastmcp import Client

from sub_graph.sub_graph_states import SearchInputSchema, SearchSchema, OutputSchema

load_dotenv()


class SearchSubGraph:

    def __init__(self, max_connections=5):
        self.config = {
            "mcpServers": {
                "web_search": {
                    "url": "http://localhost:8000/mcp",
                    "transport": "streamable-http",
                }
            }
        }
        self.semaphore = Semaphore(max_connections)  # 控制最大并发数

    async def use_tool(self, tool_name: str, params: dict):
        async with self.semaphore:  # 限制并发数
            async with Client(self.config) as client:  # 每个任务独立 Client
                result = await client.call_tool(tool_name, params)
                return result

    async def executor_search(self, state: SearchInputSchema):
        # get tool name
        tool_name = state.tool_name  # only one tool, So there is no "if" behavior here.
        # get question
        question = state.question
        # retrieve information by using tool, we use mcp server here
        mcp_return = await self.use_tool("tavily_search", {"question": question})
        mcp_return_text = mcp_return[0].text
        text = json.loads(mcp_return_text)["result"]
        # prepare data to return
        message = [{"search_clause": question, "search_result": text}]
        return {"retrieved_information": message}

    async def aggregate_information(self, state: SearchSchema):
        information = state.retrieved_information
        return {"retrieved_information": "delete", "search_result": information}

    def construct_graph(self):
        builder = StateGraph(SearchSchema, input=SearchInputSchema, output=OutputSchema)
        # add nodes
        builder.add_node("executor_search", self.executor_search)
        builder.add_node("aggregate", self.aggregate_information)

        # add edges
        builder.add_edge(START, "executor_search")
        builder.add_edge("executor_search", "aggregate")
        builder.add_edge("aggregate", END)

        return builder.compile()


async def main():
    agent = SearchSubGraph().construct_graph()
    content = "Which country has issued new AI regulatory policies in the past month?"
    state = SearchInputSchema(question=content, tool_name="tavily")
    result = await agent.ainvoke(state)
    print(result)


if __name__ == '__main__':
    asyncio.run(main())
