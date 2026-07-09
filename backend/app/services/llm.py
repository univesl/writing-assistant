import asyncio
import time
from typing import AsyncGenerator, Literal, List, Dict, Union
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from llm import LLMAPIClient, get_llm_client

DEFAULT_MODEL = "qwen"
_clients = {}
_STREAM_END = object()


def _next_stream_chunk(stream_gen):
    try:
        return next(stream_gen)
    except StopIteration:
        return _STREAM_END


def get_client(model_type: str = None):
    """根据模型类型获取对应的客户端"""
    if model_type is None:
        model_type = DEFAULT_MODEL
    if model_type not in _clients:
        _clients[model_type] = get_llm_client(model_type)
    return _clients[model_type]


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
        print(f"[LLM] 开始流式调用，model={llm_model}")
        
        loop = asyncio.get_running_loop()
        client = get_client(llm_model)
        
        def sync_stream():
            try:
                if isinstance(messages_or_prompt, list):
                    # 直接使用 messages 列表
                    result = client.stream_chat_with_messages(messages_or_prompt)
                else:
                    # 兼容旧调用方式
                    result = client.stream_chat(messages_or_prompt, system_prompt=system_prompt)
                return result
            except Exception as e:
                print(f"[LLM] 同步调用失败：{e}")
                import traceback
                traceback.print_exc()
                raise
        
        stream_gen = await loop.run_in_executor(None, sync_stream)
        
        start_time = time.perf_counter()
        first_chunk_time = None
        chunk_count = 0
        while True:
            chunk = await loop.run_in_executor(None, _next_stream_chunk, stream_gen)
            if chunk is _STREAM_END:
                break
            chunk_count += 1
            if chunk:
                if first_chunk_time is None:
                    first_chunk_time = time.perf_counter()
                    print(f"[LLM] first chunk after {first_chunk_time - start_time:.2f}s")
                yield chunk
        
        total_time = time.perf_counter() - start_time
        print(f"[LLM] stream complete, chunks={chunk_count}, total={total_time:.2f}s")
    except Exception as e:
        print(f"[LLM] 调用失败：{e}")
        import traceback
        traceback.print_exc()
        yield f"生成失败：{str(e)}"


async def stream_text(full_text: str, chunk_size: int = 1, delay: float = 0.01) -> AsyncGenerator[str, None]:
    """本地流式输出文本（作为备用）"""
    for i in range(0, len(full_text), chunk_size):
        await asyncio.sleep(delay)
        yield full_text[i : i + chunk_size]
