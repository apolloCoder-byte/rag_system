from dotenv import load_dotenv

from langchain_tavily import TavilySearch
from mcp.server.fastmcp import FastMCP

load_dotenv()

tavily_search_tool = TavilySearch(max_results=3)

mcp = FastMCP("web search tool")


@mcp.tool()
async def tavily_search(question: str):
    """use tavily search tool to retrieve information for Internet"""
    results = tavily_search_tool.invoke({"query": question})
    results_list = results["results"]
    joined_result = "\n---\n".join(item["content"] for item in results_list)
    data = {"result": joined_result}
    return data


@mcp.tool()
async def test(a: int):
    data = {"result": f"this is a fake result: {a}"}
    return data


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
