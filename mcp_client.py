import asyncio

from mcp.client.stdio import stdio_client
from mcp import ClientSession, StdioServerParameters


async def main():
    # 为 stdio 连接创建服务器参数
    server_params = StdioServerParameters(
        # 服务器执行的命令，这里我们使用 uv 来运行 web_search.py
        command='uv',
        # 运行的参数
        args=['run', 'web_search.py'],
        # 环境变量，默认为 None，表示使用当前环境变量
        env=None
    )

    # 创建 stdio 客户端
    async with stdio_client(server_params) as (stdio, write):
        # 创建 ClientSession 对象
        async with ClientSession(stdio, write) as session:
            # 初始化 ClientSession
            await session.initialize()

            # 列出可用的工具
            response = await session.list_tools()
            print("可用工具列表:")
            for tool in response.tools:
                print(f" - {tool.name}: {tool.description}")

            # 循环接收用户输入并调用工具
            while True:
                query = input("\n请输入搜索内容(输入'quit'退出): ").strip()
                
                if query.lower() == 'quit':
                    break
                    
                print(f"正在搜索: {query}")
                # 调用工具
                response = await session.call_tool('web_search', {'query': query})
                print("\n搜索结果:")
                print(response.content[0].text)


if __name__ == '__main__':
    asyncio.run(main()) 