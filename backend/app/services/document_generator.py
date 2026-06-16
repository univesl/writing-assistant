"""
公文文档生成服务
使用 KnG RAG API 进行知识库检索，结合大模型生成文档
"""

import os
import json
import time
import requests
from typing import List, Dict, Any, Optional, AsyncGenerator
from .kng_rag_service import get_kng_rag_service
from .prompt_builder import build_prompt


async def generate_document_async(
    topic: str,
    requirements: str = "",
    model_name: str = "qwen2.5-72b",
    use_knowledge_base: bool = True,
    retrieval_mode: str = "local",
    top_k: int = 60,
    chunk_top_k: int = 5,
    reference_content: str = "",
) -> Dict[str, Any]:
    """
    基于 KnG RAG 检索生成文档
    
    Args:
        topic: 文档主题/标题
        requirements: 特殊要求
        model_name: 使用的模型名称
        use_knowledge_base: 是否使用知识库
        retrieval_mode: 检索模式 (hybrid, local, global, mix, naive)
        top_k: 检索数量
        chunk_top_k: 文本块数量
        reference_content: 参考文档内容，优先级高于知识库但低于用户要求
        
    Returns:
        {"content": "生成的文档", "references": ["参考文件列表"], "timing": {...}}
    """
    total_start = time.time()
    timing_info = {
        "step1_rag_retrieval_seconds": 0,
        "step2_build_prompt_seconds": 0,
        "step3_llm_generation_seconds": 0,
        "total_seconds": 0
    }
    
    print(f"\n[文档生成] ===== 开始文档生成流程 =====")
    print(f"[文档生成] 主题: {topic}")
    print(f"[文档生成] 使用知识库: {use_knowledge_base}, 模式: {retrieval_mode}")
    
    knowledge_base_content = ""
    references = []
    
    # Step 1: 使用 KnG RAG 检索知识库
    step1_start = time.time()
    if use_knowledge_base:
        try:
            service = get_kng_rag_service()
            
            if service.is_ready():
                print(f"[文档生成] Step 1: 正在进行 RAG 检索...")
                retrieval_result = service.retrieve_for_document_generation(
                    topic=topic,
                    requirements=requirements,
                    mode=retrieval_mode,
                )
                
                knowledge_base_content = retrieval_result.get("content", "")
                # 获取KNG返回的时间信息
                kng_timing = retrieval_result.get("timing", {})
                print(f"[文档生成] Step 1: RAG 检索完成 (KNG耗时: {kng_timing.get('total_seconds', 'N/A')}s)")
                
                # 提取参考信息（从返回内容中解析）
                if "参考" in knowledge_base_content or "来源" in knowledge_base_content:
                    references.append("知识库检索结果")
            else:
                print(f"[文档生成] KnG 服务未就绪，跳过知识库检索")
                
        except Exception as e:
            print(f"[文档生成] 知识库检索失败: {e}")
            # 继续生成，只是没有知识库内容
    
    timing_info["step1_rag_retrieval_seconds"] = round(time.time() - step1_start, 2)
    print(f"[文档生成] Step 1 耗时: {timing_info['step1_rag_retrieval_seconds']}s")
    
    timing_info["total_seconds"] = round(time.time() - total_start, 2)
    print(f"[文档生成] ===== 文档生成完成，总耗时: {timing_info['total_seconds']}s =====\n")
    
    return {
        "content": knowledge_base_content,
        "references": references,
        "model_used": model_name,
        "retrieval_info": {
            "mode": retrieval_mode,
            "used_knowledge_base": use_knowledge_base and bool(knowledge_base_content),
        },
        "timing": timing_info
    }


# LLM API 配置（使用h3i平台）
MODEL_API_BASE = os.getenv("MODEL_API_BASE", "http://model.ic.h3i.buaa.edu.cn")
MODEL_API_KEY = os.getenv("MODEL_API_KEY", "")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "Qwen2.5-72B-Instruct")


def _call_llm_with_messages(messages: list, model_name: str) -> str:
    """调用大模型生成内容（使用 messages 列表）"""
    try:
        url = f"{MODEL_API_BASE}/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {MODEL_API_KEY}"
        }
        
        model = DEFAULT_MODEL
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": 4000,
            "temperature": 0.7
        }
        
        print(f"[文档生成] 调用模型: {model}")
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        
        result = response.json()
        if "choices" in result and len(result["choices"]) > 0:
            msg = result["choices"][0]["message"]
            # Qwen3 可能返回 reasoning_content
            content = msg.get("content") or msg.get("reasoning_content", "")
            print(f"[文档生成] 模型生成成功，长度: {len(content)}")
            return content
        else:
            return "生成失败：模型返回结果为空"
            
    except Exception as e:
        print(f"[文档生成] 模型调用失败: {e}")
        return f"生成失败：{str(e)}"


def list_available_models() -> List[Dict[str, str]]:
    """获取可用的模型列表"""
    return [
        {"id": "Qwen2.5-72B-Instruct", "name": "Qwen2.5-72B (统一模型)"},
    ]


async def retrieve_knowledge_base_content(
    topic: str,
    mode: str = "local",
) -> Dict[str, Any]:
    """
    直接检索知识库内容
    
    Args:
        topic: 查询主题
        mode: 检索模式
        
    Returns:
        检索结果
    """
    try:
        service = get_kng_rag_service()
        
        if not service.is_ready():
            return {
                "content": "",
                "error": "KnG 服务未就绪",
            }
        
        result = service.retrieve_for_document_generation(
            topic=topic,
            mode=mode,
        )
        
        return result
        
    except Exception as e:
        return {
            "content": "",
            "error": str(e),
        }


async def _call_llm_stream(prompt, model_name):
    """
    流式调用大模型生成内容，每次 yield 一个文本块
    使用 asyncio.to_thread 在后台线程中执行同步 requests 请求
    """
    import asyncio
    
    url = f"{MODEL_API_BASE}/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MODEL_API_KEY}"
    }
    
    model = DEFAULT_MODEL
    
    payload = {
        "model": model,
        "messages": prompt if isinstance(prompt, list) else [
            {"role": "system", "content": "你是一位精通北航（北京航空航天大学）公文写作的专家。你的任务是根据用户提供的主题和要求，以**北航真实公文**为参考标准，撰写正式、规范的公文。\n\n核心原则：\n1. 严格参照北航真实公文的文风、用语习惯和格式规范\n2. 公文体裁涵盖：通知、报告、请示、函、纪要、批复、决定、意见等\n3. 语言严谨、准确、简练，体现高校行政公文的正式性和权威性\n4. 保持客观中立的官方口吻，避免主观评价性语言\n5. 落款居右，发文单位在上、日期在下，日期用中文数字"},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 4000,
        "temperature": 0.7,
        "stream": True
    }
    
    print(f"[流式调用] 调用模型: {model}")
    
    queue = asyncio.Queue()
    
    def _sync_request():
        try:
            response = requests.post(url, headers=headers, json=payload, stream=True, timeout=180)
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        if "choices" in data and len(data["choices"]) > 0:
                            delta = data["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                loop.call_soon_threadsafe(queue.put_nowait, ("chunk", content))
                    except json.JSONDecodeError:
                        continue
            
            print(f"[流式调用] 模型生成完成")
        except Exception as e:
            print(f"[流式调用] 模型调用失败: {e}")
            loop.call_soon_threadsafe(queue.put_nowait, ("error", str(e)))
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, ("done", None))
    
    loop = asyncio.get_event_loop()
    task = loop.run_in_executor(None, _sync_request)
    
    while True:
        msg_type, data = await queue.get()
        if msg_type == "chunk":
            yield data
        elif msg_type == "error":
            yield f"生成失败：{data}"
            break
        elif msg_type == "done":
            break
    
    await task


def _build_summary_prompt(content):
    """构建摘要提示词"""
    return f"请为以下公文生成一个简短的摘要（100字以内），概括核心内容和要点：\n\n{content}"


async def generate_reply_document(
    topic: str,
    requirements: str,
    original_content: str,
    extracted_fields: dict,
    model_name: str = DEFAULT_MODEL,
    use_knowledge_base: bool = True,
    top_k: int = 3,
) -> AsyncGenerator[str, None]:
    """生成回函"""
    
    kb_content = ""
    if use_knowledge_base:
        try:
            kb_result = await retrieve_knowledge_base_content(topic or requirements)
            kb_content = kb_result.get("content", "")
        except Exception as e:
            print(f"[WARN] 知识库检索失败: {e}")
    
    # 使用 PromptBuilder 构建回函 prompt
    messages = build_prompt(
        mode="reply",
        style="general",
        data={
            "user_requirements": requirements,
            "reference_content": original_content,
            "rag_content": kb_content,
            "extracted_fields": extracted_fields,
            "style": "general",
        },
    )
    
    async for chunk in _call_llm_stream(messages, model_name):
        yield chunk


async def generate_reference_document(
    reference_content: str,
    reference_filename: str = "",
    generate_type: str = "general",
    topic: str = "",
    requirements: str = "",
    model_name: str = DEFAULT_MODEL,
    use_knowledge_base: bool = True,
    top_k: int = 3,
) -> AsyncGenerator[str, None]:
    """参考写作：根据上传文件生成公文（流式）"""
    
    kb_content = ""
    if use_knowledge_base:
        try:
            kb_result = await retrieve_knowledge_base_content(topic or requirements or reference_filename)
            kb_content = kb_result.get("content", "")
        except Exception as e:
            print(f"[WARN] 知识库检索失败: {e}")
    
    # 映射 generate_type 到 PromptBuilder 的 mode
    mode_map = {
        "reply": "reply",
        "imitate": "imitate",
        "general": "general_ref",
    }
    mode = mode_map.get(generate_type, "general_ref")
    
    # 使用 PromptBuilder 统一构建 prompt
    messages = build_prompt(
        mode=mode,
        style="general",
        data={
            "user_requirements": requirements or topic,
            "reference_content": reference_content,
            "reference_filename": reference_filename,
            "rag_content": kb_content,
            "style": "general",
        },
    )
    
    async for chunk in _call_llm_stream(messages, model_name):
        yield chunk