"""
Run from the repository root:
    uv run examples/snippets/clients/streamable_basic.py
"""

import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():
    # Connect to a streamable HTTP server
    async with streamablehttp_client("http://localhost:8000/mcp") as (
        read_stream,
        write_stream,
        get_session_id,
    ):
        # Create a session using the client streams
        async with ClientSession(read_stream, write_stream) as session:
            # Initialize the connection
            await session.initialize()

            # get session id
            session_id = get_session_id()
            print(f"Session ID: {session_id}")

            # call tool
            result = await session.call_tool("stream", {"name": "John"})

            print(result)


if __name__ == "__main__":
    asyncio.run(main())
