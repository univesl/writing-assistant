# LLM系统API客户端
from openai import OpenAI, AsyncOpenAI
from typing import AsyncGenerator, Generator, List, Dict, Optional
import logging
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# LLM系统API配置（用于问题定位）
LLM_API_KEY = os.getenv("LLM_API_KEY", "f93082e1-2cbf-4f81-af8f-9c98d528b6b1")
LLM_API_URL = os.getenv("LLM_API_URL", "https://xhang.buaa.edu.cn/xhang/v1")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "xhang")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LLMAPIClient:
    def __init__(self):
        """初始化LLM API客户端"""
        self.client = OpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_API_URL
        )
        self.async_client = AsyncOpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_API_URL
        )
        self.model_name = LLM_MODEL_NAME
    
    def chat_completion(self, messages: List[Dict], stream: bool = True, temperature: float = 0.7, max_tokens: int = 300) -> any:
        """调用LLM API进行对话
        
        Args:
            messages: 对话消息列表，格式：[{"role": "user", "content": "问题内容"}]
            stream: 是否使用流式响应（默认为True）
            temperature: 温度参数
            max_tokens: 最大token数
            
        Returns:
            流式响应生成器或完整响应对象
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                stream=stream,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response
        except Exception as e:
            logger.error(f"LLM API调用失败: {e}")
            raise
    
    def stream_chat(self, question: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        """流式对话接口
        
        Args:
            question: 用户问题
            system_prompt: 系统提示词
            
        Yields:
            AI回答的文本片段
        """
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": question})
            
            response = self.chat_completion(messages, stream=True)
            
            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"流式对话失败: {e}")
            yield f"对话失败: {str(e)}"
    
    async def async_chat_completion(self, messages: List[Dict], temperature: float = 0.7, max_tokens: int = 1000) -> str:
        """异步调用LLM API进行对话
        
        Args:
            messages: 对话消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            
        Returns:
            完整的响应文本
        """
        try:
            response = await self.async_client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                stream=False,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"异步LLM API调用失败: {e}")
            return f"调用失败: {str(e)}"
    
    async def async_chat(self, question: str, system_prompt: Optional[str] = None) -> str:
        """异步对话接口
        
        Args:
            question: 用户问题
            system_prompt: 系统提示词
            
        Returns:
            AI回答的完整文本
        """
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": question})
            
            response = await self.async_chat_completion(messages)
            return response
        except Exception as e:
            logger.error(f"异步对话失败: {e}")
            return f"对话失败: {str(e)}"