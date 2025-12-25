import asyncio
from typing import AsyncGenerator, Literal, List, Dict
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

# 导入LLM API客户端
from llm import LLMAPIClient

# 初始化LLM客户端实例
llm_client = LLMAPIClient()

async def build_quick_output(prompt: str, model_type: Literal["general", "creative"]) -> str:
    """调用LLM生成快速写作内容"""
    try:
        if model_type == "creative":
            system_prompt = "你是一个创意文案专家，请根据用户提供的提示生成富有创意和吸引力的文案。"
        else:
            system_prompt = "你是一个专业文案撰写人，请根据用户提供的提示生成结构完整、表达清晰的通用文案。"
        
        # 使用异步调用获取完整响应
        response = await llm_client.async_chat(prompt, system_prompt=system_prompt)
        return response
    except Exception as e:
        # 失败时返回错误信息
        return f"生成失败：{str(e)}"

async def build_step_output(product_name: str, selling_points: list[str], style: str, length: str) -> str:
    """调用LLM生成分步写作内容"""
    try:
        sp = "；".join([s for s in selling_points if s.strip()]) or "（暂无卖点）"
        
        # 构建提示词
        prompt = (
            f"请为产品 '{product_name}' 生成一份文案，要求如下：\n"
            f"- 产品卖点：{sp}\n"
            f"- 写作风格：{style}\n"
            f"- 内容长度：{length}\n"
            f"请确保文案结构清晰、重点突出。"
        )
        
        system_prompt = "你是一个专业的产品文案策划师，请根据用户提供的产品信息生成结构化的产品文案。"
        
        # 使用异步调用获取完整响应
        response = await llm_client.async_chat(prompt, system_prompt=system_prompt)
        return response
    except Exception as e:
        # 失败时返回错误信息
        return f"生成失败：{str(e)}"

async def polish_text(content: str, polish_type: str) -> str:
    """调用LLM进行文本校对润色"""
    try:
        # 根据不同的润色类型构建不同的提示词
        if polish_type == "check":
            prompt = f"请检查以下文本的语法和拼写错误，并进行修正：\n\n{content}"
            system_prompt = "你是一个专业的文本校对员，请检查用户提供的文本并修正语法和拼写错误。"
        elif polish_type == "optimize":
            prompt = f"请优化以下文本的表达，使其更加流畅自然：\n\n{content}"
            system_prompt = "你是一个专业的文本优化师，请优化用户提供的文本表达，使其更加流畅自然。"
        else:  # expand
            prompt = f"请扩写以下文本，增加更多细节和背景信息：\n\n{content}"
            system_prompt = "你是一个专业的文本扩写师，请扩写用户提供的文本，增加更多细节和背景信息。"
        
        # 使用异步调用获取完整响应
        response = await llm_client.async_chat(prompt, system_prompt=system_prompt)
        return response
    except Exception as e:
        # 失败时返回原始内容
        return content + f"\n\n（润色失败：{str(e)}）"

async def stream_text_from_llm(question: str, system_prompt: str = None) -> AsyncGenerator[str, None]:
    """从LLM流式获取文本响应"""
    try:
        print(f"[DEBUG] 调用LLM，问题：{question}")
        print(f"[DEBUG] 系统提示词：{system_prompt}")
        
        # 使用线程池执行同步的流式调用
        loop = asyncio.get_running_loop()
        
        def sync_stream():
            try:
                print("[DEBUG] 开始同步调用LLM API")
                result = llm_client.stream_chat(question, system_prompt=system_prompt)
                print(f"[DEBUG] 获取到流式生成器：{type(result)}")
                return result
            except Exception as e:
                print(f"[DEBUG] 同步调用LLM API失败：{e}")
                import traceback
                traceback.print_exc()
                raise
        
        # 获取流式生成器
        print("[DEBUG] 开始执行线程池任务")
        stream_gen = await loop.run_in_executor(None, sync_stream)
        print("[DEBUG] 成功获取流式生成器")
        
        # 逐块返回
        print("[DEBUG] 开始遍历流式生成器")
        chunk_count = 0
        for chunk in stream_gen:
            chunk_count += 1
            print(f"[DEBUG] LLM返回片段 #{chunk_count}：{chunk}")
            if chunk:
                yield chunk
            else:
                print("[DEBUG] 接收到空片段")
        
        print(f"[DEBUG] LLM流式调用完成，共接收 {chunk_count} 个片段")
    except Exception as e:
        print(f"[DEBUG] LLM调用失败：{e}")
        import traceback
        traceback.print_exc()
        # 失败时返回错误信息
        yield f"生成失败：{str(e)}"

async def stream_text(full_text: str, chunk_size: int = 1, delay: float = 0.01) -> AsyncGenerator[str, None]:
    """本地流式输出文本（作为备用）"""
    for i in range(0, len(full_text), chunk_size):
        await asyncio.sleep(delay)
        yield full_text[i : i + chunk_size]
