import httpx
from mcp.server import FastMCP
import logging
import time
import os
import json
from datetime import datetime
from logging.handlers import RotatingFileHandler

# 创建 logs 目录（如果不存在）
logs_dir = "logs"
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)

# 创建 search_records 目录（用于保存搜索记录JSON文件）
records_dir = os.path.join(logs_dir, "search_records")
if not os.path.exists(records_dir):
    os.makedirs(records_dir)

# 生成日志文件名（按日期）
log_filename = os.path.join(logs_dir, f"web_search_{datetime.now().strftime('%Y%m%d')}.log")

# 配置日志
logger = logging.getLogger("web_search")
logger.setLevel(logging.INFO)

# 日志格式
log_format = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S.%f')

# 控制台处理器
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_format)
logger.addHandler(console_handler)

# 文件处理器（限制大小为5MB，最多保留5个备份文件）
file_handler = RotatingFileHandler(
    log_filename, 
    maxBytes=5*1024*1024,  # 5MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(log_format)
logger.addHandler(file_handler)

# 确保不重复记录日志（避免重复日志输出）
logger.propagate = False

# 记录启动信息
logger.info("=" * 50)
logger.info(f"Web搜索服务启动 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
logger.info("=" * 50)

# 初始化 FastMCP 服务器
app = FastMCP('web-search', host='127.0.0.1', port=3000)

def save_search_record(request_id, data):
    """
    将搜索记录保存为JSON文件
    
    Args:
        request_id: 请求ID，用于生成文件名
        data: 要保存的数据字典
    """
    try:
        filename = os.path.join(records_dir, f"search_{request_id}.json")
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"[{request_id}] 搜索记录已保存至: {filename}")
    except Exception as e:
        logger.error(f"[{request_id}] 保存搜索记录失败: {str(e)}")

@app.tool()
async def web_search(query: str) -> str:
    """
    搜索互联网内容

    Args:
        query: 要搜索内容

    Returns:
        搜索结果的总结
    """
    start_time = time.time()
    request_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
    logger.info(f"[{request_id}] 收到搜索请求: '{query}'")
    
    # 初始化记录数据
    record_data = {
        "request_id": request_id,
        "timestamp": datetime.now().isoformat(),
        "query": query,
        "metrics": {
            "start_time": start_time,
            "api_call_time": None,
            "total_time": None,
        },
        "status": "pending",
        "result": None,
        "error": None
    }

    try:
        async with httpx.AsyncClient() as client:
            logger.info(f"[{request_id}] 正在调用大模型 API...")
            
            api_start_time = time.time()
            response = await client.post(
                'https://open.bigmodel.cn/api/paas/v4/tools',
                headers={'Authorization': '5e37af5f39c18c88ef3a89e4b45da86e.OoaoX8822YSCXM9P'},
                json={
                    'tool': 'web-search-pro',
                    'messages': [
                        {'role': 'user', 'content': query}
                    ],
                    'stream': False
                }
            )
            api_end_time = time.time()
            api_call_time = api_end_time - api_start_time
            
            # 更新记录
            record_data["metrics"]["api_call_time"] = api_call_time
            
            logger.info(f"[{request_id}] API 调用完成，耗时: {api_call_time:.2f}秒，状态码: {response.status_code}")
            
            if response.status_code != 200:
                error_msg = f"搜索请求失败: HTTP {response.status_code}"
                logger.error(f"[{request_id}] API 返回错误状态码: {response.status_code}, 响应: {response.text}")
                
                # 更新记录
                record_data["status"] = "error"
                record_data["error"] = error_msg
                record_data["raw_response"] = response.text
                
                # 保存记录
                end_time = time.time()
                record_data["metrics"]["total_time"] = end_time - start_time
                save_search_record(request_id, record_data)
                
                return error_msg
            
            try:
                response_json = response.json()
                logger.info(f"[{request_id}] 成功解析 API 响应 JSON")
                
                # 保存原始响应（但不包括内容以减小文件大小）
                record_data["raw_response_status"] = "success"
            except Exception as e:
                error_msg = f"搜索结果解析失败: {str(e)}"
                logger.error(f"[{request_id}] 解析 JSON 失败: {str(e)}")
                
                # 更新记录
                record_data["status"] = "error"
                record_data["error"] = error_msg
                
                # 保存记录
                end_time = time.time()
                record_data["metrics"]["total_time"] = end_time - start_time
                save_search_record(request_id, record_data)
                
                return error_msg
            
            res_data = []
            choices_count = len(response_json.get('choices', []))
            logger.info(f"[{request_id}] 收到 {choices_count} 个搜索结果集")
            
            # 记录结果统计
            result_stats = {
                "choices_count": choices_count,
                "results_found": 0
            }
            record_data["result_stats"] = result_stats
            
            for choice_idx, choice in enumerate(response_json.get('choices', [])):
                tool_calls = choice.get('message', {}).get('tool_calls', [])
                logger.info(f"[{request_id}] 结果集 {choice_idx+1}: 包含 {len(tool_calls)} 个工具调用")
                
                for message in tool_calls:
                    search_results = message.get('search_result', [])
                    if not search_results:
                        continue
                    
                    result_count = len(search_results)
                    logger.info(f"[{request_id}] 发现 {result_count} 个搜索结果")
                    record_data["result_stats"]["results_found"] += result_count
                    
                    for result in search_results:
                        res_data.append(result['content'])
            
            result = '\n\n\n'.join(res_data)
            end_time = time.time()
            total_time = end_time - start_time
            
            # 更新记录
            record_data["status"] = "success"
            record_data["result"] = result
            record_data["metrics"]["total_time"] = total_time
            
            # 保存记录
            save_search_record(request_id, record_data)
            
            logger.info(f"[{request_id}] 搜索完成，总耗时: {total_time:.2f}秒，结果长度: {len(result)} 字符")
            return result
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[{request_id}] 搜索过程中发生错误: {error_msg}")
        
        # 更新记录
        record_data["status"] = "error"
        record_data["error"] = error_msg
        
        # 保存记录
        end_time = time.time()
        record_data["metrics"]["total_time"] = end_time - start_time
        save_search_record(request_id, record_data)
        
        return f"搜索过程中发生错误: {error_msg}"

if __name__ == "__main__":
    logger.info("启动 MCP 服务器，使用 stdio 通信...")
    try:
        app.run(transport='stdio')
    except Exception as e:
        logger.error(f"MCP 服务器运行出错: {str(e)}")
        raise