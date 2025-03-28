import asyncio
from mcp.client.stdio import stdio_client
from mcp import ClientSession, StdioServerParameters
from mcp.shared.context import RequestContext
from mcp.types import (
    TextContent,
    CreateMessageRequestParams,
    CreateMessageResult,
)

# 步骤1: 定义sampling回调函数
# 当服务端发送SamplingMessage时，这个函数会被调用
async def sampling_callback(
        context: RequestContext[ClientSession, None],
        params: CreateMessageRequestParams,
):
    # 显示服务端的确认消息，并获取用户输入
    user_input = input(params.messages[0].content.text)
    
    # 将用户输入返回给服务端
    return CreateMessageResult(
        role='user',
        content=TextContent(
            type='text',
            text=user_input.strip()
        ),
        model='user-input',
        stopReason='endTurn'
    )

async def main():
    # 步骤2: 配置服务器参数
    server_params = StdioServerParameters(
        command='uv',
        args=['run', 'file_ops_server.py'],
        env=None
    )

    # 步骤3: 连接到服务器并创建会话
    async with stdio_client(server_params) as (stdio, write):
        # 创建会话并设置sampling_callback
        async with ClientSession(
                stdio, write,
                sampling_callback=sampling_callback  # 关键部分: 传入回调函数
        ) as session:
            await session.initialize()
            
            # 步骤4: 获取和显示可用工具
            tools_response = await session.list_tools()
            print("可用工具:")
            for tool in tools_response.tools:
                print(f" - {tool.name}: {tool.description}")
            
            # 步骤5: 交互式操作循环
            while True:
                file_path = input("\n请输入要删除的文件路径（输入'quit'退出）: ")
                
                if file_path.lower() == 'quit':
                    break
                
                # 调用删除文件工具
                response = await session.call_tool(
                    'delete_file',
                    {'file_path': file_path}
                )
                
                # 显示结果
                print("\n操作结果:")
                print(response.content[0].text)

if __name__ == '__main__':
    asyncio.run(main()) 