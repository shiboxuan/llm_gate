"""运行时配置注入测试

验证后端 serve index.html 时，将 LLM_GATE_PUBLIC_API_BASE_URL 注入到前端
新手引导弹窗展示用的运行时配置占位符的逻辑（见 app/main.py 的 _render_index_html）。
"""
import json

from app.main import _render_index_html


def test_render_index_html_replaces_placeholder_with_json():
    """占位符被替换为包含 apiBaseUrl 的 JSON"""
    rendered = _render_index_html("__LLM_GATE_RUNTIME_CONFIG__", "http://example.com:9981/v1")

    assert "__LLM_GATE_RUNTIME_CONFIG__" not in rendered
    assert json.loads(rendered) == {"apiBaseUrl": "http://example.com:9981/v1"}


def test_render_index_html_keeps_surrounding_markup():
    """模板其余部分保持不变"""
    template = (
        "<!DOCTYPE html><html><head></head><body>"
        '<script id="llm-gate-runtime-config" type="application/json">__LLM_GATE_RUNTIME_CONFIG__</script>'
        '<div id="root"></div>'
        "</body></html>"
    )
    rendered = _render_index_html(template, "http://example.com:9981/v1")

    assert rendered.startswith("<!DOCTYPE html><html><head></head><body>")
    assert '<div id="root"></div>' in rendered
    assert rendered.endswith("</body></html>")
    assert "__LLM_GATE_RUNTIME_CONFIG__" not in rendered


def test_render_index_html_escapes_less_than_sign():
    """值中的 < 被转义为 \\u003c，防止 </script> 破坏 script 标签"""
    malicious = "http://evil.com/v1</script><script>alert(1)</script>"
    rendered = _render_index_html("__LLM_GATE_RUNTIME_CONFIG__", malicious)

    # 渲染结果中不含裸 </script>（恶意值中的 < 已被转义）
    assert "</script>" not in rendered
    # JSON 解析后应还原为原值（\\u003c 还原为 <）
    assert json.loads(rendered) == {"apiBaseUrl": malicious}


def test_render_index_html_without_placeholder_returns_template_unchanged():
    """模板无占位符时原样返回"""
    template = "<html><body>no placeholder here</body></html>"
    rendered = _render_index_html(template, "http://example.com:9981/v1")

    assert rendered == template


def test_render_index_html_empty_value_means_auto():
    """空值（后端默认，表示前端自动推导 window.location.origin）正常注入为空字符串"""
    rendered = _render_index_html("__LLM_GATE_RUNTIME_CONFIG__", "")
    assert json.loads(rendered) == {"apiBaseUrl": ""}


def test_render_index_html_explicit_slash_v1():
    """显式 /v1 正常注入"""
    rendered = _render_index_html("__LLM_GATE_RUNTIME_CONFIG__", "/v1")
    assert json.loads(rendered) == {"apiBaseUrl": "/v1"}
