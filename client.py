import asyncio
import json

from mcp import Client


async def main():
    async with Client("http://localhost:8000/mcp") as client:
        # Discover what this server offers.
        available = await client.list_tools()

        for tool in available.tools:
            print("Tool:", tool.name)
            print("Description:", tool.description)
            print("Input schema:", json.dumps(tool.input_schema, indent=2))

        # Request execution through MCP.
        result = await client.call_tool(
            "get_order_status",
            {"order_id": "1042"},
        )

        print("Tool error:", result.is_error)
        print("Structured content:", result.structured_content)
        print("Output schema:", json.dumps(tool.output_schema, indent=2))

        for block in result.content:
            print("Content block:", block)


if __name__ == "__main__":
    asyncio.run(main())