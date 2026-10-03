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
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

# ============================================================
# .env 加载（v4.0.1）
# ============================================================
# 🔴 修复「僵尸配置」：此前全仓 grep `dotenv` **零命中** ——
#    `.env` 文件里写着"配置方式（任选其一）"的说明，教使用者怎么填 key，
#    但**没有任何代码读取它**，填了也完全不生效。
#    与 B-1（prompt 硬读常量）/ B-2（启动参数无人读）属同一类缺陷。
#
# 放在本模块顶部：任何 LLM 调用路径都必须先 import 本模块，
# 因此在 api/game_manager.py 读 os.environ 之前，环境变量已就位。
# override=False → 已存在的环境变量优先，便于临时 `export LLM_API_KEY=xxx` 覆盖。
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
except ImportError:  # pragma: no cover - dotenv 缺失时静默降级为纯环境变量模式
    pass

logger = logging.getLogger(__name__)

# OpenAI 兼容API的基础URL映射
PROVIDER_BASE_URLS: Dict[str, str] = {
    "deepseek": "https://api.deepseek.com/v1",
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}

PROVIDER_MODELS: Dict[str, List[str]] = {
    # 2026-10-03 实测：调 GET {base_url}/models 得到，ctx 均为 1048576
    "deepseek": ["deepseek-flash", "deepseek-v4-pro"],
    # 以下是 OpenAI 常见 id，仅作候选展示；是否可用取决于账号权限
    "openai": ["gpt-4o", "gpt-4o-mini"],
    # OpenRouter 模型数量庞大且随时变化，不在此硬编码（留空 → 前端显示为自由输入）
    "openrouter": [],
}
"""各 provider 的候选模型清单（用于前端「模型分配」下拉）

⚠️ 只是**候选展示**，不做强校验：用户仍可填任意模型字符串，
真实可用性由 API 侧决定（填错会在第一次调用时报错）。
之所以不实时调 API 查询：避免前端每次打开设置都打一次外网请求。
"""

DEFAULT_TIMEOUT: int = 180
"""默认超时秒数（v4.0.1 由 60 提升）

🔴 为什么要提：实测 `deepseek-v4-pro` 单次游戏决策耗时约 **70 秒**
（推理 token 可达 8000+，是 deepseek-flash 的 2~3 倍）。
原 60 秒超时会让它的**每一次调用都必然超时**，触发重试后总耗时爆炸
（实测一回合 273 秒，其中大半是超时重试）。
180 秒可覆盖 v4-pro 在截断翻倍预算后的极端情况。
"""

DEFAULT_MAX_RETRIES: int = 2
"""默认最大重试次数"""

MAX_TOKEN_BUDGET: int = 32768
"""单次生成的 token 预算硬上限（v4.0.1）

用于「截断后自动翻倍重试」的天花板。深度求索模型声明 max_output_tokens=393216，
但把预算无节制翻倍会显著推高成本与延迟，因此设一个远高于实际需要的上限。
"""


class ResponseTruncatedError(Exception):
    """响应被 max_tokens 截断且正文为空

    推理模型（deepseek-flash / deepseek-v4-pro）的隐藏思维链计入 max_tokens，
    预算不足时会「把额度全花在思考上、正文一个字不输出」。
    单独定义异常类型，是为了让 chat() 能把这种**可修复的失败**
    （提高预算即可）与网络错误区分开，做针对性重试。
    """

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
            except ResponseTruncatedError as e:
                # 预算不足是「可修复的失败」：推理模型输出长度波动很大
                # （实测 deepseek-flash 的 reasoning token 在 1382~3014 间浮动，
                #   deepseek-v4-pro 可达 8192），翻倍预算后重试通常即可成功。
                last_error = e
                self.failed_calls += 1
                if attempt < self.max_retries:
                    new_budget = min(max_tokens * 2, MAX_TOKEN_BUDGET)
                    if new_budget > max_tokens:
                        logger.warning(
                            "响应被截断（推理吃光 %d token 预算），提升至 %d 后重试",
                            max_tokens, new_budget,
                        )
                        max_tokens = new_budget
                        continue
                logger.error("响应持续被截断，预算已到上限 %d: %s", max_tokens, e)
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
        # 估算费用 (DeepSeek: $0.14/1M input, $0.28/1M output)
        pt = usage.get("prompt_tokens", 0)
        ct = usage.get("completion_tokens", 0)
        self.total_cost += pt * 0.14 / 1_000_000 + ct * 0.28 / 1_000_000

        # 提取回复内容
        choices = data.get("choices", [])
        if not choices:
            return ""

        choice = choices[0]
        message = choice.get("message", {})
        content = message.get("content", "")
        finish_reason = choice.get("finish_reason", "")

        # ============================================================
        # 截断检测（v4.0.1）
        # ============================================================
        # 🔴 原实现直接 `return content`，**完全不看 finish_reason**。
        #    而 DeepSeek 系（deepseek-flash / deepseek-v4-pro）**都是推理模型**，
        #    隐藏思维链 reasoning_content 的 token **计入 max_tokens**。
        #    实测（真实游戏 prompt，5308 字符，max_tokens=4096）：
        #        finish_reason=length
        #        completion_tokens=4095 / reasoning_tokens=4095
        #        content 长度=0，reasoning_content 长度=6219
        #    → 预算被 CoT 吃光，正文一个字都没输出。
        #    由于这里返回空串，上层只看到"LLM输出为空"，无法区分
        #    "模型不想说话"与"预算被吃光"，排查成本极高。
        # 现在把「截断且正文为空」变成显式异常，交给 chat() 的预算翻倍重试处理。
        if finish_reason == "length" and not (content or "").strip():
            detail = usage.get("completion_tokens_details", {}) or {}
            raise ResponseTruncatedError(
                f"响应被 max_tokens({max_tokens}) 截断且正文为空："
                f"completion={usage.get('completion_tokens')} "
                f"reasoning={detail.get('reasoning_tokens')} "
                f"reasoning_content={len(message.get('reasoning_content') or '')}字符。"
                "推理模型的思维链计入 max_tokens，需提高预算"
                "（见 llm_player.LLM_MAX_TOKENS）。"
            )

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
            "total_cost": round(self.total_cost, 6),
            "last_response_time": f"{self._last_response_time:.2f}s",
        }

    def close(self) -> None:
        """关闭HTTP客户端"""
        self._client.close()
