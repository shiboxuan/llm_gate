/**
 * LLM Gate axios instance and interceptors.
 *
 * Authentication strategy:
 * - Token stored in localStorage under LLM_GATE_TOKEN_KEY
 * - Sent as Authorization: Bearer <token>
 * - 401 response -> clear token and redirect to /login
 *
 * No Feishu / main-site cookie logic. The frontend is standalone.
 */
import axios, {AxiosInstance, InternalAxiosRequestConfig, AxiosResponse, AxiosError} from 'axios';
import {message} from 'antd';
import {llmGateHost} from '@/utils/variable';
import {ErrorMessages} from '@/types';
import type {AuthResponse} from '@/types';

// localStorage key for the access token
export const LLM_GATE_TOKEN_KEY = 'llm_gate_token';

// Request config extension
export interface LLMGateRequestConfig<D = any> extends InternalAxiosRequestConfig<D> {
    /** Skip adding the Authorization header (e.g. login / register) */
    skipAuth?: boolean;
    /** Suppress antd message on error */
    silent?: boolean;
}

// ==================== Token helpers ====================

export const getToken = (): string | null => {
    return localStorage.getItem(LLM_GATE_TOKEN_KEY);
};

export const setToken = (token: string): void => {
    localStorage.setItem(LLM_GATE_TOKEN_KEY, token);
};

export const clearToken = (): void => {
    localStorage.removeItem(LLM_GATE_TOKEN_KEY);
};

// ==================== Redirect to login ====================

let redirectTimer: ReturnType<typeof setTimeout> | null = null;

const redirectToLogin = (): void => {
    if (redirectTimer) return; // avoid duplicate redirects
    redirectTimer = setTimeout(() => {
        redirectTimer = null;
        // Use pathname so the user returns after login
        const returnUrl = encodeURIComponent(window.location.pathname + window.location.search);
        window.location.href = `/login?returnUrl=${returnUrl}`;
    }, 100);
};

// ==================== Error message helper ====================

const getErrorMessage = (code: number, defaultMessage?: string): string => {
    return ErrorMessages[code] || defaultMessage || '请求失败，请稍后重试';
};

// ==================== Axios instance ====================

const llmGateAxios: AxiosInstance = axios.create({
    baseURL: llmGateHost,
    timeout: 30000,
    headers: {
        'Content-Type': 'application/json;charset=utf-8'
    }
});

// Request interceptor: attach Authorization header
llmGateAxios.interceptors.request.use(
    (config: InternalAxiosRequestConfig & {skipAuth?: boolean}) => {
        if (!config.skipAuth) {
            const token = getToken();
            if (token) {
                config.headers.Authorization = `Bearer ${token}`;
            }
        }
        return config;
    },
    (error: AxiosError) => {
        console.error('[LLM Gate] request interceptor error:', error);
        return Promise.reject(error);
    }
);

// Response interceptor: unified error handling
llmGateAxios.interceptors.response.use(
    (response: AxiosResponse) => response,
    async (error: unknown) => {
        const axiosError = error as AxiosError<{code?: number; message?: string}>;
        const config = axiosError.config as LLMGateRequestConfig | undefined;
        const status = axiosError.response?.status;
        const responseData = axiosError.response?.data;
        const errorCode = responseData?.code;

        // Request cancelled - silent
        if (axios.isCancel(error) || axiosError.code === 'ERR_CANCELED') {
            return Promise.reject(error);
        }

        // Silent mode
        if (config?.silent) {
            return Promise.reject(error);
        }

        // 401 Unauthorized -> clear token and redirect to login
        if (status === 401) {
            // Don't show message for login/register endpoints
            const isAuthEndpoint = config?.url?.includes('/api/auth/login') || config?.url?.includes('/api/auth/register');
            if (!isAuthEndpoint) {
                clearToken();
                message.warning('登录已过期，请重新登录');
                redirectToLogin();
            }
            return Promise.reject(error);
        }

        // 403 Forbidden
        if (status === 403) {
            const errorMessage = errorCode ? getErrorMessage(errorCode) : '无权限访问';
            message.error(errorMessage);
            return Promise.reject(error);
        }

        // 409 Conflict
        if (status === 409) {
            const errorMessage = errorCode ? getErrorMessage(errorCode) : responseData?.message || '资源冲突';
            message.error(errorMessage);
            return Promise.reject(error);
        }

        // 422 Validation error
        if (status === 422) {
            const detail = (axiosError.response?.data as any)?.detail;
            let errorMessage: string;

            if (Array.isArray(detail) && detail.length > 0) {
                errorMessage = detail
                    .map((item: any) => {
                        const path = Array.isArray(item?.loc) ? item.loc.join('.') : item?.loc;
                        if (item?.msg && path) return `${path}: ${item.msg}`;
                        if (item?.msg) return item.msg;
                        if (typeof item === 'string') return item;
                        return '';
                    })
                    .filter(Boolean)
                    .join('; ');
            } else if (typeof detail === 'string') {
                errorMessage = detail;
            } else {
                errorMessage = '参数校验失败';
            }

            message.error(errorMessage);
            return Promise.reject(error);
        }

        // 429 Rate limit
        if (status === 429) {
            message.warning('请求过于频繁，请稍后再试');
            return Promise.reject(error);
        }

        // 500+ server error
        if (status && status >= 500) {
            const errorMessage = errorCode ? getErrorMessage(errorCode) : responseData?.message || '服务器内部错误';
            message.error(errorMessage);
            return Promise.reject(error);
        }

        // Timeout
        if (axiosError.code === 'ECONNABORTED' || axiosError.message?.includes('timeout')) {
            message.error('请求超时，请稍后再试');
            return Promise.reject(error);
        }

        // Network error
        if (axiosError.code === 'ERR_NETWORK') {
            message.error('网络连接失败，请检查网络');
            return Promise.reject(error);
        }

        // Other errors
        const errorMessage = errorCode ? getErrorMessage(errorCode) : responseData?.message || axiosError.message || '请求失败';
        message.error(errorMessage);
        return Promise.reject(error);
    }
);

// Unified request function
function createRequest(service: AxiosInstance) {
    return function <T>(config: {
        url: string;
        method?: string;
        params?: any;
        data?: any;
        headers?: Record<string, string>;
        timeout?: number;
        skipAuth?: boolean;
        silent?: boolean;
    }): Promise<AxiosResponse<T>> {
        return service(config as any);
    };
}

export default createRequest(llmGateAxios);
