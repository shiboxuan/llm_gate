/**
 * LLM Gate management dashboard - main page.
 *
 * Auth: the authenticated user is passed in as a prop from the ProtectedRoute.
 * Theme: managed via the global themeStore (zustand).
 */
import React, {useState, useEffect, useCallback, useRef} from 'react';
import {Menu, Spin, message, Tooltip, Button, Dropdown} from 'antd';
import {Icon} from '@iconify/react';
import {QuestionCircleOutlined, ReadOutlined, MoonOutlined, SunOutlined, LogoutOutlined} from '@ant-design/icons';
import {useNavigate} from 'react-router-dom';
import themeStore from '@/store';
import {healthCheck, getProviderKeys, clearToken} from '@/api';
import Layout from '@/components/Layout';
import ToolManagement from '@/components/ToolManagement';
import ProviderKeyManagement from '@/components/ProviderKeyManagement';
import UsageStatistics from '@/components/UsageStatistics';
import GuideTour, {type GuideTourHandle, type GuideTourRefs} from '@/components/GuideTour';
import ModelDetector from '@/components/ModelDetector';
import type {ApiProviderKey} from '@/types';
import {TabType, TAB_TITLES, type User, type HealthStatus} from '@/types';
import './index.less';

interface HomeProps {
    user: User;
}

const Home: React.FC<HomeProps> = ({user}) => {
    const navigate = useNavigate();

    // Tab state
    const [activeTab, setActiveTab] = useState<TabType>('tools');

    // Theme
    const {mode, toggleMode} = themeStore();
    const isDarkMode = mode === 'dark';

    // Guide tour refs
    const guideTourRef = useRef<GuideTourHandle>(null);
    const guideTourRefs: GuideTourRefs = {
        welcomeRef: useRef<HTMLElement>(null),
        providerKeysNavRef: useRef<HTMLElement>(null),
        toolsNavRef: useRef<HTMLElement>(null),
        addToolBtnRef: useRef<HTMLElement>(null),
        statsNavRef: useRef<HTMLElement>(null)
    };

    const handleTourTabChange = useCallback((tab: string) => {
        setActiveTab(tab as TabType);
    }, []);

    const handleStartTour = useCallback(() => {
        guideTourRef.current?.startTour();
    }, []);

    // Model detector state
    const [detectorModalVisible, setDetectorModalVisible] = useState(false);
    const [providerKeys, setProviderKeys] = useState<ApiProviderKey[]>([]);

    // Health check state
    const [healthStatus, setHealthStatus] = useState<HealthStatus>({
        isHealthy: false,
        appName: '',
        appEnv: '',
        latency: 0,
        lastChecked: new Date(),
        loading: true,
        error: null
    });

    // ========== Health check ==========
    const performHealthCheck = useCallback(async () => {
        setHealthStatus((prev) => ({...prev, loading: true, error: null}));
        const startTime = Date.now();

        try {
            const response = await healthCheck();
            const latency = Date.now() - startTime;
            setHealthStatus({
                isHealthy: response.data.status === 'healthy',
                appName: response.data.app_name,
                appEnv: response.data.app_env,
                latency,
                lastChecked: new Date(),
                loading: false,
                error: null
            });
        } catch {
            const latency = Date.now() - startTime;
            setHealthStatus({
                isHealthy: false,
                appName: '',
                appEnv: '',
                latency,
                lastChecked: new Date(),
                loading: false,
                error: '服务连接失败'
            });
        }
    }, []);

    useEffect(() => {
        performHealthCheck();
    }, [performHealthCheck]);

    // Fetch provider keys (for model detector)
    const fetchProviderKeys = useCallback(async () => {
        try {
            const response = await getProviderKeys();
            setProviderKeys(response.data);
        } catch {
            console.error('获取 Provider Keys 失败');
        }
    }, []);

    const handleOpenDetector = useCallback(async () => {
        if (providerKeys.length === 0) {
            await fetchProviderKeys();
        }
        setDetectorModalVisible(true);
    }, [providerKeys.length, fetchProviderKeys]);

    // Logout
    const handleLogout = useCallback(() => {
        clearToken();
        message.success('已退出登录');
        navigate('/login', {replace: true});
    }, [navigate]);

    const renderContent = () => {
        switch (activeTab) {
            case 'tools':
                return <ToolManagement addToolBtnRef={guideTourRefs.addToolBtnRef} />;
            case 'interface-keys':
                return <ProviderKeyManagement />;
            case 'usage':
                return <UsageStatistics />;
            default:
                return <ToolManagement addToolBtnRef={guideTourRefs.addToolBtnRef} />;
        }
    };

    // Menu items with guide tour refs
    const menuItemsWithRef = [
        {
            key: 'tools',
            icon: <Icon icon='heroicons:squares-2x2' />,
            label: <span ref={guideTourRefs.toolsNavRef as React.RefObject<HTMLSpanElement>}>工具管理</span>
        },
        {
            key: 'interface-keys',
            icon: <Icon icon='heroicons:key' />,
            label: <span ref={guideTourRefs.providerKeysNavRef as React.RefObject<HTMLSpanElement>}>供应商密钥管理</span>
        },
        {
            key: 'usage',
            icon: <Icon icon='heroicons:chart-bar' />,
            label: <span ref={guideTourRefs.statsNavRef as React.RefObject<HTMLSpanElement>}>统计</span>
        }
    ];

    return (
        <Layout>
            <div
                className={`llm-gate-container ${isDarkMode ? 'llm-dark' : ''}`}
                ref={guideTourRefs.welcomeRef as React.RefObject<HTMLDivElement>}
            >
                {/* Guide tour */}
                <GuideTour ref={guideTourRef} refs={guideTourRefs} onTabChange={handleTourTabChange} />

                {/* Sidebar */}
                <aside className='llm-gate-sidebar'>
                    <div className='sidebar-header'>
                        <div className='logo'>
                            <Icon icon='heroicons:bolt-20-solid' className='logo-icon' />
                            <span className='logo-text'>LLM Gate</span>
                        </div>
                    </div>

                    <Menu
                        mode='inline'
                        selectedKeys={[activeTab]}
                        onClick={({key}) => setActiveTab(key as TabType)}
                        items={menuItemsWithRef}
                        className='sidebar-menu'
                    />

                    <div className='sidebar-footer'>
                        <Tooltip
                            title={
                                healthStatus.loading
                                    ? '检查中...'
                                    : `上次检查: ${healthStatus.lastChecked.toLocaleTimeString()}`
                            }
                            placement='top'
                        >
                            <div
                                className={`status-card ${healthStatus.isHealthy ? '' : 'error'}`}
                                onClick={performHealthCheck}
                                style={{cursor: 'pointer'}}
                            >
                                <div className='status-header'>
                                    <p className='status-label'>系统状态</p>
                                    {healthStatus.latency > 0 && !healthStatus.loading && (
                                        <span className='status-latency'>{healthStatus.latency}ms</span>
                                    )}
                                </div>
                                <div className='status-content'>
                                    {healthStatus.loading ? (
                                        <>
                                            <span className='status-text'>检查中...</span>
                                            <Spin size='small' />
                                        </>
                                    ) : healthStatus.error ? (
                                        <>
                                            <span className='status-text'>服务异常</span>
                                            <span className='status-dot error'></span>
                                        </>
                                    ) : (
                                        <>
                                            <span className='status-text'>服务正常</span>
                                            <span className='status-dot'></span>
                                        </>
                                    )}
                                </div>
                                {healthStatus.appName && !healthStatus.loading && (
                                    <p className='status-app-name'>{healthStatus.appName}</p>
                                )}
                            </div>
                        </Tooltip>
                    </div>
                </aside>

                {/* Main content */}
                <main className='llm-gate-main'>
                    {/* Header */}
                    <header className='main-header'>
                        <div className='header-title'>
                            {TAB_TITLES[activeTab]}
                            {activeTab === 'tools' && (
                                <Tooltip
                                    title={
                                        <div style={{maxWidth: 280}}>
                                            <p style={{fontWeight: 600, marginBottom: 8}}>什么是工具？</p>
                                            <p style={{marginBottom: 8}}>
                                                工具是一个独立的 LLM 服务配置单元，每个工具会生成唯一的 API
                                                Key，供客户端（如 Cline、Cursor）连接使用。
                                            </p>
                                            <p style={{marginBottom: 0}}>
                                                您可以为每个工具配置多个路由，实现不同模型的切换。激活的路由决定了该工具当前使用的模型。
                                            </p>
                                        </div>
                                    }
                                    placement='bottom'
                                    overlayStyle={{maxWidth: 320}}
                                >
                                    <QuestionCircleOutlined className='header-help-icon' />
                                </Tooltip>
                            )}
                        </div>
                        <div className='header-actions'>
                            {/* Model detector */}
                            <Tooltip title='模型探测器'>
                                <Button
                                    type='text'
                                    icon={<Icon icon='heroicons:signal' />}
                                    onClick={handleOpenDetector}
                                    className='detector-btn'
                                />
                            </Tooltip>
                            <div className='divider'></div>
                            {/* Theme toggle */}
                            <Tooltip title={isDarkMode ? '切换到亮色模式' : '切换到深色模式'}>
                                <Button
                                    type='text'
                                    icon={isDarkMode ? <SunOutlined /> : <MoonOutlined />}
                                    onClick={toggleMode}
                                    className='theme-toggle-btn'
                                />
                            </Tooltip>
                            <div className='divider'></div>
                            {/* Guide tour */}
                            <Tooltip title='查看新手引导'>
                                <Button
                                    type='text'
                                    icon={<ReadOutlined />}
                                    onClick={handleStartTour}
                                    className='guide-tour-btn'
                                >
                                    新手引导
                                </Button>
                            </Tooltip>
                            <div className='divider'></div>
                            <div className='notification-btn'>
                                <Icon icon='heroicons:bell' />
                            </div>
                            <div className='divider'></div>

                            {/* User info + logout */}
                            <Dropdown
                                menu={{
                                    items: [
                                        {
                                            key: 'logout',
                                            icon: <LogoutOutlined />,
                                            label: '退出登录',
                                            onClick: handleLogout
                                        }
                                    ]
                                }}
                            >
                                <div className='user-info' style={{cursor: 'pointer'}}>
                                    <div className='user-details'>
                                        <p className='user-name'>{user.username}</p>
                                        <p className='user-role'>{user.email || (user.is_admin ? 'ADMINISTRATOR' : 'USER')}</p>
                                    </div>
                                    <div className='user-avatar'>{user.username?.charAt(0).toUpperCase() || 'U'}</div>
                                </div>
                            </Dropdown>
                        </div>
                    </header>

                    {/* Content */}
                    <div className='main-content'>{renderContent()}</div>
                </main>

                {/* Model detector modal */}
                <ModelDetector
                    visible={detectorModalVisible}
                    onClose={() => setDetectorModalVisible(false)}
                    providerKeys={providerKeys}
                />
            </div>
        </Layout>
    );
};

export default Home;
