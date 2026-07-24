"""
KnG RAG 检索服务
通过 HTTP API 调用 KnG 服务进行检索
"""

import os
import re
import requests
import time
from typing import List, Dict, Any, Optional

# KnG 服务配置
KNG_BASE_URL = os.getenv("KNG_BASE_URL", "http://127.0.0.1:50001")
KNG_STATUS_TIMEOUT = float(os.getenv("KNG_STATUS_TIMEOUT", "5"))
KNG_QUERY_TIMEOUT = float(os.getenv("KNG_QUERY_TIMEOUT", "120"))

_REFERENCE_HEADING_RE = re.compile(
    r"(?im)^[ \t]*(?:#{1,6}[ \t]*)?(?:references|参考(?:文献|来源))[ \t]*:?[ \t]*$"
)
_REFERENCE_ITEM_RE = re.compile(r"^[ \t]*[-*][ \t]*\[(\d+)\][ \t]*(.+?)[ \t]*$")
_REFERENCE_BULLET_RE = re.compile(r"^[ \t]*[-*][ \t]+(.+?)[ \t]*$")
_SOURCE_SECTION_RE = re.compile(
    r"(?im)^[ \t]*#{1,6}[ \t]*(?:相关)?文件(?:名称)?(?:和|及)?来源[ \t]*:?[ \t]*$"
)
_NEXT_HEADING_RE = re.compile(r"(?m)^[ \t]*#{1,6}[ \t]+.+$")


def _parse_reference_block(reference_block: str) -> List[str]:
    references = []
    seen = set()
    for line in reference_block.splitlines():
        match = _REFERENCE_ITEM_RE.match(line)
        if match:
            reference = f"[{match.group(1)}] {match.group(2).strip()}"
        else:
            bullet = _REFERENCE_BULLET_RE.match(line)
            if not bullet:
                continue
            reference = bullet.group(1).strip().replace("**", "")

        if reference and reference not in seen:
            references.append(reference)
            seen.add(reference)
    return references


def split_rag_response(raw_content: str) -> tuple[str, List[str]]:
    """Split KnG's native answer from its References section."""
    content = (raw_content or "").strip()
    heading = _REFERENCE_HEADING_RE.search(content)
    if heading:
        answer = content[:heading.start()].rstrip()
        return answer, _parse_reference_block(content[heading.end():])

    source_heading = _SOURCE_SECTION_RE.search(content)
    if not source_heading:
        return content, []

    source_block = content[source_heading.end():]
    next_heading = _NEXT_HEADING_RE.search(source_block)
    if next_heading:
        source_block = source_block[:next_heading.start()]
    return content, _parse_reference_block(source_block)


class KnGRAGService:
    """KnG RAG 检索服务 - HTTP API 版"""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or KNG_BASE_URL
        print(f"[KnG RAG] Service URL: {self.base_url}")
    
    def is_ready(self) -> bool:
        """检查服务是否就绪"""
        try:
            response = requests.get(f"{self.base_url}/api/status", timeout=KNG_STATUS_TIMEOUT)
            return response.status_code == 200
        except Exception as e:
            print(f"[KnG RAG] Service not ready: {e}")
            return False
    
    def query(
        self,
        query: str,
        mode: str = "local",
        system_prompt: str = None,
        conversation_history: List[Dict] = None,
        knowledge_source: str = "kg",
        stream: bool = False,
    ) -> str:
        """
        调用 KnG RAG 查询
        
        Args:
            query: 查询文本
            mode: 检索模式 (local, global, hybrid, mix, naive)
            system_prompt: 系统提示词
            conversation_history: 对话历史
            knowledge_source: 知识源 (kg, web, both)
            stream: 是否流式返回
            
        Returns:
            生成的回答文本
        """
        start_time = time.time()
        print(f"[KnG RAG] 开始查询，模式: {mode}, 知识源: {knowledge_source}")
        
        url = f"{self.base_url}/api/v1/chats_openai/default/chat/completions"
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # 添加对话历史
        if conversation_history:
            messages.extend(conversation_history)
        
        # 添加当前查询
        messages.append({"role": "user", "content": query})
        
        payload = {
            "model": "kng",
            "messages": messages,
            "mode": mode,
            "knowledge_source": knowledge_source,
            "stream": stream,
        }
        
        try:
            api_start = time.time()
            response = requests.post(url, json=payload, timeout=KNG_QUERY_TIMEOUT)
            api_time = time.time() - api_start
            print(f"[KnG RAG] API请求耗时: {api_time:.2f}s")
            
            response.raise_for_status()
            
            result = response.json()
            total_time = time.time() - start_time
            print(f"[KnG RAG] 总耗时: {total_time:.2f}s")
            
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0]["message"]["content"]
                print(f"[KnG RAG] 返回内容长度: {len(content)} 字符")
                return content
            else:
                print(f"[KnG RAG] 返回结果为空")
                return ""
                
        except Exception as e:
            total_time = time.time() - start_time
            print(f"[KnG RAG] Query failed after {total_time:.2f}s: {e}")
            raise
    
    def retrieve_for_document_generation(
        self,
        topic: str,
        requirements: str = "",
        mode: str = "local",
    ) -> Dict[str, Any]:
        """
        为文档生成检索参考内容
        
        Args:
            topic: 主题/标题
            requirements: 特殊要求
            mode: 检索模式
            
        Returns:
            {"content": "检索结果文本", "query": "查询语句", "timing": {...}}
        """
        total_start = time.time()
        print(f"\n[KnG RAG] ===== 开始文档生成检索 =====")
        print(f"[KnG RAG] 主题: {topic}")
        print(f"[KnG RAG] 检索模式: {mode}")
        
        query = (
            "请从北航公文知识库中检索与以下写作任务直接相关的资料。\n\n"
            f"写作任务：{topic}"
        )
        if requirements:
            query += f"\n用户要求：{requirements}"
        query += (
            "\n\n请重点返回："
            "\n1. 与任务直接相关的制度依据、事实信息和既有做法；"
            "\n2. 可以用于写作的准确表述和必要原文片段；"
            "\n3. 相关文件名称和来源。"
            "\n只完成资料检索和归纳，不要代写最终公文；"
            "知识库中没有的信息请明确说明，不要编造。"
        )
        
        try:
            raw_content = self.query(
                query=query,
                mode=mode,
                knowledge_source="kg",
                stream=False,
            )
            content, references = split_rag_response(raw_content)
            
            total_time = time.time() - total_start
            print(f"[KnG RAG] ===== 检索完成，总耗时: {total_time:.2f}s =====\n")
            
            return {
                "content": content,
                "references": references,
                "query": query,
                "timing": {
                    "total_seconds": round(total_time, 2)
                }
            }
            
        except Exception as e:
            total_time = time.time() - total_start
            print(f"[KnG RAG] Retrieval failed after {total_time:.2f}s: {e}\n")
            return {
                "content": "",
                "references": [],
                "query": query,
                "error": str(e),
                "timing": {
                    "total_seconds": round(total_time, 2)
                }
            }


# 全局服务实例
_kng_rag_service: Optional[KnGRAGService] = None


def get_kng_rag_service() -> KnGRAGService:
    """获取 KnG RAG 服务实例（单例模式）"""
    global _kng_rag_service
    if _kng_rag_service is None:
        _kng_rag_service = KnGRAGService()
    return _kng_rag_service


def retrieve_from_knowledge_base(
    query: str,
    mode: str = "local",
) -> str:
    """
    便捷函数：从知识库检索内容
    
    Args:
        query: 查询文本
        mode: 检索模式
        
    Returns:
        检索结果文本
    """
    service = get_kng_rag_service()
    return service.query(query, mode=mode)
