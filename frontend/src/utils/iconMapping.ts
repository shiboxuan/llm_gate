/**
 * LLMGate 图标映射工具
 *
 * 功能说明：
 * 1. 根据工具名称自动匹配对应的 App 图标（如 Cline、Cursor、Trae 等）
 * 2. 根据模型名称自动匹配对应的提供商图标（如 OpenAI、Anthropic 等）
 */

// ==================== 类型定义 ====================

export interface IconInfo {
    icon: string; // Iconify 图标名称或图片 URL
    iconColor: string; // 图标颜色
    iconBgColor: string; // 图标背景渐变色
    isImageUrl?: boolean; // 是否为图片 URL
}

export interface RouteIconInfo {
    icon: string; // Iconify 图标名称
    color: string; // 图标颜色
}

// ==================== 工具图标映射 ====================

/**
 * 工具名称关键字到图标的映射配置
 * 使用小写关键字进行匹配
 */
const TOOL_ICON_MAP: Record<string, IconInfo> = {
    // Cline - AI 编程助手
    cline: {
        icon: 'https://mintcdn.com/cline-efdc8260/tkBpPpnPdliQ8Wgu/assets/Cline_Logo-complete_black.png?fit=max&auto=format&n=tkBpPpnPdliQ8Wgu&q=85&s=e47e2108fe0ef7de1ae02704a8f5362c',
        iconColor: '#000000',
        iconBgColor: 'linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%)',
        isImageUrl: true
    },
    // Cursor - AI 代码编辑器
    cursor: {
        icon: 'https://workos.imgix.net/app-branding/environment_01GS6W3C901N50J4ZGFB6V1Z6C/01K7002RKC1S3W3WGAGWBX547Y',
        iconColor: '#000000',
        iconBgColor: 'linear-gradient(135deg, #faf5ff 0%, #f3e8ff 100%)',
        isImageUrl: true
    },
    // Trae - AI 开发工具
    trae: {
        icon: 'simple-icons:bytedance',
        iconColor: '#3b82f6',
        iconBgColor: 'linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%)'
    },
    // Claude Code - Anthropic 的代码助手
    claudecode: {
        icon: 'simple-icons:anthropic',
        iconColor: '#d97706',
        iconBgColor: 'linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%)'
    },
    'claude-code': {
        icon: 'simple-icons:anthropic',
        iconColor: '#d97706',
        iconBgColor: 'linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%)'
    },
    // Codex - OpenAI Codex
    codex: {
        icon: 'simple-icons:openai',
        iconColor: '#10a37f',
        iconBgColor: 'linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%)'
    },
    // Windsurf - Codeium 的 AI IDE
    windsurf: {
        icon: 'mdi:surfing',
        iconColor: '#06b6d4',
        iconBgColor: 'linear-gradient(135deg, #ecfeff 0%, #cffafe 100%)'
    },
    // GitHub Copilot
    copilot: {
        icon: 'simple-icons:githubcopilot',
        iconColor: '#000000',
        iconBgColor: 'linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)'
    },
    // JetBrains AI
    jetbrains: {
        icon: 'simple-icons:jetbrains',
        iconColor: '#000000',
        iconBgColor: 'linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%)'
    },
    // Tabnine
    tabnine: {
        icon: 'mdi:tab',
        iconColor: '#ca8a04',
        iconBgColor: 'linear-gradient(135deg, #fefce8 0%, #fef9c3 100%)'
    },
    // Amazon Q
    amazon: {
        icon: 'simple-icons:amazonaws',
        iconColor: '#f97316',
        iconBgColor: 'linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%)'
    },
    // Sourcegraph Cody
    cody: {
        icon: 'simple-icons:sourcegraph',
        iconColor: '#a855f7',
        iconBgColor: 'linear-gradient(135deg, #faf5ff 0%, #f3e8ff 100%)'
    },
    sourcegraph: {
        icon: 'simple-icons:sourcegraph',
        iconColor: '#a855f7',
        iconBgColor: 'linear-gradient(135deg, #faf5ff 0%, #f3e8ff 100%)'
    },
    // Continue
    continue: {
        icon: 'mdi:play-circle-outline',
        iconColor: '#22c55e',
        iconBgColor: 'linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)'
    },
    // Aider
    aider: {
        icon: 'mdi:robot-outline',
        iconColor: '#14b8a6',
        iconBgColor: 'linear-gradient(135deg, #f0fdfa 0%, #ccfbf1 100%)'
    },
    // Replit
    replit: {
        icon: 'simple-icons:replit',
        iconColor: '#f97316',
        iconBgColor: 'linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%)'
    },
    // OpenCode - AI 编程工具
    opencode: {
        icon: 'https://opencode.ai/docs/_astro/logo-light.B0yzR0O5.svg',
        iconColor: '#000000',
        iconBgColor: 'linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)',
        isImageUrl: true
    }
};

/**
 * 默认工具图标配置
 */
const DEFAULT_TOOL_ICON: IconInfo = {
    icon: 'heroicons:cpu-chip',
    iconColor: '#6366f1',
    iconBgColor: 'linear-gradient(135deg, #eef2ff 0%, #e0e7ff 100%)'
};

/**
 * 根据工具名称获取对应的图标配置
 * @param toolName 工具名称
 * @returns 图标配置信息
 */
export function getToolIcon(toolName: string): IconInfo {
    if (!toolName) {
        return DEFAULT_TOOL_ICON;
    }

    const lowerName = toolName.toLowerCase();

    // 遍历映射表，查找包含关键字的匹配
    for (const [keyword, iconInfo] of Object.entries(TOOL_ICON_MAP)) {
        if (lowerName.includes(keyword)) {
            return iconInfo;
        }
    }

    return DEFAULT_TOOL_ICON;
}

// ==================== 模型提供商图标映射 ====================

/**
 * 模型名称模式到提供商图标的映射配置
 * 使用正则表达式进行匹配
 */
interface ModelProviderPattern {
    pattern: RegExp;
    provider: string;
    icon: string;
    color: string;
}

const MODEL_PROVIDER_PATTERNS: ModelProviderPattern[] = [
    // OpenAI 系列（包含匹配，支持如 azure-gpt-4 等格式）
    {
        pattern: /(gpt|chatgpt|o1|o3|o4|text-davinci|text-curie|text-babbage|text-ada|dall-e|whisper)/i,
        provider: 'OpenAI',
        icon: 'simple-icons:openai',
        color: '#10a37f'
    },
    // Anthropic Claude 系列（包含匹配，支持如 anthropic.claude-xxx 等格式）
    {
        pattern: /claude/i,
        provider: 'Anthropic',
        icon: 'simple-icons:anthropic',
        color: '#d97706'
    },
    // Google Gemini/PaLM 系列
    {
        pattern: /(gemini|palm|bard|gemma)/i,
        provider: 'Google',
        icon: 'simple-icons:google',
        color: '#4285f4'
    },
    // DeepSeek 系列
    {
        pattern: /deepseek/i,
        provider: 'DeepSeek',
        icon: 'mdi:alpha-d-circle',
        color: '#0891b2'
    },
    // Moonshot/Kimi 系列
    {
        pattern: /(kimi|moonshot)/i,
        provider: 'Moonshot',
        icon: 'mdi:moon-waning-crescent',
        color: '#7c3aed'
    },
    // 阿里云通义千问系列
    {
        pattern: /(qwen|tongyi|qianwen)/i,
        provider: 'Alibaba',
        icon: 'simple-icons:alibabacloud',
        color: '#ff6a00'
    },
    // Meta LLaMA 系列
    {
        pattern: /(llama|codellama)/i,
        provider: 'Meta',
        icon: 'simple-icons:meta',
        color: '#0668e1'
    },
    // Mistral 系列
    {
        pattern: /(mistral|mixtral)/i,
        provider: 'Mistral',
        icon: 'mdi:alpha-m-circle',
        color: '#f97316'
    },
    // Cohere 系列
    {
        pattern: /(cohere|command|embed)/i,
        provider: 'Cohere',
        icon: 'mdi:alpha-c-circle',
        color: '#39594d'
    },
    // 百度文心一言系列
    {
        pattern: /(ernie|wenxin|yiyan)/i,
        provider: 'Baidu',
        icon: 'simple-icons:baidu',
        color: '#2932e1'
    },
    // 字节跳动豆包系列
    {
        pattern: /(doubao|skylark)/i,
        provider: 'ByteDance',
        icon: 'simple-icons:bytedance',
        color: '#3b82f6'
    },
    // 智谱 GLM 系列
    {
        pattern: /(glm|chatglm|zhipu)/i,
        provider: 'Zhipu',
        icon: 'mdi:alpha-z-circle',
        color: '#2563eb'
    },
    // 讯飞星火系列
    {
        pattern: /(spark|xinghuo)/i,
        provider: 'iFlytek',
        icon: 'mdi:fire',
        color: '#dc2626'
    },
    // 腾讯混元系列
    {
        pattern: /(hunyuan)/i,
        provider: 'Tencent',
        icon: 'simple-icons:tencentqq',
        color: '#12b7f5'
    },
    // AWS Bedrock / Amazon 系列
    {
        pattern: /(amazon|titan|bedrock)/i,
        provider: 'Amazon',
        icon: 'simple-icons:amazonaws',
        color: '#f97316'
    },
    // 零一万物 Yi 系列
    {
        pattern: /(yi-)/i,
        provider: '01.AI',
        icon: 'mdi:numeric-0',
        color: '#1e40af'
    },
    // Minimax 系列
    {
        pattern: /(minimax|abab)/i,
        provider: 'Minimax',
        icon: 'mdi:alpha-m-box',
        color: '#8b5cf6'
    },
    // Perplexity 系列
    {
        pattern: /(pplx|perplexity|sonar)/i,
        provider: 'Perplexity',
        icon: 'mdi:help-circle',
        color: '#22d3ee'
    },
    // xAI Grok 系列
    {
        pattern: /(grok)/i,
        provider: 'xAI',
        icon: 'simple-icons:x',
        color: '#000000'
    }
];

/**
 * 默认路由图标配置
 */
const DEFAULT_ROUTE_ICON: RouteIconInfo = {
    icon: 'heroicons:cpu-chip',
    color: '#64748b'
};

/**
 * 根据模型名称获取对应的提供商图标配置
 * @param modelName 模型名称
 * @returns 路由图标配置信息
 */
export function getModelProviderIcon(modelName: string): RouteIconInfo {
    if (!modelName) {
        return DEFAULT_ROUTE_ICON;
    }

    // 遍历模式列表，查找匹配的提供商
    for (const {pattern, icon, color} of MODEL_PROVIDER_PATTERNS) {
        if (pattern.test(modelName)) {
            return {icon, color};
        }
    }

    return DEFAULT_ROUTE_ICON;
}

/**
 * 根据模型名称获取提供商名称
 * @param modelName 模型名称
 * @returns 提供商名称
 */
export function getModelProviderName(modelName: string): string {
    if (!modelName) {
        return 'Unknown';
    }

    for (const {pattern, provider} of MODEL_PROVIDER_PATTERNS) {
        if (pattern.test(modelName)) {
            return provider;
        }
    }

    return 'Unknown';
}
