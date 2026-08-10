"""
连接测试服务单元测试

覆盖 anthropic_messages 类型的连通性测试逻辑：
- 按用户 base_url 原样构建请求（不静默补 /v1）
- 失败时额外尝试 /v1 路径（仅诊断提示），成功后提示用户修改 base_url
- 全部失败时列出尝试过的所有 URL
"""
import asyncio

import pytest

from app.services.connection_test_service import ConnectionTestService, ConnectionTestResult


def _service() -> ConnectionTestService:
    # 测试方法通过替换 _send_test_request 模拟，http_client 不会被使用
    return ConnectionTestService(http_client=None)


@pytest.mark.parametrize(
    "base_url, expected",
    [
        # 按用户填写原样构建，不补 /v1
        ("https://api.anthropic.com", "https://api.anthropic.com/messages"),
        ("https://ark.cn-beijing.volces.com/api/plan", "https://ark.cn-beijing.volces.com/api/plan/messages"),
        # 已带 /v1：直接拼 /messages
        ("https://api.anthropic.com/v1", "https://api.anthropic.com/v1/messages"),
        # 已带完整 /messages 端点：原样返回
        ("https://api.anthropic.com/v1/messages", "https://api.anthropic.com/v1/messages"),
        # 尾部斜杠不影响
        ("https://ark.cn-beijing.volces.com/api/plan/", "https://ark.cn-beijing.volces.com/api/plan/messages"),
    ],
)
def test_build_url_anthropic_primary(base_url: str, expected: str):
    assert _service()._build_url(base_url, "/messages") == expected


def _make_fake_send(fail_urls: set, success_message: str = "连接成功"):
    """构造模拟 _send_test_request：fail_urls 中的 URL 返回失败，其余成功"""
    async def fake_send(url: str, headers: dict, payload: dict) -> ConnectionTestResult:
        if url in fail_urls:
            return ConnectionTestResult(success=False, message="认证失败：API Key 无效", error_code="AUTH_ERROR", latency_ms=100)
        return ConnectionTestResult(success=True, message=success_message, latency_ms=50)
    return fake_send


async def _run_test(svc, base_url: str) -> ConnectionTestResult:
    return await svc._test_anthropic_messages(base_url, "glm-5.2", "sk-test")


def test_primary_success_no_fallback():
    """primary URL 直接成功：不再尝试 fallback"""
    svc = _service()
    svc._send_test_request = _make_fake_send(fail_urls=set())
    result = asyncio.run(_run_test(svc, "https://ark.cn-beijing.volces.com/api/plan/v1"))
    assert result.success is True
    assert result.attempted_urls is None


def test_primary_fail_fallback_success_returns_hint():
    """primary 失败、加 /v1 后成功：返回失败 + 提示修改 base_url"""
    svc = _service()
    svc._send_test_request = _make_fake_send(fail_urls={"https://ark.cn-beijing.volces.com/api/plan/messages"})
    result = asyncio.run(_run_test(svc, "https://ark.cn-beijing.volces.com/api/plan"))
    assert result.success is False
    assert result.error_code == "NEED_V1_SUFFIX"
    assert "请将 base_url 修改为：https://ark.cn-beijing.volces.com/api/plan/v1" in result.message
    assert result.attempted_urls == [
        "https://ark.cn-beijing.volces.com/api/plan/messages",
        "https://ark.cn-beijing.volces.com/api/plan/v1/messages",
    ]


def test_both_fail_lists_attempted_urls():
    """两个 URL 都失败：列出尝试过的所有 URL"""
    svc = _service()
    svc._send_test_request = _make_fake_send(fail_urls={
        "https://ark.cn-beijing.volces.com/api/plan/messages",
        "https://ark.cn-beijing.volces.com/api/plan/v1/messages",
    })
    result = asyncio.run(_run_test(svc, "https://ark.cn-beijing.volces.com/api/plan"))
    assert result.success is False
    assert "所有尝试均失败" in result.message
    assert "https://ark.cn-beijing.volces.com/api/plan/messages" in result.message
    assert "https://ark.cn-beijing.volces.com/api/plan/v1/messages" in result.message
    assert result.attempted_urls == [
        "https://ark.cn-beijing.volces.com/api/plan/messages",
        "https://ark.cn-beijing.volces.com/api/plan/v1/messages",
    ]


def test_v1_already_present_no_fallback():
    """base_url 已带 /v1：失败时不再尝试第二个 URL"""
    svc = _service()
    svc._send_test_request = _make_fake_send(fail_urls={"https://ark.cn-beijing.volces.com/api/plan/v1/messages"})
    result = asyncio.run(_run_test(svc, "https://ark.cn-beijing.volces.com/api/plan/v1"))
    assert result.success is False
    assert result.attempted_urls is None
