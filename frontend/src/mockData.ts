/**
 * LLMGate 模拟数据
 * TODO: 后续删除，替换为真实 API 数据
 */

import {ToolConfig, ProviderKey, StatCard, ToolUsageData, RouteTypeUsage} from './types';

// 是否使用模拟数据（开发阶段设为true，对接API时改为false）
export const USE_MOCK_DATA = false;

// 供应商选项
export const PROVIDER_OPTIONS = [
    {value: 'winky', label: 'Winky'},
    {value: 'bedrock', label: 'AWS Bedrock'},
    {value: 'openai', label: 'OpenAI'},
    {value: 'anthropic', label: 'Anthropic'}
];

// 工具列表模拟数据
export const mockTools: ToolConfig[] = [
    {
        id: '1',
        name: 'Claude Assistant',
        description: '智能对话助手，支持多轮对话和复杂任务处理',
        icon: 'simple-icons:anthropic',
        iconColor: '#ea580c',
        iconBgColor: 'linear-gradient(to bottom right, #fed7aa, #ffedd5)',
        apiKey: 'sk-claude-abc123xyz789',
        status: 'running',
        routes: [
            {
                id: '1-1',
                name: 'Claude Sonnet 主路由',
                provider: 'winky',
                endpoint: '/v1/messages',
                modelName: 'claude-sonnet-4-20250514',
                enabled: true,
                order: 0
            },
            {
                id: '1-2',
                name: 'Claude Opus 备用',
                provider: 'winky',
                endpoint: '/v1/messages',
                modelName: 'claude-opus-4-20250514',
                enabled: false,
                order: 1
            },
            {
                id: '1-3',
                name: 'Claude Haiku 快速',
                provider: 'winky',
                endpoint: '/v1/messages',
                modelName: 'claude-3-5-haiku-20241022',
                enabled: false,
                order: 2
            },
            {
                id: '1-4',
                name: 'OpenAI 兼容接口',
                provider: 'winky',
                endpoint: '/v1/chat/completions',
                modelName: 'claude-sonnet-4-20250514',
                enabled: false,
                order: 3
            }
        ]
    },
    {
        id: '2',
        name: 'OpenAI GPT',
        description: '通用大语言模型，适用于各类文本生成任务',
        icon: 'simple-icons:openai',
        iconColor: '#059669',
        iconBgColor: 'linear-gradient(to bottom right, #d1fae5, #ecfdf5)',
        apiKey: 'sk-openai-def456uvw012',
        status: 'running',
        routes: [
            {
                id: '2-1',
                name: 'GPT-4o 主路由',
                provider: 'winky',
                endpoint: '/v1/responses',
                modelName: 'gpt-4o',
                enabled: true,
                order: 0
            },
            {
                id: '2-2',
                name: 'GPT-4o-mini 轻量',
                provider: 'winky',
                endpoint: '/v1/responses',
                modelName: 'gpt-4o-mini',
                enabled: false,
                order: 1
            },
            {
                id: '2-3',
                name: 'GPT-4o Chat',
                provider: 'winky',
                endpoint: '/v1/chat/completions',
                modelName: 'gpt-4o',
                enabled: false,
                order: 2
            },
            {
                id: '2-4',
                name: 'GPT-4 Turbo',
                provider: 'winky',
                endpoint: '/v1/chat/completions',
                modelName: 'gpt-4-turbo',
                enabled: false,
                order: 3
            }
        ]
    },
    {
        id: '3',
        name: 'Moonshot Kimi',
        description: '月之暗面大模型，擅长长文本理解与生成',
        icon: 'heroicons:sparkles',
        iconColor: '#7c3aed',
        iconBgColor: 'linear-gradient(to bottom right, #ede9fe, #f5f3ff)',
        apiKey: 'sk-kimi-ghi789rst456',
        status: 'running',
        routes: [
            {
                id: '3-1',
                name: 'Kimi K2 主路由',
                provider: 'winky',
                endpoint: '/v1/messages',
                modelName: 'kimi-k2-0711-preview',
                enabled: true,
                order: 0
            },
            {
                id: '3-2',
                name: 'Kimi K2 Chat',
                provider: 'winky',
                endpoint: '/v1/chat/completions',
                modelName: 'kimi-k2-0711-preview',
                enabled: false,
                order: 1
            },
            {
                id: '3-3',
                name: 'Moonshot 128K',
                provider: 'winky',
                endpoint: '/v1/chat/completions',
                modelName: 'moonshot-v1-128k',
                enabled: false,
                order: 2
            }
        ]
    },
    {
        id: '4',
        name: 'DeepSeek',
        description: '深度求索大模型，支持代码生成与推理任务',
        icon: 'heroicons:cube-transparent',
        iconColor: '#0891b2',
        iconBgColor: 'linear-gradient(to bottom right, #cffafe, #ecfeff)',
        apiKey: 'sk-deepseek-jkl012mno345',
        status: 'configuring',
        routes: [
            {
                id: '4-1',
                name: 'DeepSeek Chat',
                provider: 'winky',
                endpoint: '/v1/chat/completions',
                modelName: 'deepseek-chat',
                enabled: true,
                order: 0
            },
            {
                id: '4-2',
                name: 'DeepSeek 推理',
                provider: 'winky',
                endpoint: '/v1/chat/completions',
                modelName: 'deepseek-reasoner',
                enabled: false,
                order: 1
            }
        ]
    }
];

// 供应商密钥模拟数据（使用 ApiProviderKey 类型）
import type { ApiProviderKey } from './types';

export const mockApiProviderKeys: ApiProviderKey[] = [
    {
        id: 1,
        user_id: 'mock_user',
        name: 'my-openai-key',
        status: 1,
        created_at: '2026-02-20T10:00:00Z'
    },
    {
        id: 2,
        user_id: 'mock_user',
        name: 'my-anthropic-key',
        status: 1,
        created_at: '2026-02-25T14:30:00Z'
    }
];

// 兼容旧的 mockProviderKeys（保留向后兼容）
export const mockProviderKeys: ProviderKey[] = [
    {
        id: '1',
        name: 'Winky API Key',
        key: 'sk-winky-************************'
    }
];

// 请求统计模拟数据
export const mockRequestStats: StatCard[] = [
    {
        icon: 'heroicons:chart-bar',
        iconColor: 'blue',
        value: '1,234,567',
        label: '总请求数',
        trend: { type: 'up', value: '+12.5%' }
    },
    {
        icon: 'heroicons:check-circle',
        iconColor: 'green',
        value: '1,228,432',
        label: '成功请求',
        trend: { type: 'up', value: '+8.3%' }
    },
    {
        icon: 'heroicons:x-circle',
        iconColor: 'red',
        value: '6,135',
        label: '异常请求',
        trend: { type: 'down', value: '-2.1%' }
    }
];

// 用量统计模拟数据
export const mockUsageStats: StatCard[] = [
    {
        icon: 'heroicons:cube',
        iconColor: 'purple',
        value: '89.7M',
        label: '总用量 (Tokens)'
    },
    {
        icon: 'heroicons:calendar',
        iconColor: 'orange',
        value: '12.3M',
        label: '近一个月用量 (Tokens)',
        trend: { type: 'up', value: '+15.2%' }
    },
    {
        icon: 'heroicons:clock',
        iconColor: 'cyan',
        value: '456K',
        label: '今日用量 (Tokens)',
        trend: { type: 'up', value: '+23.8%' }
    }
];

// 按工具分类使用量模拟数据
export const mockToolUsageData: ToolUsageData[] = [
    {
        id: '1',
        name: 'Claude Assistant',
        description: '智能对话助手',
        icon: 'simple-icons:anthropic',
        iconBgColor: 'linear-gradient(135deg, #d4a574 0%, #c49660 100%)',
        routeCount: 3,
        requestCount: 523456,
        tokenCount: '45.2M',
        percentage: 65,
        routes: [
            { id: '1-1', name: 'Claude Sonnet 主路由', endpoint: '/v1/messages', modelName: 'claude-sonnet-4-20250514', requestCount: 312456, isActive: true },
            { id: '1-2', name: 'Claude Opus 备用', endpoint: '/v1/messages', modelName: 'claude-opus-4-20250514', requestCount: 156234, isActive: false },
            { id: '1-3', name: 'Claude Haiku 快速', endpoint: '/v1/messages', modelName: 'claude-3-5-haiku-20241022', requestCount: 54766, isActive: false }
        ]
    },
    {
        id: '2',
        name: 'OpenAI GPT',
        description: '通用大语言模型',
        icon: 'simple-icons:openai',
        iconBgColor: 'linear-gradient(135deg, #10a37f 0%, #0d8a6a 100%)',
        routeCount: 4,
        requestCount: 398765,
        tokenCount: '32.8M',
        percentage: 35,
        routes: [
            { id: '2-1', name: 'GPT-4o 主路由', endpoint: '/v1/responses', modelName: 'gpt-4o', requestCount: 189432, isActive: true },
            { id: '2-2', name: 'GPT-4o Chat', endpoint: '/v1/chat/completions', modelName: 'gpt-4o', requestCount: 124567, isActive: true },
            { id: '2-3', name: 'GPT-4o-mini 轻量', endpoint: '/v1/responses', modelName: 'gpt-4o-mini', requestCount: 56234, isActive: false },
            { id: '2-4', name: 'GPT-4 Turbo', endpoint: '/v1/chat/completions', modelName: 'gpt-4-turbo', requestCount: 28532, isActive: false }
        ]
    }
];

// 按路由分类使用量模拟数据
export const mockRouteTypeUsage: RouteTypeUsage[] = [
    { name: '/v1/messages', path: 'Claude Messages API', description: 'Claude Messages API', colorClass: 'messages', count: 523456 },
    { name: '/v1/chat/completions', path: 'OpenAI Chat API', description: 'OpenAI Chat API', colorClass: 'chat', count: 398765 },
    { name: '/v1/responses', path: 'OpenAI Responses API', description: 'OpenAI Responses API', colorClass: 'responses', count: 245666 },
    { name: '/v1/embeddings', path: 'Embeddings API', description: 'Embeddings API', colorClass: 'embeddings', count: 66680 }
];
