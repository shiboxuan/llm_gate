/**
 * LLM Gate 新手引导组件
 * 重构版本 - 使用 Ant Design Tour 组件实现分步引导
 * 特点：白色主题弹窗，优化蒙版透明度，正确聚焦添加工具按钮
 */
import React, {useState, useEffect, useCallback, forwardRef, useImperativeHandle} from 'react';
import {Tour, Button, message} from 'antd';
import type {TourProps} from 'antd';
import {Icon} from '@iconify/react';
import {CopyOutlined, CheckOutlined} from '@ant-design/icons';
import {copyToClipboard} from '@/utils/copyToClipboard';
import {RUNTIME_CONFIG} from '@/config/runtime';
import './index.less';

// Backend API base URL, 由后端运行时配置注入（仅用于新手引导展示）
const API_BASE_URL = RUNTIME_CONFIG.apiBaseUrl;

// localStorage key
const GUIDE_COMPLETED_KEY = 'llm_gate_guide_completed';

// 引导步骤的 ref 类型
export interface GuideTourRefs {
    welcomeRef: React.RefObject<HTMLElement | null>;
    providerKeysNavRef: React.RefObject<HTMLElement | null>;
    toolsNavRef: React.RefObject<HTMLElement | null>;
    addToolBtnRef: React.RefObject<HTMLElement | null>;
    statsNavRef: React.RefObject<HTMLElement | null>;
}

interface GuideTourProps {
    refs: GuideTourRefs;
    onTabChange?: (tab: string) => void;
}

export interface GuideTourHandle {
    startTour: () => void;
    isFirstVisit: () => boolean;
}

/**
 * API 地址复制组件
 */
const ApiUrlCopyBox: React.FC = () => {
    const [copied, setCopied] = useState(false);

    const handleCopy = async () => {
        try {
            await copyToClipboard(API_BASE_URL);
            setCopied(true);
            message.success('已复制到剪贴板');
            setTimeout(() => setCopied(false), 2000);
        } catch {
            message.error('复制失败');
        }
    };

    return (
        <div className='api-url-box'>
            <div className='api-url-label'>
                <Icon icon='heroicons:server' />
                <span>后端 API 地址</span>
            </div>
            <div className='api-url-content'>
                <code className='api-url-text'>{API_BASE_URL}</code>
                <Button type='text' size='small' icon={copied ? <CheckOutlined /> : <CopyOutlined />} onClick={handleCopy}>
                    {copied ? '已复制' : '复制'}
                </Button>
            </div>
            <p className='api-url-hint'>在 Cline / Cursor 等客户端中配置此地址作为 API Endpoint</p>
        </div>
    );
};

const GuideTour = forwardRef<GuideTourHandle, GuideTourProps>(({refs, onTabChange}, ref) => {
    const [open, setOpen] = useState(false);
    const [currentStep, setCurrentStep] = useState(0);

    // 检查是否首次访问
    const isFirstVisit = useCallback(() => {
        const completed = localStorage.getItem(GUIDE_COMPLETED_KEY);
        return completed !== 'true';
    }, []);

    // 标记引导完成
    const markAsCompleted = useCallback(() => {
        localStorage.setItem(GUIDE_COMPLETED_KEY, 'true');
    }, []);

    // 开始引导
    const startTour = useCallback(() => {
        setCurrentStep(0);
        setOpen(true);
    }, []);

    // 暴露方法给父组件
    useImperativeHandle(ref, () => ({
        startTour,
        isFirstVisit
    }));

    // 首次访问自动开始引导
    useEffect(() => {
        if (isFirstVisit()) {
            // 延迟启动，确保页面完全加载
            const timer = setTimeout(() => {
                startTour();
            }, 1000);
            return () => clearTimeout(timer);
        }
    }, [isFirstVisit, startTour]);

    // 引导步骤配置
    const steps: TourProps['steps'] = [
        {
            title: (
                <div className='tour-step-title'>
                    <Icon icon='heroicons:sparkles' className='tour-title-icon' />
                    <span>欢迎使用 LLM Gate</span>
                </div>
            ),
            description: (
                <div className='tour-step-content'>
                    <p>
                        LLM Gate 是一个统一的 LLM 路由管理平台，帮助您：
                    </p>
                    <ul className='feature-list'>
                        <li>
                            <Icon icon='heroicons:check-circle' className='check-icon' />
                            集中管理多个 AI 模型的 API 调用
                        </li>
                        <li>
                            <Icon icon='heroicons:check-circle' className='check-icon' />
                            为 Cline、ClaudeCode 等工具提供统一的 API 入口
                        </li>
                        <li>
                            <Icon icon='heroicons:check-circle' className='check-icon' />
                            跟踪和统计 Token 使用量
                        </li>
                    </ul>
                    <ApiUrlCopyBox />
                </div>
            ),
            target: null, // 居中显示，不指定目标元素
            placement: 'center'
        },
        {
            title: (
                <div className='tour-step-title'>
                    <Icon icon='heroicons:key' className='tour-title-icon' />
                    <span>第一步：配置供应商密钥</span>
                </div>
            ),
            description: (
                <div className='tour-step-content'>
                    <p>在使用之前，您需要先配置 <strong>供应商密钥</strong>。</p>
                    <div className='info-box'>
                        <Icon icon='heroicons:information-circle' className='info-icon' />
                        <div>
                            <p>供应商密钥是您从 LLM 服务商（如 OpenAI、Anthropic、Azure 等）获取的 API Key。</p>
                            <p>这些 Key 将被安全加密存储，用于实际调用 AI 模型。</p>
                        </div>
                    </div>
                </div>
            ),
            target: refs.providerKeysNavRef.current ?? undefined,
            placement: 'right'
        },
        {
            title: (
                <div className='tour-step-title'>
                    <Icon icon='heroicons:squares-2x2' className='tour-title-icon' />
                    <span>第二步：创建工具</span>
                </div>
            ),
            description: (
                <div className='tour-step-content'>
                    <p><strong>工具</strong> 是一个独立的 LLM 服务配置单元。</p>
                    <div className='info-box'>
                        <Icon icon='heroicons:light-bulb' className='info-icon warning' />
                        <div>
                            <p>每个工具会生成一个唯一的 <strong>API Key</strong>，您将使用这个 Key 在客户端（如 Cline、ClaudeCode）中进行配置。</p>
                        </div>
                    </div>
                    <div className='example-box'>
                        <p className='example-title'>客户端配置示例：</p>
                        <code className='example-code'>
                            API Endpoint: {API_BASE_URL}
                            <br />
                            API Key: sk-llmgate-xxxxxxxx
                        </code>
                    </div>
                </div>
            ),
            target: refs.toolsNavRef.current ?? undefined,
            placement: 'right'
        },
        {
            title: (
                <div className='tour-step-title'>
                    <Icon icon='heroicons:plus-circle' className='tour-title-icon' />
                    <span>添加您的第一个工具</span>
                </div>
            ),
            description: (
                <div className='tour-step-content'>
                    <p>点击此按钮创建新工具。</p>
                    <div className='steps-box'>
                        <p className='steps-title'>创建工具后，您需要：</p>
                        <ol className='steps-list'>
                            <li>为工具添加 <strong>路由</strong>（配置使用哪个模型）</li>
                            <li><strong>激活</strong> 一个路由（工具需要有激活的路由才能工作）</li>
                            <li>复制工具的 <strong>API Key</strong> 到您的客户端</li>
                        </ol>
                    </div>
                </div>
            ),
            target: refs.addToolBtnRef.current ?? undefined,
            placement: 'bottomLeft'
        },
        {
            title: (
                <div className='tour-step-title'>
                    <Icon icon='heroicons:chart-bar' className='tour-title-icon' />
                    <span>查看使用统计</span>
                </div>
            ),
            description: (
                <div className='tour-step-content'>
                    <p>在统计页面，您可以查看：</p>
                    <ul className='feature-list'>
                        <li>
                            <Icon icon='heroicons:check-circle' className='check-icon' />
                            请求总数和成功率
                        </li>
                        <li>
                            <Icon icon='heroicons:check-circle' className='check-icon' />
                            Token 使用量统计
                        </li>
                        <li>
                            <Icon icon='heroicons:check-circle' className='check-icon' />
                            各工具的用量分布
                        </li>
                    </ul>
                </div>
            ),
            target: refs.statsNavRef.current ?? undefined,
            placement: 'right'
        },
        {
            title: (
                <div className='tour-step-title'>
                    <Icon icon='heroicons:rocket-launch' className='tour-title-icon' />
                    <span>开始使用吧！</span>
                </div>
            ),
            description: (
                <div className='tour-step-content'>
                    <p>恭喜！您已经了解了 LLM Gate 的基本功能。</p>
                    <div className='summary-box'>
                        <p className='summary-title'>快速回顾：</p>
                        <ol className='summary-list'>
                            <li>在「供应商密钥管理」添加您的 API Key</li>
                            <li>在「工具管理」创建工具并配置路由</li>
                            <li>复制工具的 API Key 到 Cline/ClaudeCode 中使用</li>
                        </ol>
                    </div>
                    <ApiUrlCopyBox />
                    <p className='final-hint'>
                        <Icon icon='heroicons:information-circle' />
                        您可以随时点击顶部的「新手引导」按钮重新查看此引导。
                    </p>
                </div>
            ),
            target: null, // 居中显示，不指定目标元素
            placement: 'center'
        }
    ];

    // 处理步骤变化
    const handleStepChange = (current: number) => {
        setCurrentStep(current);
    };

    // 处理关闭
    const handleClose = () => {
        setOpen(false);
        markAsCompleted();
    };

    // 处理完成
    const handleFinish = () => {
        setOpen(false);
        markAsCompleted();
        message.success('引导完成！开始您的 LLM Gate 之旅吧 🚀');
    };

    return (
        <Tour
            open={open}
            onClose={handleClose}
            onFinish={handleFinish}
            steps={steps}
            current={currentStep}
            onChange={handleStepChange}
            mask={{
                style: {
                    boxShadow: 'inset 0 0 15px rgba(0, 0, 0, 0.1)'
                },
                color: 'rgba(0, 0, 0, 0.45)' // 深色半透明蒙版
            }}
            type='default'
            indicatorsRender={(current, total) => (
                <span className='tour-indicators'>
                    {current + 1} / {total}
                </span>
            )}
        />
    );
});

GuideTour.displayName = 'GuideTour';

export default GuideTour;
