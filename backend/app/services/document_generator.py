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
    
    # Step 2: 构建生成提示词
    step2_start = time.time()
    prompt = await _build_generation_prompt(
        topic=topic,
        requirements=requirements,
        knowledge_base_content=knowledge_base_content,
        reference_content=reference_content,
    )
    timing_info["step2_build_prompt_seconds"] = round(time.time() - step2_start, 2)
    print(f"[文档生成] Step 2 构建提示词耗时: {timing_info['step2_build_prompt_seconds']}s")
    
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


async def _build_generation_prompt(
    topic: str,
    requirements: str = "",
    knowledge_base_content: str = "",
    reference_content: str = "",
) -> str:
    """构建文档生成提示词"""
    
    prompt_parts = []
    
    # 主题
    prompt_parts.append(f"""## 主题
{topic}
""")
    
    # 特殊要求
    if requirements:
        prompt_parts.append(f"""## 特殊要求
{requirements}
""")
    
    # 参考文档内容（来自上传文件），优先级高于知识库但低于用户要求
    if reference_content:
        prompt_parts.append(f"""## 【参考文档内容】
以下内容为上传的参考文档，请作为本次公文撰写的重要参考依据，参考其中的文风、用语、结构和格式：

{reference_content}
""")
    
    # 北航真实公文参考（RAG 知识库检索结果）
    if knowledge_base_content:
        prompt_parts.append(f"""## 【北航真实公文参考】
以下内容来自北航校内真实公文档案知识库，请作为本次公文撰写的核心参考依据，严格参照其中的文风、用语和格式规范：

{knowledge_base_content}
""")
    else:
        prompt_parts.append("""## 【北航真实公文参考】
（本次未检索到北航真实公文参考，请依据你自身对公文写作规范的了解进行撰写）
""")
    
    # 写作要求
    prompt_parts.append("""## 写作要求
1. 语言正式、规范，符合《党政机关公文格式》国家标准（GB/T 9704-2012）
2. 结构清晰，逻辑严密，层次分明
3. 内容准确、详实，实事求是
4. 严格参照【北航真实公文参考】中的文风和表述方式
5. 如参考内容中包含与主题相关的具体段落，可直接适配使用""")
    
    # 格式规范
    prompt_parts.append("""## 格式规范
1. 标题：二号方正小标宋简体，居中
2. 正文：三号仿宋_GB2312，首行缩进2字符，行距28磅
3. 一级标题：三号黑体，顶格
4. 二级标题：三号楷体_GB2312，首行缩进2字符
5. 落款：居右（右空四格），发文单位在上，成文日期在下，日期用中文数字（如"二〇二五年X月X日"）
6. 页面：A4纸型，上白边37mm±1mm，下白边35mm±1mm，左白边28mm±1mm，右白边26mm±1mm

请直接输出完整的公文内容，不需要额外的解释说明。""")
    
    return "\n\n".join(prompt_parts)


# LLM API 配置（使用h3i平台）
MODEL_API_BASE = os.getenv("MODEL_API_BASE", "http://model.ic.h3i.buaa.edu.cn")
MODEL_API_KEY = os.getenv("MODEL_API_KEY", "")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "Qwen2.5-72B-Instruct")


async def _call_llm(prompt: str, model_name: str) -> str:
    """
    调用大模型生成内容
    RAG 检索使用 KnG，文档生成使用 h3i平台 Qwen2.5-72B
    """
    try:
        url = f"{MODEL_API_BASE}/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {MODEL_API_KEY}"
        }
        
        model = DEFAULT_MODEL
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "你是一位精通北航（北京航空航天大学）公文写作的专家。你的任务是根据用户提供的主题和要求，以**北航真实公文**为参考标准，撰写正式、规范的公文。\n\n核心原则：\n1. 严格参照用户提供的【北航真实公文参考】中的文风、用语习惯和格式规范\n2. 公文体裁涵盖：通知、报告、请示、函、纪要、批复、决定、意见等\n3. 语言严谨、准确、简练，体现高校行政公文的正式性和权威性\n4. 保持客观中立的官方口吻，避免主观评价性语言"},
                {"role": "user", "content": prompt}
            ],
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


def _build_reply_prompt(topic, requirements, original_content, extracted_fields, kb_content):
    """构建回函提示词"""
    fields_str = json.dumps(extracted_fields, ensure_ascii=False, indent=2) if extracted_fields else ""
    
    system_prompt = "你是一位精通北航（北京航空航天大学）公文写作的专家，专门负责撰写正式回函（复函）。\n"
    system_prompt += "你撰写的回函必须符合《党政机关公文格式》国家标准（GB/T 9704-2012）和北航公文规范。\n"
    system_prompt += "必须严格遵循以下回函格式：\n"
    system_prompt += "1. 标题：关于XXXX的复函\n"
    system_prompt += "2. 主送机关：来文单位的名称\n"
    system_prompt += "3. 正文：开头引用来文标题和文号（\"你单位《XXXX》（X字〔20XX〕X号）收悉\"），主体逐条回复，结尾用\"此复\"\n"
    system_prompt += "4. 落款：发文单位全称（居右）+ 发文日期（居右，用中文数字格式如\"二〇二五年X月X日\"）\n"
    system_prompt += "5. 语言要求：正式、严谨、规范，使用公文惯用语\n"
    
    user_prompt = ""
    if kb_content:
        user_prompt += f"【北航真实公文参考】\n{kb_content}\n\n"
    if original_content:
        user_prompt += f"【来文公文内容】\n{original_content}\n\n"
    if fields_str:
        user_prompt += f"【来文提取字段】\n{fields_str}\n\n"
    if topic:
        user_prompt += f"【回函主题】\n{topic}\n\n"
    if requirements:
        user_prompt += f"【特殊要求】\n{requirements}\n\n"
    
    return [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]


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
    
    prompt = _build_reply_prompt(topic, requirements, original_content, extracted_fields, kb_content)
    
    async for chunk in _call_llm_stream(prompt, model_name):
        yield chunk


def _build_reference_prompt(
    generate_type: str,
    reference_content: str,
    reference_filename: str,
    topic: str,
    requirements: str,
    kb_content: str,
) -> list:
    """构建参考写作提示词（三种模式：reply / imitate / general）"""
    
    if generate_type == "reply":
        system_prompt = "你是一位精通北航（北京航空航天大学）公文写作的专家，专门负责撰写正式回函（复函）。\n"
        system_prompt += "你撰写的回函必须符合《党政机关公文格式》国家标准（GB/T 9704-2012）和北航公文规范。\n"
        system_prompt += "必须严格遵循以下回函格式：\n"
        system_prompt += "1. 标题：关于XXXX的复函\n"
        system_prompt += "2. 主送机关：根据来文内容确定\n"
        system_prompt += "3. 正文：开头引用来文标题和文号（\"你单位《XXXX》（X字〔20XX〕X号）收悉\"），主体逐条回复，结尾用\"此复\"\n"
        system_prompt += "4. 落款：发文单位全称（居右）+ 发文日期（居右，用中文数字格式如\"二〇二五年X月X日\"）\n"
        system_prompt += "5. 语言要求：正式、严谨、规范，使用公文惯用语\n"
        
        user_prompt = ""
        if kb_content:
            user_prompt += f"【北航真实公文参考】\n{kb_content}\n\n"
        if reference_content:
            user_prompt += f"【来文公文内容】\n{reference_content}\n\n"
        if reference_filename:
            user_prompt += f"【来文文件名】\n{reference_filename}\n\n"
        if topic:
            user_prompt += f"【回函主题】\n{topic}\n\n"
        if requirements:
            user_prompt += f"【特殊要求】\n{requirements}\n\n"
        user_prompt += "\n请严格按照以下格式输出：\n\n---ARTICLE---\n[回函正文，使用Markdown]\n\n---SUMMARY---\n[100字以内总结]"
        
        return [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
    
    elif generate_type == "imitate":
        system_prompt = "你是一位精通北航（北京航空航天大学）公文写作的专家。\n"
        system_prompt += "请仔细学习以下参考文件的行文风格、结构组织、用语习惯和格式规范。\n"
        system_prompt += "然后，以相同的写作风格撰写一篇新的公文。\n"
        system_prompt += "\n无论参考文件的格式如何，你撰写的公文必须符合以下北航公文规范：\n"
        system_prompt += "1. 标题：居中，简洁明确，概括全文主旨\n"
        system_prompt += "2. 正文：语言正式、严谨、规范，首行缩进2字符\n"
        system_prompt += "3. 结构：层次分明，逻辑严密，使用公文惯用语\n"
        system_prompt += "4. 落款：发文单位全称（居右）+ 发文日期（居右，用中文数字格式如\"二〇二五年X月X日\"）\n"
        system_prompt += "5. 行文风格：客观中立，实事求是，保持高校行政公文的正式性和权威性\n"
        
        user_prompt = ""
        if kb_content:
            user_prompt += f"【北航真实公文参考】\n{kb_content}\n\n"
        if reference_content:
            user_prompt += f"【参考范文（请学习其风格）】\n{reference_content}\n\n"
        if reference_filename:
            user_prompt += f"【参考文件名】\n{reference_filename}\n\n"
        if topic:
            user_prompt += f"【新公文主题】\n{topic}\n\n"
        if requirements:
            user_prompt += f"【特殊要求】\n{requirements}\n\n"
        user_prompt += "\n请严格按照以下格式输出：\n\n---ARTICLE---\n[正文，使用Markdown]\n\n---SUMMARY---\n[100字以内总结]"
        
        return [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
    
    else:
        system_prompt = "你是一位精通北航（北京航空航天大学）公文写作的专家。\n"
        system_prompt += "请根据参考文档内容，撰写一篇相关的正式公文。\n"
        system_prompt += "\n撰写的公文必须符合以下北航公文规范：\n"
        system_prompt += "1. 标题：居中，简洁明确，概括全文主旨\n"
        system_prompt += "2. 正文：语言正式、严谨、规范，首行缩进2字符\n"
        system_prompt += "3. 结构：层次分明，逻辑严密，使用公文惯用语\n"
        system_prompt += "4. 落款：发文单位全称（居右）+ 发文日期（居右，用中文数字格式如\"二〇二五年X月X日\"）\n"
        system_prompt += "5. 行文风格：客观中立，实事求是，保持高校行政公文的正式性和权威性\n"
        
        user_prompt = ""
        if kb_content:
            user_prompt += f"【北航真实公文参考】\n{kb_content}\n\n"
        if reference_content:
            user_prompt += f"【参考文档内容】\n{reference_content}\n\n"
        if reference_filename:
            user_prompt += f"【参考文件名】\n{reference_filename}\n\n"
        if topic:
            user_prompt += f"【公文主题】\n{topic}\n\n"
        if requirements:
            user_prompt += f"【特殊要求】\n{requirements}\n\n"
        user_prompt += "\n请严格按照以下格式输出：\n\n---ARTICLE---\n[正文，使用Markdown]\n\n---SUMMARY---\n[100字以内总结]"
        
        return [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]


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
    
    prompt = _build_reference_prompt(
        generate_type, reference_content, reference_filename,
        topic, requirements, kb_content
    )
    
    async for chunk in _call_llm_stream(prompt, model_name):
        yield chunk
