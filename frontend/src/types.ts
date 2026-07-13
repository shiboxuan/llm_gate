/**
 * LLM Gate type definitions
 */

// ==================== API 类型定义 ====================

/** API 类型枚举 */
export type ApiType = 'openai_chat' | 'openai_responses' | 'anthropic_messages' | 'gemini_generate' | 'openai_embeddings';

/** API 类型显示名称映射 */
export const API_TYPE_LABELS: Record<ApiType, string> = {
    openai_chat: 'OpenAI Chat',
    openai_responses: 'OpenAI Responses',
    anthropic_messages: 'Anthropic Messages',
    gemini_generate: 'Gemini',
    openai_embeddings: 'OpenAI Embeddings'
};

/** API 类型颜色配置（用于标签显示） */
export const API_TYPE_COLORS: Record<ApiType, {bg: string; text: string; border: string}> = {
    openai_chat: {bg: '#e0f2fe', text: '#0369a1', border: '#7dd3fc'},
    openai_responses: {bg: '#fef3c7', text: '#b45309', border: '#fcd34d'},
    anthropic_messages: {bg: '#fce7f3', text: '#be185d', border: '#f9a8d4'},
    gemini_generate: {bg: '#dcfce7', text: '#15803d', border: '#86efac'},
    openai_embeddings: {bg: '#ede9fe', text: '#6d28d9', border: '#c4b5fd'}
};

/** API 类型下拉选项 */
export const API_TYPE_OPTIONS = [
    {value: 'openai_chat', label: 'OpenAI Chat'},
    {value: 'anthropic_messages', label: 'Anthropic Messages'},
    {value: 'openai_responses', label: 'OpenAI Responses'},
    {value: 'openai_embeddings', label: 'OpenAI Embeddings'}
    // { value: 'gemini_generate', label: 'Gemini' } // backend not yet implemented
];

// ==================== 路由配置类型 ====================

export interface RouteConfig {
    id: string;
    name: string;
    provider: string;
    endpoint: string;
    modelName: string;
    enabled: boolean;
    apiType?: ApiType;
    order: number;
}

export interface ToolConfig {
    id: string;
    name: string;
    description: string;
    icon: string;
    iconColor: string;
    iconBgColor: string;
    apiKey: string;
    status: 'running' | 'configuring' | 'stopped';
    apiType?: ApiType;
    routes: RouteConfig[];
}

export interface ProviderKey {
    id: string;
    name: string;
    key: string;
}

// ==================== Tab 类型 ====================

export type TabType = 'tools' | 'interface-keys' | 'usage';

export const TAB_TITLES: Record<TabType, string> = {
    tools: '工具管理',
    'interface-keys': '供应商密钥管理',
    usage: '统计'
};

// ==================== API 响应类型 ====================

export interface ApiResponse<T = any> {
    code?: number;
    message?: string;
    data: T;
}

export interface ErrorResponse {
    code: number;
    message: string;
    data: null;
}

export type TimeFilter = 'all' | 'today' | 'week' | 'month';

// ==================== 健康检查类型 ====================

export interface HealthCheckResponse {
    status: 'healthy' | 'unhealthy';
    app_name: string;
    app_env: string;
}

export interface HealthStatus {
    isHealthy: boolean;
    appName: string;
    appEnv: string;
    latency: number;
    lastChecked: Date;
    loading: boolean;
    error: string | null;
}

// ==================== 用户与认证类型 ====================

/** User object returned by the backend */
export interface User {
    id: string;
    username: string;
    email: string;
    is_admin: boolean;
    status: number;
}

/** Registration request body */
export interface RegisterRequest {
    username: string;
    password: string;
    email?: string;
}

/** Login request body */
export interface LoginRequest {
    username: string;
    password: string;
}

/** Auth response (register / login) */
export interface AuthResponse {
    access_token: string;
    token_type: string;
    user: User;
}

// ==================== 工具相关 API 类型 ====================

export interface Tool {
    id: number;
    user_id: string;
    name: string;
    description: string;
    active_route_name: string | null;
    routes: Route[];
    status: number;
    api_type?: ApiType;
    created_at: string;
    updated_at: string;
}

export interface ToolWithApiKey extends Tool {
    api_key: string;
}

export interface CreateToolRequest {
    name: string;
    description?: string;
    api_type?: ApiType;
}

export interface UpdateToolRequest {
    name?: string;
    description?: string;
    active_route_name?: string;
    status?: number;
    api_type?: ApiType;
}

// ==================== 路由相关 API 类型 ====================

export interface Route {
    name: string;
    provider: string;
    base_url: string;
    model: string;
    provider_key_name: string;
    api_path: string;
    is_active: boolean;
    api_type?: ApiType;
    order: number;
}

export interface CreateRouteRequest {
    name: string;
    provider: string;
    base_url: string;
    model: string;
    provider_key_name: string;
    api_path?: string;
    set_active?: boolean;
    api_type?: ApiType;
}

export interface UpdateRouteRequest {
    provider?: string;
    base_url?: string;
    model?: string;
    provider_key_name?: string;
    api_path?: string;
    api_type?: ApiType;
}

export interface ReorderRoutesRequest {
    orders: Record<string, number>;
}

export interface ConnectionTestRequest {
    api_type: ApiType;
    base_url: string;
    model: string;
    provider_key_name: string;
}

export interface ConnectionTestResponse {
    success: boolean;
    message: string;
    latency_ms?: number;
    error_code?: string;
    details?: string;
}

// ==================== Provider Key API 类型 ====================

export interface ApiProviderKey {
    id: number;
    user_id: string;
    name: string;
    status: number;
    created_at: string;
}

export interface CreateProviderKeyRequest {
    name: string;
    api_key: string;
}

export interface UpdateProviderKeyRequest {
    api_key?: string;
    status?: number;
}

// ==================== 用量统计 API 类型 ====================

export interface RequestStats {
    total_requests: number;
    success_requests: number;
    error_requests: number;
    success_rate: number;
}

export interface TokenStats {
    total_tokens: number;
    month_tokens: number;
    today_tokens: number;
    month_change_rate: number;
    today_change_rate: number;
}

export interface RouteUsageDetail {
    route_name: string;
    model: string;
    api_path: string;
    is_active: boolean;
    total_tokens: number;
}

export interface ApiToolUsage {
    tool_id: number;
    tool_name: string;
    description: string;
    route_count: number;
    request_count: number;
    total_tokens: number;
    usage_percentage: number;
    routes: RouteUsageDetail[];
}

export interface UsageOverview {
    request_stats: RequestStats;
    token_stats: TokenStats;
    tool_usage: ApiToolUsage[];
}

// ==================== 统计展示类型 ====================

export interface StatCard {
    icon: string;
    iconColor: string;
    value: string;
    label: string;
    trend?: {
        type: 'up' | 'down';
        value: string;
    };
}

export interface ToolUsageData {
    id: string;
    name: string;
    description: string;
    icon: string;
    iconBgColor: string;
    isImageUrl?: boolean;
    routeCount: number;
    requestCount: number;
    tokenCount: string;
    percentage: number;
    routes: RouteUsageData[];
}

export interface RouteUsageData {
    id: string;
    name: string;
    endpoint: string;
    modelName: string;
    requestCount: number;
    isActive: boolean;
}

export interface RouteTypeUsage {
    name: string;
    path: string;
    description: string;
    colorClass: string;
    count: number;
}

// ==================== 错误码枚举 ====================

export enum ErrorCode {
    PARAM_MISSING = 10001,
    PARAM_INVALID = 10002,
    UNAUTHORIZED = 10003,
    TOKEN_EXPIRED = 10004,
    TOKEN_INVALID = 10005,
    FORBIDDEN = 10006,
    RATE_LIMIT_EXCEEDED = 10007,
    INTERNAL_ERROR = 10008,
    USER_NOT_FOUND = 11001,
    USER_DISABLED = 11002,
    USER_CREATE_FAILED = 11003,
    TOOL_NOT_FOUND = 12001,
    TOOL_DISABLED = 12002,
    TOOL_TOKEN_INVALID = 12003,
    TOOL_CREATE_FAILED = 12004,
    TOOL_UPDATE_FAILED = 12005,
    TOOL_DELETE_FAILED = 12006,
    TOOL_NAME_DUPLICATE = 12007,
    ROUTE_NOT_FOUND = 13001,
    ROUTE_NOT_ACTIVE = 13002,
    ROUTE_CREATE_FAILED = 13003,
    ROUTE_UPDATE_FAILED = 13004,
    ROUTE_DELETE_FAILED = 13005,
    ROUTE_NAME_DUPLICATE = 13006,
    PROVIDER_KEY_NOT_FOUND = 14001,
    PROVIDER_KEY_DECRYPT_FAILED = 14002,
    PROVIDER_KEY_CREATE_FAILED = 14003,
    PROVIDER_KEY_NAME_DUPLICATE = 14004
}

// ==================== 用量记录 API 类型 ====================

export interface UsageRecord {
    id: number;
    user_id: string;
    tool_id: number;
    tool_name: string | null;
    route_name: string;
    provider_key_name: string;
    model: string;
    base_url: string;
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    cache_creation_input_tokens: number;
    cache_read_input_tokens: number;
    cached_tokens: number;
    request_id: string | null;
    status: 'success' | 'error';
    error_message: string | null;
    created_at: string | null;
}

export interface UsageRecordsResponse {
    records: UsageRecord[];
    total: number;
    limit: number;
}

export interface GetUsageRecordsParams {
    limit?: number;
    tool_id?: number;
}

// ==================== 成本计算类型 ====================

export interface ModelPricing {
    baseInputTokens: number;
    cache5mWrites: number;
    cache1hWrites: number;
    cacheHitsRefreshes: number;
    outputTokens: number;
}

export const MODEL_PRICING: Record<string, ModelPricing> = {
    'claude-opus-4-6': {baseInputTokens: 5, cache5mWrites: 6.25, cache1hWrites: 10, cacheHitsRefreshes: 0.5, outputTokens: 25},
    'claude-opus-4-5': {baseInputTokens: 5, cache5mWrites: 6.25, cache1hWrites: 10, cacheHitsRefreshes: 0.5, outputTokens: 25},
    'claude-opus-4-1': {baseInputTokens: 15, cache5mWrites: 18.75, cache1hWrites: 30, cacheHitsRefreshes: 1.5, outputTokens: 75},
    'claude-opus-4': {baseInputTokens: 15, cache5mWrites: 18.75, cache1hWrites: 30, cacheHitsRefreshes: 1.5, outputTokens: 75},
    'claude-sonnet-4-6': {baseInputTokens: 3, cache5mWrites: 3.75, cache1hWrites: 6, cacheHitsRefreshes: 0.3, outputTokens: 15},
    'claude-sonnet-4-5': {baseInputTokens: 3, cache5mWrites: 3.75, cache1hWrites: 6, cacheHitsRefreshes: 0.3, outputTokens: 15},
    'claude-sonnet-4': {baseInputTokens: 3, cache5mWrites: 3.75, cache1hWrites: 6, cacheHitsRefreshes: 0.3, outputTokens: 15},
    'claude-3-7-sonnet': {baseInputTokens: 3, cache5mWrites: 3.75, cache1hWrites: 6, cacheHitsRefreshes: 0.3, outputTokens: 15},
    'claude-haiku-4-5': {baseInputTokens: 1, cache5mWrites: 1.25, cache1hWrites: 2, cacheHitsRefreshes: 0.1, outputTokens: 5},
    'claude-3-5-haiku': {baseInputTokens: 0.8, cache5mWrites: 1, cache1hWrites: 1.6, cacheHitsRefreshes: 0.08, outputTokens: 4},
    'claude-3-opus': {baseInputTokens: 15, cache5mWrites: 18.75, cache1hWrites: 30, cacheHitsRefreshes: 1.5, outputTokens: 75},
    'claude-3-haiku': {baseInputTokens: 0.25, cache5mWrites: 0.3, cache1hWrites: 0.5, cacheHitsRefreshes: 0.03, outputTokens: 1.25}
};

export const getModelPricing = (modelName: string): ModelPricing | null => {
    const lowerName = modelName.toLowerCase();

    if (MODEL_PRICING[lowerName]) {
        return MODEL_PRICING[lowerName];
    }

    if (lowerName.includes('opus') && (lowerName.includes('4-6') || lowerName.includes('4.6'))) {
        return MODEL_PRICING['claude-opus-4-6'];
    }
    if (lowerName.includes('opus') && (lowerName.includes('4-5') || lowerName.includes('4.5'))) {
        return MODEL_PRICING['claude-opus-4-5'];
    }
    if (lowerName.includes('opus') && (lowerName.includes('4-1') || lowerName.includes('4.1'))) {
        return MODEL_PRICING['claude-opus-4-1'];
    }
    if (lowerName.includes('opus') && lowerName.includes('4') && !lowerName.includes('3')) {
        return MODEL_PRICING['claude-opus-4'];
    }
    if (lowerName.includes('opus') && lowerName.includes('3')) {
        return MODEL_PRICING['claude-3-opus'];
    }

    if (lowerName.includes('sonnet') && (lowerName.includes('4-6') || lowerName.includes('4.6'))) {
        return MODEL_PRICING['claude-sonnet-4-6'];
    }
    if (lowerName.includes('sonnet') && (lowerName.includes('4-5') || lowerName.includes('4.5') || lowerName.includes('3-5') || lowerName.includes('3.5'))) {
        return MODEL_PRICING['claude-sonnet-4-5'];
    }
    if (lowerName.includes('sonnet') && (lowerName.includes('3-7') || lowerName.includes('3.7'))) {
        return MODEL_PRICING['claude-3-7-sonnet'];
    }
    if (lowerName.includes('sonnet') && lowerName.includes('4')) {
        return MODEL_PRICING['claude-sonnet-4'];
    }

    if (lowerName.includes('haiku') && (lowerName.includes('4-5') || lowerName.includes('4.5'))) {
        return MODEL_PRICING['claude-haiku-4-5'];
    }
    if (lowerName.includes('haiku') && (lowerName.includes('3-5') || lowerName.includes('3.5'))) {
        return MODEL_PRICING['claude-3-5-haiku'];
    }
    if (lowerName.includes('haiku') && lowerName.includes('3')) {
        return MODEL_PRICING['claude-3-haiku'];
    }

    return null;
};

export const calculateRecordCost = (record: UsageRecord): number | null => {
    const pricing = getModelPricing(record.model);
    if (!pricing) return null;

    const baseInputCost = (record.prompt_tokens - record.cache_creation_input_tokens - record.cache_read_input_tokens) * pricing.baseInputTokens / 1000000;
    const cacheWriteCost = record.cache_creation_input_tokens * pricing.cache5mWrites / 1000000;
    const cacheReadCost = record.cache_read_input_tokens * pricing.cacheHitsRefreshes / 1000000;
    const outputCost = record.completion_tokens * pricing.outputTokens / 1000000;

    return Math.max(0, baseInputCost) + cacheWriteCost + cacheReadCost + outputCost;
};

// ==================== OpenAI 成本计算类型 ====================

export interface OpenAIPricing {
    input: number;
    cachedInput: number;
    output: number;
    longInput?: number;
    longCachedInput?: number;
    longOutput?: number;
}

export const OPENAI_MODEL_PRICING: Record<string, OpenAIPricing> = {
    'gpt-5.4': {input: 2.5, cachedInput: 0.25, output: 15, longInput: 5, longCachedInput: 0.5, longOutput: 22.5},
    'gpt-5.4-pro': {input: 30, cachedInput: 0, output: 180, longInput: 60, longCachedInput: 0, longOutput: 270},
    'gpt-5.2': {input: 1.75, cachedInput: 0.175, output: 14},
    'gpt-5.1': {input: 1.25, cachedInput: 0.125, output: 10},
    'gpt-5': {input: 1.25, cachedInput: 0.125, output: 10},
    'gpt-5-mini': {input: 0.25, cachedInput: 0.025, output: 2},
    'gpt-5-nano': {input: 0.05, cachedInput: 0.005, output: 0.4},
    'gpt-5.3-chat-latest': {input: 1.75, cachedInput: 0.175, output: 14},
    'gpt-5.2-chat-latest': {input: 1.75, cachedInput: 0.175, output: 14},
    'gpt-5.1-chat-latest': {input: 1.25, cachedInput: 0.125, output: 10},
    'gpt-5-chat-latest': {input: 1.25, cachedInput: 0.125, output: 10},
    'gpt-5.3-codex': {input: 1.75, cachedInput: 0.175, output: 14},
    'gpt-5.2-codex': {input: 1.75, cachedInput: 0.175, output: 14},
    'gpt-5.1-codex-max': {input: 1.25, cachedInput: 0.125, output: 10},
    'gpt-5.1-codex': {input: 1.25, cachedInput: 0.125, output: 10},
    'gpt-5-codex': {input: 1.25, cachedInput: 0.125, output: 10},
    'gpt-5.1-codex-mini': {input: 0.25, cachedInput: 0.025, output: 2},
    'codex-mini-latest': {input: 1.5, cachedInput: 0.375, output: 6},
    'gpt-5.2-pro': {input: 21, cachedInput: 0, output: 168},
    'gpt-5-pro': {input: 15, cachedInput: 0, output: 120},
    'gpt-4.1': {input: 2, cachedInput: 0.5, output: 8},
    'gpt-4.1-mini': {input: 0.4, cachedInput: 0.1, output: 1.6},
    'gpt-4.1-nano': {input: 0.1, cachedInput: 0.025, output: 0.4},
    'gpt-4o': {input: 2.5, cachedInput: 1.25, output: 10},
    'gpt-4o-2024-05-13': {input: 5, cachedInput: 0, output: 15},
    'gpt-4o-mini': {input: 0.15, cachedInput: 0.075, output: 0.6},
    'gpt-realtime': {input: 4, cachedInput: 0.4, output: 16},
    'gpt-realtime-1.5': {input: 4, cachedInput: 0.4, output: 16},
    'gpt-realtime-mini': {input: 0.6, cachedInput: 0.06, output: 2.4},
    'gpt-4o-realtime-preview': {input: 5, cachedInput: 2.5, output: 20},
    'gpt-4o-mini-realtime-preview': {input: 0.6, cachedInput: 0.3, output: 2.4},
    'gpt-audio': {input: 2.5, cachedInput: 0, output: 10},
    'gpt-audio-1.5': {input: 2.5, cachedInput: 0, output: 10},
    'gpt-audio-mini': {input: 0.6, cachedInput: 0, output: 2.4},
    'gpt-4o-audio-preview': {input: 2.5, cachedInput: 0, output: 10},
    'gpt-4o-mini-audio-preview': {input: 0.15, cachedInput: 0, output: 0.6},
    'o1': {input: 15, cachedInput: 7.5, output: 60},
    'o1-pro': {input: 150, cachedInput: 0, output: 600},
    'o3-pro': {input: 20, cachedInput: 0, output: 80},
    'o3': {input: 2, cachedInput: 0.5, output: 8},
    'o3-deep-research': {input: 10, cachedInput: 2.5, output: 40},
    'o4-mini': {input: 1.1, cachedInput: 0.275, output: 4.4},
    'o4-mini-deep-research': {input: 2, cachedInput: 0.5, output: 8},
    'o3-mini': {input: 1.1, cachedInput: 0.55, output: 4.4},
    'o1-mini': {input: 1.1, cachedInput: 0.55, output: 4.4},
    'gpt-5-search-api': {input: 1.25, cachedInput: 0.125, output: 10},
    'gpt-4o-mini-search-preview': {input: 0.15, cachedInput: 0, output: 0.6},
    'gpt-4o-search-preview': {input: 2.5, cachedInput: 0, output: 10},
    'computer-use-preview': {input: 3, cachedInput: 0, output: 12},
    'gpt-image-1.5': {input: 5, cachedInput: 1.25, output: 10},
    'chatgpt-image-latest': {input: 5, cachedInput: 1.25, output: 10},
    'gpt-image-1': {input: 5, cachedInput: 1.25, output: 0},
    'gpt-image-1-mini': {input: 2, cachedInput: 0.2, output: 0}
};

export const getOpenAIPricing = (modelName: string): OpenAIPricing | null => {
    const lowerName = modelName.toLowerCase();

    if (OPENAI_MODEL_PRICING[lowerName]) {
        return OPENAI_MODEL_PRICING[lowerName];
    }

    for (const key of Object.keys(OPENAI_MODEL_PRICING)) {
        if (lowerName.includes(key) || key.includes(lowerName)) {
            return OPENAI_MODEL_PRICING[key];
        }
    }

    return null;
};

export const isLongContext = (totalTokens: number): boolean => {
    return totalTokens >= 272000;
};

export const calculateOpenAIRecordCost = (record: UsageRecord, useLongContext?: boolean): number | null => {
    const pricing = getOpenAIPricing(record.model);
    if (!pricing) return null;

    const useLong = useLongContext ?? isLongContext(record.total_tokens);

    const inputPrice = useLong && pricing.longInput !== undefined ? pricing.longInput : pricing.input;
    const cachedInputPrice = useLong && pricing.longCachedInput !== undefined ? pricing.longCachedInput : pricing.cachedInput;
    const outputPrice = useLong && pricing.longOutput !== undefined ? pricing.longOutput : pricing.output;

    const baseInputTokens = record.prompt_tokens - record.cached_tokens;
    const inputCost = baseInputTokens * inputPrice / 1000000;
    const cachedInputCost = record.cached_tokens * cachedInputPrice / 1000000;
    const outputCost = record.completion_tokens * outputPrice / 1000000;

    return Math.max(0, inputCost) + cachedInputCost + outputCost;
};

// ==================== 模型探测器类型 ====================

export interface ModelInfo {
    id: string;
    object: string;
    created?: number;
    owned_by?: string;
    [key: string]: any;
}

export interface ModelsListData {
    object: string;
    data: ModelInfo[];
}

export interface ProbeTarget {
    base_url: string;
    provider_key_name: string;
}

export interface ModelsProbeRequest {
    targets: ProbeTarget[];
}

export interface ProbeResult {
    base_url: string;
    success: boolean;
    message: string;
    latency_ms: number | null;
    data: ModelsListData | null;
    error_code: string | null;
}

export interface ModelsProbeResponse {
    results: ProbeResult[];
}

/** Error code message mapping */
export const ErrorMessages: Record<number, string> = {
    [ErrorCode.PARAM_MISSING]: '缺少必要参数',
    [ErrorCode.PARAM_INVALID]: '参数格式无效',
    [ErrorCode.UNAUTHORIZED]: '未授权，请重新登录',
    [ErrorCode.TOKEN_EXPIRED]: 'Token已过期，请重新登录',
    [ErrorCode.TOKEN_INVALID]: 'Token无效',
    [ErrorCode.FORBIDDEN]: '无权限访问',
    [ErrorCode.RATE_LIMIT_EXCEEDED]: '请求过于频繁，请稍后再试',
    [ErrorCode.INTERNAL_ERROR]: '服务器内部错误',
    [ErrorCode.USER_NOT_FOUND]: '用户不存在',
    [ErrorCode.USER_DISABLED]: '用户已被禁用',
    [ErrorCode.USER_CREATE_FAILED]: '用户创建失败',
    [ErrorCode.TOOL_NOT_FOUND]: '工具不存在',
    [ErrorCode.TOOL_DISABLED]: '工具已被禁用',
    [ErrorCode.TOOL_TOKEN_INVALID]: '工具Token无效',
    [ErrorCode.TOOL_CREATE_FAILED]: '工具创建失败',
    [ErrorCode.TOOL_UPDATE_FAILED]: '工具更新失败',
    [ErrorCode.TOOL_DELETE_FAILED]: '工具删除失败',
    [ErrorCode.TOOL_NAME_DUPLICATE]: '工具名称已存在',
    [ErrorCode.ROUTE_NOT_FOUND]: '路由不存在',
    [ErrorCode.ROUTE_NOT_ACTIVE]: '无激活路由',
    [ErrorCode.ROUTE_CREATE_FAILED]: '路由创建失败',
    [ErrorCode.ROUTE_UPDATE_FAILED]: '路由更新失败',
    [ErrorCode.ROUTE_DELETE_FAILED]: '路由删除失败，不能删除激活中的路由',
    [ErrorCode.ROUTE_NAME_DUPLICATE]: '路由名称已存在',
    [ErrorCode.PROVIDER_KEY_NOT_FOUND]: '密钥不存在',
    [ErrorCode.PROVIDER_KEY_DECRYPT_FAILED]: '密钥解密失败',
    [ErrorCode.PROVIDER_KEY_CREATE_FAILED]: '密钥创建失败',
    [ErrorCode.PROVIDER_KEY_NAME_DUPLICATE]: '密钥名称已存在'
};
