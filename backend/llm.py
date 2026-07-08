# LLM系统API客户端（支持h3i平台）
import requests
import json
import re
from typing import AsyncGenerator, Generator, List, Dict, Optional
import logging
import os
from dotenv import load_dotenv
import asyncio

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

load_dotenv()

LLM_API_URL = os.getenv("LLM_API_URL", "http://model.ic.h3i.buaa.edu.cn/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "Qwen2.5-72B-Instruct")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LLMAPIClient:
    """LLM模型API客户端（使用h3i平台）"""
    
    def __init__(self):
        if OpenAI is None:
            raise ImportError("openai库未安装，请运行: pip install openai")
        
        self.api_url = LLM_API_URL
        self.api_key = LLM_API_KEY
        self.model_name = LLM_MODEL_NAME
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.api_url,
            timeout=30.0,
            max_retries=0,
        )
        logger.info(f"LLM客户端初始化完成，API地址: {self.api_url}")
    
    def _prepare_messages(self, question: str, system_prompt: Optional[str] = None) -> List[Dict]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": question})
        return messages
    
    def stream_chat(self, question: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        try:
            messages = self._prepare_messages(question, system_prompt)
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
                stream=True
            )
            
            for chunk in response:
                if chunk.choices and len(chunk.choices) > 0:
                    content = chunk.choices[0].delta.content
                    if content:
                        yield content
        except Exception as e:
            logger.error(f"LLM流式对话失败: {e}")
            yield f"生成失败：{str(e)}"
    
    def stream_chat_with_messages(self, messages: List[Dict]) -> Generator[str, None, None]:
        """使用完整的 messages 列表进行流式对话"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.7,
                max_tokens=4000,
                stream=True
            )
            
            for chunk in response:
                if chunk.choices and len(chunk.choices) > 0:
                    content = chunk.choices[0].delta.content
                    if content:
                        yield content
        except Exception as e:
            logger.error(f"LLM流式对话失败: {e}")
            yield f"生成失败：{str(e)}"
    
    async def async_chat(self, question: str, system_prompt: Optional[str] = None) -> str:
        try:
            messages = self._prepare_messages(question, system_prompt)
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
                stream=False
            )
            
            if response.choices and len(response.choices) > 0:
                return response.choices[0].message.content
            return ""
        except Exception as e:
            logger.error(f"LLM异步对话失败: {e}")
            return f"生成失败：{str(e)}"


def get_llm_client(model_type: str = None):
    """获取LLM客户端实例"""
    return LLMAPIClient()