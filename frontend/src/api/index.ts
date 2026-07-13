/**
 * LLM Gate API service layer
 */
import request, {getToken, setToken, clearToken, LLM_GATE_TOKEN_KEY} from './request';
import type {AxiosResponse} from 'axios';
import type {
    RegisterRequest,
    LoginRequest,
    AuthResponse,
    User,
    Tool,
    ToolWithApiKey,
    CreateToolRequest,
    UpdateToolRequest,
    CreateRouteRequest,
    UpdateRouteRequest,
    ReorderRoutesRequest,
    ApiProviderKey,
    CreateProviderKeyRequest,
    UpdateProviderKeyRequest,
    UsageOverview,
    RequestStats,
    TokenStats,
    ApiToolUsage,
    RouteUsageDetail,
    TimeFilter,
    UsageRecordsResponse,
    GetUsageRecordsParams,
    HealthCheckResponse,
    ConnectionTestRequest,
    ConnectionTestResponse,
    ModelsProbeRequest,
    ModelsProbeResponse
} from '@/types';

// Re-export token management helpers
export {getToken, setToken, clearToken, LLM_GATE_TOKEN_KEY};

// ==================== Auth ====================

/**
 * Register a new account
 */
export function register(data: RegisterRequest): Promise<AxiosResponse<AuthResponse>> {
    return request({
        url: '/api/auth/register',
        method: 'post',
        data,
        skipAuth: true
    });
}

/**
 * Login with username and password
 */
export function login(data: LoginRequest): Promise<AxiosResponse<AuthResponse>> {
    return request({
        url: '/api/auth/login',
        method: 'post',
        data,
        skipAuth: true
    });
}

/**
 * Get current authenticated user
 */
export function getCurrentUser(): Promise<AxiosResponse<User>> {
    return request({
        url: '/api/auth/me',
        method: 'get'
    });
}

// ==================== Tool management ====================

export function getTools(): Promise<AxiosResponse<Tool[]>> {
    return request({url: '/api/tools/', method: 'get'});
}

export function getTool(toolId: number): Promise<AxiosResponse<Tool>> {
    return request({url: `/api/tools/${toolId}`, method: 'get'});
}

export function createTool(data: CreateToolRequest): Promise<AxiosResponse<ToolWithApiKey>> {
    return request({url: '/api/tools/', method: 'post', data});
}

export function updateTool(toolId: number, data: UpdateToolRequest): Promise<AxiosResponse<Tool>> {
    return request({url: `/api/tools/${toolId}`, method: 'put', data});
}

export function deleteTool(toolId: number): Promise<AxiosResponse<void>> {
    return request({url: `/api/tools/${toolId}`, method: 'delete'});
}

export function regenerateToolKey(toolId: number): Promise<AxiosResponse<ToolWithApiKey>> {
    return request({url: `/api/tools/${toolId}/regenerate-key`, method: 'post'});
}

// ==================== Route management ====================

export function addRoute(toolId: number, data: CreateRouteRequest): Promise<AxiosResponse<Tool>> {
    return request({url: `/api/tools/${toolId}/routes`, method: 'post', data});
}

export function updateRoute(toolId: number, routeName: string, data: UpdateRouteRequest): Promise<AxiosResponse<Tool>> {
    return request({url: `/api/tools/${toolId}/routes/${encodeURIComponent(routeName)}`, method: 'put', data});
}

export function deleteRoute(toolId: number, routeName: string): Promise<AxiosResponse<Tool>> {
    return request({url: `/api/tools/${toolId}/routes/${encodeURIComponent(routeName)}`, method: 'delete'});
}

export function activateRoute(toolId: number, routeName: string): Promise<AxiosResponse<Tool>> {
    return request({url: `/api/tools/${toolId}/activate/${encodeURIComponent(routeName)}`, method: 'put'});
}

export function deactivateRoute(toolId: number): Promise<AxiosResponse<Tool>> {
    return request({url: `/api/tools/${toolId}`, method: 'put', data: {active_route_name: ''}});
}

export function reorderRoutes(toolId: number, data: ReorderRoutesRequest): Promise<AxiosResponse<Tool>> {
    return request({url: `/api/tools/${toolId}/routes/reorder`, method: 'put', data});
}

// ==================== Provider Key ====================

export function getProviderKeys(): Promise<AxiosResponse<ApiProviderKey[]>> {
    return request({url: '/api/provider-keys/', method: 'get'});
}

export function getProviderKey(keyId: number): Promise<AxiosResponse<ApiProviderKey>> {
    return request({url: `/api/provider-keys/${keyId}`, method: 'get'});
}

export function createProviderKey(data: CreateProviderKeyRequest): Promise<AxiosResponse<ApiProviderKey>> {
    return request({url: '/api/provider-keys/', method: 'post', data});
}

export function updateProviderKey(keyId: number, data: UpdateProviderKeyRequest): Promise<AxiosResponse<ApiProviderKey>> {
    return request({url: `/api/provider-keys/${keyId}`, method: 'put', data});
}

export function deleteProviderKey(keyId: number): Promise<AxiosResponse<void>> {
    return request({url: `/api/provider-keys/${keyId}`, method: 'delete'});
}

// ==================== Usage statistics ====================

export function getUsageOverview(timeFilter: TimeFilter = 'month'): Promise<AxiosResponse<UsageOverview>> {
    return request({url: '/api/usage/overview', method: 'get', params: {time_filter: timeFilter}});
}

export function getRequestStats(timeFilter: TimeFilter = 'month'): Promise<AxiosResponse<RequestStats>> {
    return request({url: '/api/usage/requests', method: 'get', params: {time_filter: timeFilter}});
}

export function getTokenStats(): Promise<AxiosResponse<TokenStats>> {
    return request({url: '/api/usage/tokens', method: 'get'});
}

export function getToolUsage(timeFilter: TimeFilter = 'month'): Promise<AxiosResponse<ApiToolUsage[]>> {
    return request({url: '/api/usage/tools', method: 'get', params: {time_filter: timeFilter}});
}

export function getToolRouteUsage(toolId: number, timeFilter: TimeFilter = 'month'): Promise<AxiosResponse<RouteUsageDetail[]>> {
    return request({url: `/api/usage/tools/${toolId}/routes`, method: 'get', params: {time_filter: timeFilter}});
}

export function getUsageRecords(params?: GetUsageRecordsParams): Promise<AxiosResponse<UsageRecordsResponse>> {
    return request({url: '/api/usage/records', method: 'get', params});
}

// ==================== Health check ====================

export function healthCheck(): Promise<AxiosResponse<HealthCheckResponse>> {
    return request({url: '/health', method: 'get', skipAuth: true});
}

// ==================== Connection test ====================

export function testConnection(data: ConnectionTestRequest): Promise<AxiosResponse<ConnectionTestResponse>> {
    return request({url: '/api/test/connection', method: 'post', data});
}

// ==================== Model probe ====================

export function probeModels(data: ModelsProbeRequest): Promise<AxiosResponse<ModelsProbeResponse>> {
    return request({url: '/api/test/models', method: 'post', data});
}
