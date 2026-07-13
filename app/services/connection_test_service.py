"""
连接测试服务 - LLM Provider 连通性测试

根据不同的 api_type 发送简单的测试请求，验证配置是否正确。
"""
import time
from typing import Dict, Any, Tuple
from dataclasses import dataclass

import httpx

from app.config import get_settings
from app.models.tool import ApiType
from app.logger_mgr import get_logger

logger = get_logger("app.services.connection_test_service")

# 测试请求超时配置
TEST_CONNECT_TIMEOUT = 5.0   # 连接超时（秒）
TEST_READ_TIMEOUT = 30.0     # 读取超时（秒）


@dataclass
class ConnectionTestResult:
    """连接测试结果"""
    success: bool
    message: str
    latency_ms: int = 0
    error_code: str = None
    details: str = None


@dataclass
class ModelsProbeResult:
    """模型探测结果"""
    base_url: str
    success: bool
    message: str
    latency_ms: int = 0
    data: dict = None
    error_code: str = None


class ConnectionTestService:
    """连接测试服务类"""

    def __init__(self, http_client: httpx.AsyncClient):
        """
        初始化连接测试服务

        Args:
            http_client: HTTP 异步客户端
        """
        self.http_client = http_client

    async def test_connection(self, api_type: ApiType, base_url: str, model: str, api_key: str) -> ConnectionTestResult:
        """
        测试 LLM Provider 连通性

        Args:
            api_type: API 类型
            base_url: API 基础 URL
            model: 模型名称
            api_key: API 密钥（明文）

        Returns:
            TestResult: 测试结果
        """
        # 根据 api_type 分发到对应的测试方法
        test_methods = {
            "openai_chat": self._test_openai_chat,
            "openai_responses": self._test_openai_responses,
            "anthropic_messages": self._test_anthropic_messages,
            "gemini_generate": self._test_gemini_generate,
            "openai_embeddings": self._test_openai_embeddings,
        }

        test_method = test_methods.get(api_type)
        if not test_method:
            return ConnectionTestResult(success=False, message=f"不支持的 API 类型: {api_type}", error_code="UNSUPPORTED_API_TYPE")

        try:
            result = await test_method(base_url, model, api_key)
            return result
        except Exception as e:
            logger.exception(f"连接测试异常: {e}")
            return ConnectionTestResult(success=False, message=f"测试过程中发生异常: {str(e)}", error_code="INTERNAL_ERROR", details=str(e))

    async def _test_openai_chat(self, base_url: str, model: str, api_key: str) -> ConnectionTestResult:
        """测试 OpenAI Chat Completions API"""
        url = self._build_url(base_url, "/chat/completions")
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"model": model, "messages": [{"role": "user", "content": "请只回复一个数字 1"}]}

        return await self._send_test_request(url, headers, payload)

    async def _test_openai_responses(self, base_url: str, model: str, api_key: str) -> ConnectionTestResult:
        """测试 OpenAI Responses API"""
        url = self._build_url(base_url, "/responses")
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"model": model, "input": "请只回复一个数字 1"}

        return await self._send_test_request(url, headers, payload)

    async def _test_anthropic_messages(self, base_url: str, model: str, api_key: str) -> ConnectionTestResult:
        """测试 Anthropic Messages API"""
        url = self._build_url(base_url, "/messages")

        # 判断是否使用 Bearer 认证（基于配置标记，兼容自建 Bearer 代理）
        settings = get_settings()
        is_bearer_proxy = any(marker in base_url for marker in settings.anthropic_bearer_auth_markers)

        if is_bearer_proxy:
            # Bearer 认证代理
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        else:
            # 官方 Anthropic API：使用 x-api-key 认证
            headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}

        payload = {"model": model, "messages": [{"role": "user", "content": "请只回复一个数字 1"}], "max_tokens": 10}

        return await self._send_test_request(url, headers, payload)

    async def _test_gemini_generate(self, base_url: str, model: str, api_key: str) -> ConnectionTestResult:
        """测试 Google Gemini generateContent API"""
        # Gemini API URL 格式：{base_url}/models/{model}:generateContent?key={api_key}
        # 或者使用 Authorization header
        base_url = base_url.rstrip("/")

        # 检查 base_url 是否已包含 model
        if "/models/" in base_url:
            url = f"{base_url}:generateContent"
        else:
            url = f"{base_url}/models/{model}:generateContent"

        # Gemini 支持两种认证方式，优先使用 header
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"contents": [{"parts": [{"text": "请只回复一个数字 1"}]}]}

        return await self._send_test_request(url, headers, payload)

    async def _test_openai_embeddings(self, base_url: str, model: str, api_key: str) -> ConnectionTestResult:
        """测试 OpenAI Embeddings API"""
        url = self._build_url(base_url, "/embeddings")
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"model": model, "input": "test"}

        return await self._send_test_request(url, headers, payload)

    def _build_url(self, base_url: str, endpoint: str) -> str:
        """
        构建完整的 API URL

        Args:
            base_url: 基础 URL
            endpoint: 端点路径

        Returns:
            完整的 URL
        """
        base_url = base_url.rstrip("/")

        # 如果 base_url 已经包含了端点，直接返回
        if base_url.endswith(endpoint.lstrip("/")):
            return base_url

        # 移除可能存在的其他端点后缀
        common_endpoints = ["/chat/completions", "/messages", "/responses", "/embeddings"]
        for ep in common_endpoints:
            if base_url.endswith(ep):
                base_url = base_url[:-len(ep)]
                break

        return f"{base_url}{endpoint}"

    async def _send_test_request(self, url: str, headers: Dict[str, str], payload: Dict[str, Any]) -> ConnectionTestResult:
        """
        发送测试请求

        Args:
            url: 请求 URL
            headers: 请求头
            payload: 请求体

        Returns:
            TestResult: 测试结果
        """
        timeout = httpx.Timeout(connect=TEST_CONNECT_TIMEOUT, read=TEST_READ_TIMEOUT, write=10.0, pool=5.0)

        start_time = time.time()

        try:
            response = await self.http_client.post(url, headers=headers, json=payload, timeout=timeout)
            latency_ms = int((time.time() - start_time) * 1000)

            if response.status_code < 400:
                return ConnectionTestResult(success=True, message="连接成功", latency_ms=latency_ms)

            # 处理错误响应
            error_text = response.text
            error_info = self._parse_error_response(response.status_code, error_text)

            logger.warning(f"[connection_test] 测试失败\n├── url: {url}\n├── status: {response.status_code}\n└── response: {error_text[:500]}")

            return ConnectionTestResult(success=False, message=error_info["message"], latency_ms=latency_ms, error_code=error_info["code"], details=error_text[:1000])

        except httpx.ConnectTimeout:
            latency_ms = int((time.time() - start_time) * 1000)
            return ConnectionTestResult(success=False, message="连接超时：无法连接到服务器", latency_ms=latency_ms, error_code="CONNECT_TIMEOUT")

        except httpx.ReadTimeout:
            latency_ms = int((time.time() - start_time) * 1000)
            return ConnectionTestResult(success=False, message="读取超时：服务器响应过慢", latency_ms=latency_ms, error_code="READ_TIMEOUT")

        except httpx.ConnectError as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return ConnectionTestResult(success=False, message=f"连接失败：{str(e)}", latency_ms=latency_ms, error_code="CONNECT_ERROR", details=str(e))

        except httpx.HTTPError as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return ConnectionTestResult(success=False, message=f"HTTP 错误：{str(e)}", latency_ms=latency_ms, error_code="HTTP_ERROR", details=str(e))

    def _parse_error_response(self, status_code: int, error_text: str) -> Dict[str, str]:
        """
        解析错误响应，返回友好的错误信息

        Args:
            status_code: HTTP 状态码
            error_text: 错误响应文本

        Returns:
            包含 message 和 code 的字典
        """
        error_map = {
            400: {"message": "请求格式错误：请检查 model 名称是否正确", "code": "BAD_REQUEST"},
            401: {"message": "认证失败：API Key 无效", "code": "AUTH_ERROR"},
            403: {"message": "权限不足：API Key 没有访问该资源的权限", "code": "FORBIDDEN"},
            404: {"message": "端点不存在：请检查 base_url 是否正确", "code": "NOT_FOUND"},
            429: {"message": "请求频率限制：请稍后再试", "code": "RATE_LIMIT"},
        }

        if status_code in error_map:
            return error_map[status_code]

        if 500 <= status_code < 600:
            return {"message": f"Provider 服务端错误 ({status_code})", "code": "SERVER_ERROR"}

        return {"message": f"请求失败 (HTTP {status_code})", "code": "UNKNOWN_ERROR"}

    async def probe_models(self, base_url: str, api_key: str) -> ModelsProbeResult:
        """
        探测 Provider 支持的模型列表

        调用 GET /models 端点获取模型列表

        Args:
            base_url: API 基础 URL
            api_key: API 密钥（明文）

        Returns:
            ModelsProbeResult: 探测结果
        """
        url = self._build_url(base_url, "/models")
        headers = {"Authorization": f"Bearer {api_key}"}
        timeout = httpx.Timeout(connect=TEST_CONNECT_TIMEOUT, read=TEST_READ_TIMEOUT, write=10.0, pool=5.0)

        start_time = time.time()

        try:
            response = await self.http_client.get(url, headers=headers, timeout=timeout)
            latency_ms = int((time.time() - start_time) * 1000)

            if response.status_code < 400:
                # 尝试解析 JSON，失败时返回原始文本
                try:
                    data = response.json()
                except Exception:
                    data = {"raw_response": response.text[:500]}
                result = ModelsProbeResult(base_url=base_url, success=True, message="探测成功", latency_ms=latency_ms, data=data)
                return result

            # 处理错误响应
            error_text = response.text
            error_info = self._parse_error_response(response.status_code, error_text)

            logger.warning(f"[probe_models] 探测失败\n├── url: {url}\n├── status: {response.status_code}\n└── response: {error_text[:500]}")

            result = ModelsProbeResult(base_url=base_url, success=False, message=error_info["message"], latency_ms=latency_ms, error_code=error_info["code"])
            return result

        except httpx.ConnectTimeout:
            latency_ms = int((time.time() - start_time) * 1000)
            result = ModelsProbeResult(base_url=base_url, success=False, message="连接超时：无法连接到服务器", latency_ms=latency_ms, error_code="CONNECT_TIMEOUT")
            return result

        except httpx.ReadTimeout:
            latency_ms = int((time.time() - start_time) * 1000)
            result = ModelsProbeResult(base_url=base_url, success=False, message="读取超时：服务器响应过慢", latency_ms=latency_ms, error_code="READ_TIMEOUT")
            return result

        except httpx.ConnectError as e:
            latency_ms = int((time.time() - start_time) * 1000)
            result = ModelsProbeResult(base_url=base_url, success=False, message=f"连接失败：{str(e)}", latency_ms=latency_ms, error_code="CONNECT_ERROR")
            return result

        except httpx.HTTPError as e:
            latency_ms = int((time.time() - start_time) * 1000)
            result = ModelsProbeResult(base_url=base_url, success=False, message=f"HTTP 错误：{str(e)}", latency_ms=latency_ms, error_code="HTTP_ERROR")
            return result

        except Exception as e:
            # 兜底捕获所有其他异常，确保不会中断调用方的批量处理
            latency_ms = int((time.time() - start_time) * 1000)
            logger.exception(f"[probe_models] 探测异常: {e}")
            result = ModelsProbeResult(base_url=base_url, success=False, message=f"探测异常：{str(e)}", latency_ms=latency_ms, error_code="INTERNAL_ERROR")
            return result
