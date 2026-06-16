"""
KnG RAG 检索服务
通过 HTTP API 调用 KnG 服务进行检索
"""

import os
import json
import requests
import time
from typing import List, Dict, Any, Optional
from pathlib import Path

# KnG 服务配置
KNG_BASE_URL = os.getenv("KNG_BASE_URL", "http://127.0.0.1:50001")


class KnGRAGService:
    """KnG RAG 检索服务 - HTTP API 版"""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or KNG_BASE_URL
        print(f"[KnG RAG] Service URL: {self.base_url}")
    
    def is_ready(self) -> bool:
        """检查服务是否就绪"""
        try:
            response = requests.get(f"{self.base_url}/api/status", timeout=5)
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
            response = requests.post(url, json=payload, timeout=60)
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
        
        # 构建查询语句
        query = f"请根据以下主题提供相关的北航真实公文参考内容：\n\n主题：{topic}"
        if requirements:
            query += f"\n要求：{requirements}"
        query += "\n\n请提供相关的完整公文原文作为参考，包括标题格式、正文结构、落款方式等。"
        
        system_prompt = """你是北航公文知识库助手。请基于知识库检索结果，提供真实公文原文作为参考：
1. 返回与主题最相关的公文原文内容（尽量完整）
2. 标注公文的文体类型（通知/规章制度/讲话稿/报告/函等）
3. 提取关键的格式特征和用语习惯

尽量提供完整的公文原文，可以适当举例说明格式要点。"""
        
        try:
            content = self.query(
                query=query,
                mode=mode,
                system_prompt=system_prompt,
                knowledge_source="kg",
                stream=False,
            )
            
            total_time = time.time() - total_start
            print(f"[KnG RAG] ===== 检索完成，总耗时: {total_time:.2f}s =====\n")
            
            return {
                "content": content,
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
