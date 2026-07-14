/**
 * 运行时配置：由后端在 serve index.html 时注入（见 app/main.py 的 _render_index_html）。
 *
 * 当前仅用于新手引导弹窗展示「后端 API 地址」，不影响实际 API 请求路由
 * （请求 baseURL 仍由 @/utils/variable 的 llmGateHost 决定，默认同源 `/`）。
 *
 * 取值优先级：
 * 1. 后端注入的非空 LLM_GATE_PUBLIC_API_BASE_URL（展示固定地址，如规范域名）
 * 2. 自动推导 window.location.origin + '/v1'（浏览器实际访问地址，容器化部署零配置即可正确）
 *
 * dev 模式下 index.html 由 webpack-dev-server 直出、不经后端，占位符不会被替换，
 * 此时自然回退到第 2 项自动推导，无需额外配置。
 */

interface RuntimeConfig {
    apiBaseUrl: string;
}

// 自动推导的 API 基地址：浏览器当前访问地址 + /v1。
// window.location.origin 自带用户实际访问的 host/端口/协议，容器化部署无需配置即可正确展示。
const AUTO_API_BASE_URL = `${window.location.origin}/v1`;

/**
 * 从 index.html 中 <script id="llm-gate-runtime-config" type="application/json"> 标签
 * 读取后端注入的运行时配置。读取失败（dev 模式占位符未替换 / 解析异常 / 注入空值）时
 * 回退到自动推导的 AUTO_API_BASE_URL。
 */
function loadRuntimeConfig(): RuntimeConfig {
    try {
        const el = document.getElementById('llm-gate-runtime-config');
        const text = el?.textContent?.trim();
        if (text && text !== '__LLM_GATE_RUNTIME_CONFIG__') {
            const parsed = JSON.parse(text);
            // 后端注入空字符串表示"自动推导"，此时回退到 AUTO_API_BASE_URL
            if (parsed && typeof parsed.apiBaseUrl === 'string' && parsed.apiBaseUrl) {
                return {apiBaseUrl: parsed.apiBaseUrl};
            }
        }
    } catch {
        // 解析失败时回退自动推导，避免阻塞前端渲染
    }
    return {apiBaseUrl: AUTO_API_BASE_URL};
}

export const RUNTIME_CONFIG: RuntimeConfig = loadRuntimeConfig();
