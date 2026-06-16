import asyncio
from typing import AsyncGenerator, Literal, List, Dict, Union
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from llm import LLMAPIClient, get_llm_client

DEFAULT_MODEL = "qwen"


def get_client(model_type: str = None):
    """根据模型类型获取对应的客户端"""
    if model_type is None:
        model_type = DEFAULT_MODEL
    return get_llm_client(model_type)


async def stream_text_from_llm(
    messages_or_prompt: Union[str, List[Dict[str, str]]],
    system_prompt: str = None,
    llm_model: str = DEFAULT_MODEL,
) -> AsyncGenerator[str, None]:
    """从LLM流式获取文本响应
    
    Args:
        messages_or_prompt: 可以是 messages 列表 [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
                           也可以是纯字符串 prompt（兼容旧调用）
        system_prompt: 系统提示词（仅当 messages_or_prompt 是字符串时使用）
        llm_model: LLM模型类型
    """
    try:
        print(f"[DEBUG] 调用LLM")
        
        loop = asyncio.get_running_loop()
        client = get_client(llm_model)
        
        def sync_stream():
            try:
                print("[DEBUG] 开始同步调用LLM API")
                if isinstance(messages_or_prompt, list):
                    # 直接使用 messages 列表
                    result = client.stream_chat_with_messages(messages_or_prompt)
                else:
                    # 兼容旧调用方式
                    result = client.stream_chat(messages_or_prompt, system_prompt=system_prompt)
                print(f"[DEBUG] 获取到流式生成器：{type(result)}")
                return result
            except Exception as e:
                print(f"[DEBUG] 同步调用LLM API失败：{e}")
                import traceback
                traceback.print_exc()
                raise
        
        print("[DEBUG] 开始执行线程池任务")
        stream_gen = await loop.run_in_executor(None, sync_stream)
        print("[DEBUG] 成功获取流式生成器")
        
        print("[DEBUG] 开始遍历流式生成器")
        chunk_count = 0
        for chunk in stream_gen:
            chunk_count += 1
            print(f"[DEBUG] LLM返回片段 #{chunk_count}：{chunk[:50] if chunk and len(chunk) > 50 else chunk}...")
            if chunk:
                yield chunk
            else:
                print("[DEBUG] 接收到空片段")
        
        print(f"[DEBUG] LLM流式调用完成，共接收 {chunk_count} 个片段")
    except Exception as e:
        print(f"[DEBUG] LLM调用失败：{e}")
        import traceback
        traceback.print_exc()
        yield f"生成失败：{str(e)}"


async def stream_text(full_text: str, chunk_size: int = 1, delay: float = 0.01) -> AsyncGenerator[str, None]:
    """本地流式输出文本（作为备用）"""
    for i in range(0, len(full_text), chunk_size):
        await asyncio.sleep(delay)
        yield full_text[i : i + chunk_size]