"""LLM API客户端

统一的LLM API调用接口，支持多种提供商。
当前支持：DeepSeek、OpenAI、OpenRouter（兼容OpenAI格式）。

功能：
- 流式/非流式调用
- 超时保护
- 自动重试（指数退避）
- Token用量统计
- 成本追踪

参考设计文档：docs/design/llm-integration.md 第五章
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# OpenAI 兼容API的基础URL映射
PROVIDER_BASE_URLS: Dict[str, str] = {
    "deepseek": "https://api.deepseek.com/v1",
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}

DEFAULT_TIMEOUT: int = 60
"""默认超时秒数"""

DEFAULT_MAX_RETRIES: int = 2
"""默认最大重试次数"""

RETRY_BACKOFF: float = 2.0
"""重试指数退避基数（秒）"""


class LLMClient:
    """LLM API客户端

    支持任意兼容 OpenAI Chat Completions 格式的 API。
    """

    def __init__(
        self,
        provider: str = "deepseek",
        model: str = "deepseek-v4-flash",
        api_key: str = "",
        base_url: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        """初始化LLM客户端

        Args:
            provider: API提供商 (deepseek/openai/openrouter)
            model: 模型名称
            api_key: API密钥
            base_url: API基础URL，不传则使用默认URL
            timeout: 超时秒数
            max_retries: 最大重试次数
        """
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries

        # API 基础URL
        self.base_url = (base_url or
                         PROVIDER_BASE_URLS.get(provider, PROVIDER_BASE_URLS["deepseek"]))

        # HTTP 客户端
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

        # 用量统计
        self.total_calls: int = 0
        self.successful_calls: int = 0
        self.failed_calls: int = 0
        self.total_prompt_tokens: int = 0
        self.total_completion_tokens: int = 0
        self.total_cost: float = 0.0
        self._last_response_time: float = 0.0

    # ============================================================
    # 核心调用方法
    # ============================================================

    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """发送聊天请求

        Args:
            messages: 消息列表，格式为 [{"role": "system"/"user"/"assistant", "content": "..."}]
            max_tokens: 最大生成token数
            temperature: 温度参数 (0.0-2.0)

        Returns:
            模型回复的文本内容

        Raises:
            httpx.RequestError: 所有重试耗尽后抛出
        """
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                result = self._call_api(messages, max_tokens, temperature)
                self.successful_calls += 1
                return result
            except httpx.RequestError as e:
                last_error = e
                self.failed_calls += 1

                if attempt < self.max_retries:
                    wait_time = RETRY_BACKOFF ** attempt
                    logger.warning(
                        "API调用失败 (尝试 %d/%d): %s. %ds后重试...",
                        attempt + 1, self.max_retries + 1, e, wait_time,
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(
                        "API调用全部失败 (%d 次): %s",
                        self.max_retries + 1, e,
                    )

        raise last_error  # type: ignore

    def _call_api(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> str:
        """实际调用API（单次）

        Args:
            messages: 消息列表
            max_tokens: 最大生成token数
            temperature: 温度参数

        Returns:
            模型回复文本
        """
        self.total_calls += 1
        start_time = time.time()

        response = self._client.post(
            "/chat/completions",
            json={
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        )
        response.raise_for_status()

        data = response.json()
        self._last_response_time = time.time() - start_time

        # 记录用量
        usage = data.get("usage", {})
        self.total_prompt_tokens += usage.get("prompt_tokens", 0)
        self.total_completion_tokens += usage.get("completion_tokens", 0)

        # 提取回复内容
        choices = data.get("choices", [])
        if not choices:
            return ""

        message = choices[0].get("message", {})
        content = message.get("content", "")

        return content

    # ============================================================
    # 工具方法
    # ============================================================

    def get_cost_summary(self) -> Dict[str, Any]:
        """获取调用统计摘要

        Returns:
            包含调用次数、token用量等的字典
        """
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
            "last_response_time": f"{self._last_response_time:.2f}s",
        }

    def close(self) -> None:
        """关闭HTTP客户端"""
        self._client.close()
