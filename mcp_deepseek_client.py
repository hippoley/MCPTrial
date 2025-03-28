import json
import asyncio
import os
from typing import Optional
from contextlib import AsyncExitStack

from openai import OpenAI
from dotenv import load_dotenv

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPClient:
    def __init__(self):
        # 加载环境变量
        load_dotenv()
        
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.client = OpenAI()
        
        # 检查环境变量是否设置
        required_env_vars = ["OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL"]
        for var in required_env_vars:
            if not os.getenv(var):
                print(f"错误: 环境变量 {var} 未设置。请检查 .env 文件。")

    async def connect_to_server(self):
        """连接到MCP服务器"""
        server_params = StdioServerParameters(
            command='uv',
            args=['run', 'web_search.py'],
            env=None
        )

        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params))
        stdio, write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(stdio, write))

        await self.session.initialize()
        print("成功连接到MCP服务器")

    async def process_query(self, query: str) -> str:
        """处理用户查询，通过DeepSeek调用MCP工具"""
        # 系统提示词，指导模型使用工具
        system_prompt = (
            "You are a helpful assistant."
            "You have the function of online search. "
            "Please MUST call web_search tool to search the Internet content before answering."
            "Please do not lose the user's question information when searching,"
            "and try to maintain the completeness of the question content as much as possible."
            "When there is a date related question in the user's question," 
            "please use the search function directly to search and PROHIBIT inserting specific time."
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]

        # 获取MCP服务器的工具列表
        response = await self.session.list_tools()
        print(f"获取到 {len(response.tools)} 个可用工具")
        
        # 格式化工具为OpenAI兼容格式
        available_tools = [{
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": json.loads(tool.inputSchema)
            }
        } for tool in response.tools]

        try:
            # 请求DeepSeek模型，传入工具定义
            print("正在请求DeepSeek模型...")
            response = self.client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL"),
                messages=messages,
                tools=available_tools
            )

            # 处理返回的内容
            content = response.choices[0]
            if content.message.tool_calls:
                # 如果需要使用工具，解析工具调用
                tool_call = content.message.tool_calls[0]
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                print(f"\n调用工具: {tool_name}")
                print(f"参数: {tool_args}")
                
                # 确保参数使用正确的键名
                if tool_name == "web_search" and "search_term" in tool_args:
                    tool_args["query"] = tool_args.pop("search_term")
                
                # 执行工具调用
                result = await self.session.call_tool(tool_name, tool_args)
                
                # 将工具调用结果添加到消息历史
                messages.append(content.message.model_dump())
                messages.append({
                    "role": "tool",
                    "content": result.content[0].text,
                    "tool_call_id": tool_call.id,
                })

                print("获取到工具调用结果，正在生成最终回答...")
                
                # 将工具执行结果返回给DeepSeek生成最终回答
                response = self.client.chat.completions.create(
                    model=os.getenv("OPENAI_MODEL"),
                    messages=messages,
                )
                return response.choices[0].message.content
            else:
                # 如果模型直接回答而不调用工具
                print("警告: 模型没有调用工具直接回答了问题")
                return content.message.content
                
        except Exception as e:
            print(f"调用API出错: {str(e)}")
            return f"抱歉，发生了错误: {str(e)}"

    async def chat_loop(self):
        """交互式聊天循环"""
        print("\n===== MCP DeepSeek 客户端 =====")
        print("输入'quit'退出\n")
        
        while True:
            try:
                query = input("\n问题: ").strip()

                if query.lower() == 'quit':
                    break

                response = await self.process_query(query)
                print("\n回答:")
                print(response)

            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"发生错误: {str(e)}")

    async def cleanup(self):
        """清理资源"""
        print("正在关闭连接...")
        await self.exit_stack.aclose()
        print("已关闭所有连接")


async def main():
    client = MCPClient()
    try:
        await client.connect_to_server()
        await client.chat_loop()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main()) 