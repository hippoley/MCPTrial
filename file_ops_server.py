from mcp.server import FastMCP
from mcp.types import SamplingMessage, TextContent
import os

# 创建FastMCP服务器实例
app = FastMCP('file_server')

@app.tool()
async def delete_file(file_path: str) -> str:
    """
    删除指定路径的文件，但会先请求用户确认
    
    Args:
        file_path: 要删除的文件路径
    
    Returns:
        操作结果描述
    """
    # 检查文件是否存在
    if not os.path.exists(file_path):
        return f"错误: 文件 '{file_path}' 不存在"
    
    # 步骤1: 创建用户确认消息
    # 这里使用SamplingMessage触发客户端的sampling_callback函数
    result = await app.get_context().session.create_message(
        messages=[
            SamplingMessage(
                role='user', 
                content=TextContent(
                    type='text', 
                    text=f'确认删除文件: {file_path} ? (Y/N): '
                )
            )
        ],
        max_tokens=100
    )

    # 步骤2: 根据用户响应执行操作
    if result.content.text.upper() == 'Y':
        try:
            os.remove(file_path)
            return f"成功: 文件 '{file_path}' 已删除"
        except Exception as e:
            return f"错误: 删除文件时发生异常 - {str(e)}"
    else:
        return f"操作已取消: 文件 '{file_path}' 未删除"

if __name__ == '__main__':
    app.run(transport='stdio') 