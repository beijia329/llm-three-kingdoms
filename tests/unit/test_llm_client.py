"""LLM客户端单元测试

测试API调用、重试、超时等功能。
使用 pytest-httpx 或 mock 模拟网络请求。
"""

import pytest
from unittest.mock import Mock, patch
from httpx import RequestError

from players.llm.llm_client import LLMClient


class TestLLMClientInit:
    """客户端初始化测试"""

    def test_init_deepseek(self):
        """初始化DeepSeek客户端"""
        client = LLMClient(
            provider="deepseek",
            model="deepseek-v4-flash",
            api_key="sk-test-key",
        )
        assert client.model == "deepseek-v4-flash"
        assert "api.deepseek.com" in client.base_url

    def test_init_openai(self):
        """初始化OpenAI客户端"""
        client = LLMClient(
            provider="openai",
            model="gpt-4",
            api_key="sk-test-key",
        )
        assert "api.openai.com" in client.base_url

    def test_init_openrouter(self):
        """初始化OpenRouter客户端"""
        client = LLMClient(
            provider="openrouter",
            model="claude-3-opus",
            api_key="sk-test-key",
        )
        assert "openrouter.ai" in client.base_url


class TestLLMChat:
    """对话功能测试（mock模式）"""

    def test_chat_returns_text(self, mocker):
        """对话返回文本"""
        mock_post = mocker.patch("httpx.Client.post")
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"test": "hello"}'}}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 10},
        }
        mock_post.return_value = mock_response

        client = LLMClient(provider="deepseek", model="test-model", api_key="sk-test")
        result = client.chat([{"role": "user", "content": "hi"}])

        assert result == '{"test": "hello"}'

    def test_chat_passes_messages(self, mocker):
        """正确传递消息"""
        mock_post = mocker.patch("httpx.Client.post")
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
        }
        mock_post.return_value = mock_response

        client = LLMClient(provider="deepseek", model="test-model", api_key="sk-test")
        messages = [
            {"role": "system", "content": "你是一个助手"},
            {"role": "user", "content": "你好"},
        ]
        client.chat(messages)

        # 验证传参
        call_kwargs = mock_post.call_args[1]
        sent_messages = call_kwargs["json"]["messages"]
        assert len(sent_messages) == 2
        assert sent_messages[0]["role"] == "system"

    def test_chat_with_temperature(self, mocker):
        """传递temperature参数"""
        mock_post = mocker.patch("httpx.Client.post")
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
        }
        mock_post.return_value = mock_response

        client = LLMClient(provider="deepseek", model="test-model", api_key="sk-test")
        client.chat([{"role": "user", "content": "hi"}], temperature=0.5)

        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["temperature"] == 0.5

    def test_chat_tracks_usage(self, mocker):
        """记录token用量"""
        mock_post = mocker.patch("httpx.Client.post")
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }
        mock_post.return_value = mock_response

        client = LLMClient(provider="deepseek", model="test-model", api_key="sk-test")
        client.chat([{"role": "user", "content": "hi"}])

        assert client.total_prompt_tokens == 100
        assert client.total_completion_tokens == 50


class TestLLMRetry:
    """重试机制测试"""

    def test_retry_on_timeout(self, mocker):
        """超时后重试"""
        mock_post = mocker.patch("httpx.Client.post")
        # 第一次超时，第二次成功
        mock_post.side_effect = [
            RequestError("timeout"),
            Mock(status_code=200, json=lambda: {
                "choices": [{"message": {"content": "ok"}}],
            }),
        ]

        client = LLMClient(
            provider="deepseek", model="test-model",
            api_key="sk-test", max_retries=2,
        )
        result = client.chat([{"role": "user", "content": "hi"}])
        assert result == "ok"
        assert mock_post.call_count == 2

    def test_retry_exhausted_raises(self, mocker):
        """重试耗尽后报错"""
        mock_post = mocker.patch("httpx.Client.post")
        mock_post.side_effect = RequestError("always fails")

        client = LLMClient(
            provider="deepseek", model="test-model",
            api_key="sk-test", max_retries=1,
        )
        with pytest.raises(RequestError):
            client.chat([{"role": "user", "content": "hi"}])

    def test_no_retry_on_success(self, mocker):
        """成功时不重试"""
        mock_post = mocker.patch("httpx.Client.post")
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: {"choices": [{"message": {"content": "ok"}}]},
        )

        client = LLMClient(
            provider="deepseek", model="test-model",
            api_key="sk-test", max_retries=3,
        )
        client.chat([{"role": "user", "content": "hi"}])
        assert mock_post.call_count == 1


class TestLLMEdgeCases:
    """边界情况测试"""

    def test_empty_response(self, mocker):
        """空响应"""
        mock_post = mocker.patch("httpx.Client.post")
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": ""}}],
        }
        mock_post.return_value = mock_response

        client = LLMClient(provider="deepseek", model="test-model", api_key="sk-test")
        result = client.chat([{"role": "user", "content": "hi"}])
        assert result == ""

    def test_http_error(self, mocker):
        """HTTP错误"""
        mock_post = mocker.patch("httpx.Client.post")
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = RequestError("401 Unauthorized")
        mock_post.return_value = mock_response

        client = LLMClient(provider="deepseek", model="test-model", api_key="sk-test")
        with pytest.raises(RequestError):
            client.chat([{"role": "user", "content": "hi"}])

    def test_get_cost_summary(self, mocker):
        """获取成本摘要"""
        client = LLMClient(provider="deepseek", model="test-model", api_key="sk-test")
        summary = client.get_cost_summary()
        assert "total_calls" in summary
        assert summary["total_calls"] == 0
