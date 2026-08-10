/**
 * 工具管理模块
 */
import React, {useState, useEffect, useCallback} from 'react';
import {Button, message, Spin, Empty, Result, Modal, Form, Input, Tag, Space} from 'antd';
import {PlusOutlined, ReloadOutlined, ExclamationCircleOutlined, CopyOutlined, SearchOutlined, ApiOutlined, CheckCircleOutlined, CloseCircleOutlined, LoadingOutlined} from '@ant-design/icons';
import {Icon} from '@iconify/react';
import ToolCard from '../ToolCard';
import LLMGateSelect from '../LLMGateSelect';
import {ToolConfig, RouteConfig, ErrorCode, ApiProviderKey, API_TYPE_OPTIONS, ApiType} from '../../types';
import {
    getTools,
    createTool,
    updateTool,
    deleteTool,
    regenerateToolKey,
    addRoute,
    updateRoute,
    deleteRoute,
    activateRoute,
    deactivateRoute,
    getProviderKeys,
    reorderRoutes,
    testConnection
} from '@/api';
import {getToolIcon} from '../../utils/iconMapping';
import {copyToClipboard} from '@/utils/copyToClipboard';
import './index.less';

interface ToolManagementProps {
    addToolBtnRef?: React.RefObject<HTMLElement | null>;
}

const ToolManagement: React.FC<ToolManagementProps> = ({addToolBtnRef}) => {
    // 状态管理
    const [tools, setTools] = useState<ToolConfig[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // 创建工具弹窗状态
    const [createModalVisible, setCreateModalVisible] = useState(false);
    const [createLoading, setCreateLoading] = useState(false);
    const [createForm] = Form.useForm();

    // 编辑工具弹窗状态
    const [editModalVisible, setEditModalVisible] = useState(false);
    const [editLoading, setEditLoading] = useState(false);
    const [editingTool, setEditingTool] = useState<ToolConfig | null>(null);
    const [editForm] = Form.useForm();

    // API Key展示弹窗状态
    const [apiKeyModalVisible, setApiKeyModalVisible] = useState(false);
    const [newApiKey, setNewApiKey] = useState('');
    const [isRegeneratedKey, setIsRegeneratedKey] = useState(false);

    // 添加路由弹窗状态
    const [addRouteModalVisible, setAddRouteModalVisible] = useState(false);
    const [addRouteLoading, setAddRouteLoading] = useState(false);
    const [addRouteToolId, setAddRouteToolId] = useState<string | null>(null);
    const [addRouteForm] = Form.useForm();

    // 测试连通性状态
    const [testConnectionStatus, setTestConnectionStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
    const [testConnectionResult, setTestConnectionResult] = useState<{latency?: number; message?: string; attemptedUrls?: string[]}>({});

    // Provider Keys 缓存状态
    const [providerKeys, setProviderKeys] = useState<ApiProviderKey[]>([]);
    const [providerKeysLoaded, setProviderKeysLoaded] = useState(false);

    // 现有路由选择弹窗状态
    const [existingRoutesModalVisible, setExistingRoutesModalVisible] = useState(false);
    const [existingRoutesSearchText, setExistingRoutesSearchText] = useState('');

    // 拖拽复制路由确认弹窗状态
    const [dragCopyModalVisible, setDragCopyModalVisible] = useState(false);
    const [dragCopyData, setDragCopyData] = useState<{
        sourceRoute: RouteConfig;
        sourceToolId: string;
        sourceToolName: string;
        targetToolId: string;
        targetToolName: string;
    } | null>(null);
    const [dragCopyLoading, setDragCopyLoading] = useState(false);

    // 数据格式转换函数
    const convertToolToConfig = (tool: any): ToolConfig => {
        // 根据工具名称获取对应的图标配置
        const iconInfo = getToolIcon(tool.name);

        return {
            id: String(tool.id),
            name: tool.name,
            description: tool.description || '',
            icon: iconInfo.icon,
            iconColor: iconInfo.iconColor,
            iconBgColor: iconInfo.iconBgColor,
            apiKey: '',
            status: tool.status === 1 ? 'running' : 'stopped',
            apiType: tool.api_type || 'openai_chat', // v2.0 新增：Tool 级别的 API 类型
            routes: (tool.routes || []).map((r: any) => ({
                id: r.name,
                name: r.name,
                provider: r.provider_key_name || r.provider,
                endpoint: r.base_url || r.api_path,
                modelName: r.model,
                enabled: r.is_active,
                order: r.order ?? 0 // v2.1 新增：保留排序字段
            }))
        };
    };

    // 获取工具列表
    const fetchTools = async () => {
        try {
            setLoading(true);
            setError(null);
            const response = await getTools();
            // 转换API数据格式为前端格式
            const toolConfigs = response.data.map(convertToolToConfig);
            setTools(toolConfigs);
        } catch {
            setError('获取工具列表失败');
            message.error('获取工具列表失败');
        } finally {
            setLoading(false);
        }
    };

    // 获取 Provider Keys
    const fetchProviderKeys = useCallback(async () => {
        try {
            const response = await getProviderKeys();
            setProviderKeys(response.data);
            setProviderKeysLoaded(true);
        } catch {
            console.error('获取 Provider Keys 失败');
        }
    }, []);

    // 刷新 Provider Keys 缓存
    const refreshProviderKeys = useCallback(async () => {
        setProviderKeysLoaded(false);
        await fetchProviderKeys();
    }, [fetchProviderKeys]);

    useEffect(() => {
        fetchTools();
        fetchProviderKeys();
    }, []);

    // 打开创建弹窗
    const handleOpenCreateModal = () => {
        createForm.resetFields();
        setCreateModalVisible(true);
    };

    // 创建工具
    const handleCreateTool = async () => {
        try {
            const values = await createForm.validateFields();
            setCreateLoading(true);

            const response = await createTool({
                name: values.name.trim(),
                description: values.description?.trim() || undefined,
                api_type: values.api_type || 'openai_chat'
            });
            await fetchTools();
            setNewApiKey(response.data.api_key);
            setIsRegeneratedKey(false);
            setCreateModalVisible(false);
            setApiKeyModalVisible(true);
            message.success('工具创建成功');
        } catch (err: any) {
            if (err.response?.data?.code === ErrorCode.TOOL_NAME_DUPLICATE) {
                createForm.setFields([{name: 'name', errors: ['工具名称已存在，请使用其他名称']}]);
            } else if (!err.errorFields) {
                message.error('创建工具失败');
            }
        } finally {
            setCreateLoading(false);
        }
    };

    // 打开编辑弹窗
    const handleEditTool = (tool: ToolConfig) => {
        setEditingTool(tool);
        editForm.setFieldsValue({
            name: tool.name,
            description: tool.description,
            api_type: tool.apiType || 'openai_chat'
        });
        setEditModalVisible(true);
    };

    // 更新工具
    const handleUpdateTool = async () => {
        if (!editingTool) return;

        try {
            const values = await editForm.validateFields();
            setEditLoading(true);

            await updateTool(Number(editingTool.id), {
                name: values.name.trim(),
                description: values.description?.trim() || undefined,
                api_type: values.api_type
            });
            await fetchTools();
            setEditModalVisible(false);
            message.success('工具更新成功');
        } catch (err: any) {
            if (err.response?.data?.code === ErrorCode.TOOL_NAME_DUPLICATE) {
                editForm.setFields([{name: 'name', errors: ['工具名称已存在，请使用其他名称']}]);
            } else if (!err.errorFields) {
                message.error('更新工具失败');
            }
        } finally {
            setEditLoading(false);
        }
    };

    // 删除工具
    const handleDeleteTool = async (toolId: string) => {
        try {
            await deleteTool(Number(toolId));
            await fetchTools();
            message.success('工具删除成功');
        } catch {
            message.error('删除工具失败');
        }
    };

    // 重新生成Key
    const handleRegenerateKey = async (toolId: string) => {
        Modal.confirm({
            title: '确定要重新生成 API Key 吗？',
            icon: <ExclamationCircleOutlined />,
            content: (
                <div>
                    <p>重新生成后，旧的 Key 将立即失效。</p>
                    <p>使用旧 Key 的客户端需要更新配置。</p>
                </div>
            ),
            okText: '确定重新生成',
            cancelText: '取消',
            onOk: async () => {
                try {
                    const response = await regenerateToolKey(Number(toolId));
                    setNewApiKey(response.data.api_key);
                    setIsRegeneratedKey(true);
                    setApiKeyModalVisible(true);
                } catch {
                    message.error('重新生成Key失败');
                }
            }
        });
    };

    // 复制API Key
    const handleCopyApiKey = async () => {
        try {
            await copyToClipboard(newApiKey);
            message.success('已复制到剪贴板');
        } catch {
            message.error('复制失败，请手动复制');
        }
    };

    // ==================== 路由相关操作 ====================

    // 打开添加路由弹窗
    const handleAddRoute = async (toolId: string) => {
        // 先确保 Provider Keys 已加载
        if (!providerKeysLoaded) {
            await fetchProviderKeys();
        }

        // 检查是否有可用的 Provider Keys
        if (providerKeys.length === 0) {
            message.warning('请先到「供应商密钥管理」中添加 Key');
            return;
        }

        setAddRouteToolId(toolId);
        addRouteForm.resetFields();
        setAddRouteModalVisible(true);
    };

    // 提交添加路由
    const handleSubmitAddRoute = async () => {
        if (!addRouteToolId) return;

        try {
            const values = await addRouteForm.validateFields();
            setAddRouteLoading(true);

            await addRoute(Number(addRouteToolId), {
                name: values.name.trim(),
                provider: '',
                base_url: values.base_url.trim(),
                model: values.model.trim(),
                provider_key_name: values.provider_key_name,
                api_path: '',
                set_active: false
            });
            await fetchTools();
            setAddRouteModalVisible(false);
            message.success('路由添加成功');
        } catch (err: any) {
            if (err.response?.data?.code === ErrorCode.ROUTE_NAME_DUPLICATE) {
                addRouteForm.setFields([{name: 'name', errors: ['路由名称已存在']}]);
            } else if (!err.errorFields) {
                message.error('添加路由失败');
            }
        } finally {
            setAddRouteLoading(false);
        }
    };

    // 测试路由连通性
    const handleTestConnection = async () => {
        // 验证必填字段
        const values = addRouteForm.getFieldsValue();
        if (!values.base_url || !values.model || !values.provider_key_name) {
            message.warning('请先填写完整的路由配置');
            return;
        }

        // 获取当前工具的 api_type
        const currentTool = tools.find((t) => t.id === addRouteToolId);
        const apiType = currentTool?.apiType || 'openai_chat';

        setTestConnectionStatus('loading');
        setTestConnectionResult({});

        try {
            const response = await testConnection({
                api_type: apiType,
                base_url: values.base_url.trim(),
                model: values.model.trim(),
                provider_key_name: values.provider_key_name
            });

            if (response.data.success) {
                setTestConnectionStatus('success');
                setTestConnectionResult({latency: response.data.latency_ms});
            } else {
                setTestConnectionStatus('error');
                setTestConnectionResult({message: response.data.message, attemptedUrls: response.data.attempted_urls});
            }
        } catch (error: any) {
            setTestConnectionStatus('error');
            setTestConnectionResult({message: error.response?.data?.message || '连接失败'});
        }

        // 3秒后恢复默认状态
        setTimeout(() => {
            setTestConnectionStatus('idle');
            setTestConnectionResult({});
        }, 3000);
    };

    // 关闭添加路由弹窗并重置状态
    const handleCloseAddRouteModal = () => {
        setAddRouteModalVisible(false);
        setTestConnectionStatus('idle');
        setTestConnectionResult({});
    };

    // 删除路由
    const handleDeleteRoute = async (toolId: string, routeId: string) => {
        // 检查是否为激活路由
        const tool = tools.find((t) => t.id === toolId);
        const route = tool?.routes.find((r) => r.id === routeId);

        if (route?.enabled) {
            message.warning('不能删除激活中的路由，请先切换到其他路由');
            return;
        }

        try {
            await deleteRoute(Number(toolId), routeId);
            await fetchTools();
            message.success('路由删除成功');
        } catch (err: any) {
            if (err.response?.data?.code === ErrorCode.ROUTE_DELETE_FAILED) {
                message.error('不能删除激活中的路由');
            } else {
                message.error('删除路由失败');
            }
        }
    };

    // 切换激活路由
    const handleToggleRoute = async (toolId: string, routeId: string, enabled: boolean): Promise<void> => {
        if (enabled) {
            // 激活路由
            await activateRoute(Number(toolId), routeId);
            await fetchTools();
            message.success('路由已激活');
        } else {
            // 关闭路由（取消激活）
            await deactivateRoute(Number(toolId));
            await fetchTools();
            message.success('路由已关闭');
        }
    };

    // ==================== 使用现有路由功能 ====================

    // 生成唯一的路由名称（添加后缀避免重复）
    const generateUniqueRouteName = (baseName: string, targetToolId: string): string => {
        const targetTool = tools.find((t) => t.id === targetToolId);
        if (!targetTool) return baseName;

        const existingNames = targetTool.routes.map((r) => r.name);
        let newName = baseName;
        let suffix = 1;

        // 如果名称已存在，添加数字后缀
        while (existingNames.includes(newName)) {
            newName = `${baseName}-copy${suffix > 1 ? suffix : ''}`;
            suffix++;
        }

        return newName;
    };

    // 打开现有路由选择弹窗
    const handleOpenExistingRoutesModal = () => {
        setExistingRoutesSearchText('');
        setExistingRoutesModalVisible(true);
    };

    // 选择现有路由并填充表单
    const handleSelectExistingRoute = (route: RouteConfig, _toolId: string) => {
        if (!addRouteToolId) return;

        // 生成唯一名称
        const uniqueName = generateUniqueRouteName(route.name, addRouteToolId);

        // 填充表单
        addRouteForm.setFieldsValue({
            name: uniqueName,
            provider_key_name: route.provider,
            base_url: route.endpoint,
            model: route.modelName
        });

        // 关闭选择弹窗
        setExistingRoutesModalVisible(false);
        message.success('已填充路由配置，可根据需要修改后保存');
    };

    // 获取所有可选择的路由（所有工具的路由）
    const getAllSelectableRoutes = useCallback(() => {
        const result: Array<{
            tool: ToolConfig;
            routes: RouteConfig[];
        }> = [];

        tools.forEach((tool) => {
            if (tool.routes.length > 0) {
                // 根据搜索文本过滤
                const filteredRoutes = existingRoutesSearchText
                    ? tool.routes.filter(
                          (route) =>
                              route.name.toLowerCase().includes(existingRoutesSearchText.toLowerCase()) ||
                              route.modelName.toLowerCase().includes(existingRoutesSearchText.toLowerCase()) ||
                              route.endpoint.toLowerCase().includes(existingRoutesSearchText.toLowerCase())
                      )
                    : tool.routes;

                if (filteredRoutes.length > 0) {
                    result.push({
                        tool,
                        routes: filteredRoutes
                    });
                }
            }
        });

        return result;
    }, [tools, existingRoutesSearchText]);

    // ==================== 拖拽复制路由功能 ====================

    // 处理拖拽放置（从 ToolCard 接收）- 跨工具复制
    const handleRouteDrop = useCallback(
        (sourceToolId: string, routeId: string, targetToolId: string) => {
            // 获取源工具和路由
            const sourceTool = tools.find((t) => t.id === sourceToolId);
            const sourceRoute = sourceTool?.routes.find((r) => r.id === routeId);
            const targetTool = tools.find((t) => t.id === targetToolId);

            if (!sourceTool || !sourceRoute || !targetTool) {
                message.error('无法获取路由信息');
                return;
            }

            // 如果是同一个工具，不处理（同工具排序由 handleRouteReorder 处理）
            if (sourceToolId === targetToolId) {
                return;
            }

            // 显示确认弹窗
            setDragCopyData({
                sourceRoute,
                sourceToolId,
                sourceToolName: sourceTool.name,
                targetToolId,
                targetToolName: targetTool.name
            });
            setDragCopyModalVisible(true);
        },
        [tools]
    );

    // 处理同工具内路由排序
    const handleRouteReorder = useCallback(
        async (toolId: string, routeId: string, newIndex: number) => {
            const tool = tools.find((t) => t.id === toolId);
            if (!tool) return;

            const routes = [...tool.routes];
            const currentIndex = routes.findIndex((r) => r.id === routeId);

            // 如果位置未变或无效，不处理
            if (currentIndex === -1 || currentIndex === newIndex || newIndex < 0 || newIndex >= routes.length) {
                return;
            }

            // 移动路由到新位置
            const [movedRoute] = routes.splice(currentIndex, 1);
            routes.splice(newIndex, 0, movedRoute);

            // 更新 order 值
            const reorderedRoutes = routes.map((route, index) => ({
                ...route,
                order: index
            }));

            // 生成新的 order 映射
            const orders: Record<string, number> = {};
            reorderedRoutes.forEach((route, index) => {
                orders[route.name] = index;
            });

            // 乐观更新 UI
            const originalTools = [...tools];
            setTools(
                tools.map((t) => {
                    if (t.id === toolId) {
                        return {...t, routes: reorderedRoutes};
                    }
                    return t;
                })
            );

            try {
                await reorderRoutes(Number(toolId), {orders});
            } catch {
                // 失败时回滚
                setTools(originalTools);
                message.error('排序失败，已恢复');
            }
        },
        [tools]
    );

    // 确认拖拽复制路由
    const handleConfirmDragCopy = async () => {
        if (!dragCopyData) return;

        const {sourceRoute, targetToolId} = dragCopyData;

        // 检查 Provider Keys
        if (providerKeys.length === 0) {
            message.warning('请先到「供应商密钥管理」中添加 Key');
            setDragCopyModalVisible(false);
            return;
        }

        // 生成唯一名称
        const uniqueName = generateUniqueRouteName(sourceRoute.name, targetToolId);

        setDragCopyLoading(true);

        try {
            await addRoute(Number(targetToolId), {
                name: uniqueName,
                provider: '',
                base_url: sourceRoute.endpoint,
                model: sourceRoute.modelName,
                provider_key_name: sourceRoute.provider,
                api_path: '',
                set_active: false
            });
            await fetchTools();
            message.success('路由复制成功');
        } catch (err: any) {
            if (err.response?.data?.code === ErrorCode.ROUTE_NAME_DUPLICATE) {
                message.error('路由名称已存在，请重试');
            } else {
                message.error('复制路由失败');
            }
        } finally {
            setDragCopyLoading(false);
            setDragCopyModalVisible(false);
            setDragCopyData(null);
        }
    };

    // 更新路由（供应商Key变更、接口地址、模型名称等）
    const handleUpdateRoute = async (toolId: string, route: RouteConfig, field?: string, value?: string) => {
        // 保存原始数据用于回滚
        const originalTools = [...tools];

        // 先乐观更新 UI
        setTools(
            tools.map((tool) => {
                if (tool.id === toolId) {
                    return {
                        ...tool,
                        routes: tool.routes.map((r) => (r.id === route.id ? route : r))
                    };
                }
                return tool;
            })
        );

        try {
            // 构建更新参数
            const updateData: any = {};
            if (field && value !== undefined) {
                updateData[field] = value;
            } else {
                // 兼容旧的调用方式
                updateData.provider_key_name = route.provider;
            }

            await updateRoute(Number(toolId), route.name, updateData);
            // 刷新数据以确保同步
            await fetchTools();
        } catch {
            // 失败时回滚
            setTools(originalTools);
            message.error('更新路由失败，已回滚');
            throw new Error('更新失败');
        }
    };

    // ==================== 渲染弹窗 ====================

    // 渲染创建工具弹窗
    const renderCreateModal = () => (
        <Modal
            title='创建新工具'
            open={createModalVisible}
            onOk={handleCreateTool}
            onCancel={() => setCreateModalVisible(false)}
            confirmLoading={createLoading}
            okText='确定'
            cancelText='取消'
            width={480}
            destroyOnClose
        >
            <Form form={createForm} layout='vertical' autoComplete='off'>
                <Form.Item
                    name='name'
                    label='工具名称'
                    rules={[
                        {required: true, message: '请输入工具名称'},
                        {max: 50, message: '工具名称最多50个字符'},
                        {pattern: /^[a-zA-Z0-9_-]+$/, message: '只能包含字母、数字、下划线和连字符'}
                    ]}
                    extra='建议使用简洁的英文名称，如：cline-dev、cursor-prod'
                >
                    <Input placeholder='请输入工具名称' maxLength={50} />
                </Form.Item>
                <Form.Item name='description' label='工具描述' rules={[{max: 200, message: '描述最多200个字符'}]}>
                    <Input.TextArea placeholder='请输入工具描述（选填）' rows={3} maxLength={200} />
                </Form.Item>
                <Form.Item
                    name='api_type'
                    label='API 类型'
                    initialValue='openai_chat'
                    extra='选择该工具使用的 API 类型，决定了请求如何转发到 Provider'
                >
                    <LLMGateSelect placeholder='请选择 API 类型' options={API_TYPE_OPTIONS} />
                </Form.Item>
            </Form>
        </Modal>
    );

    // 渲染编辑工具弹窗
    const renderEditModal = () => (
        <Modal
            title='编辑工具'
            open={editModalVisible}
            onOk={handleUpdateTool}
            onCancel={() => setEditModalVisible(false)}
            confirmLoading={editLoading}
            okText='保存'
            cancelText='取消'
            width={480}
            destroyOnClose
        >
            <Form form={editForm} layout='vertical' autoComplete='off'>
                <Form.Item
                    name='name'
                    label='工具名称'
                    rules={[
                        {required: true, message: '请输入工具名称'},
                        {max: 50, message: '工具名称最多50个字符'},
                        {pattern: /^[a-zA-Z0-9_-]+$/, message: '只能包含字母、数字、下划线和连字符'}
                    ]}
                >
                    <Input placeholder='请输入工具名称' maxLength={50} />
                </Form.Item>
                <Form.Item name='description' label='工具描述' rules={[{max: 200, message: '描述最多200个字符'}]}>
                    <Input.TextArea placeholder='请输入工具描述（选填）' rows={3} maxLength={200} />
                </Form.Item>
                <Form.Item
                    name='api_type'
                    label='API 类型'
                    extra='选择该工具使用的 API 类型，决定了请求如何转发到 Provider'
                >
                    <LLMGateSelect placeholder='请选择 API 类型' options={API_TYPE_OPTIONS} />
                </Form.Item>
            </Form>
        </Modal>
    );

    // 渲染API Key展示弹窗
    const renderApiKeyModal = () => (
        <Modal
            title={
                <div style={{display: 'flex', alignItems: 'center', gap: 8}}>
                    <Icon icon='heroicons:check-circle' style={{fontSize: 24, color: '#22c55e'}} />
                    <span>{isRegeneratedKey ? 'Key 重新生成成功' : '工具创建成功'}</span>
                </div>
            }
            open={apiKeyModalVisible}
            onCancel={() => setApiKeyModalVisible(false)}
            footer={
                <Button type='primary' onClick={() => setApiKeyModalVisible(false)}>
                    关闭
                </Button>
            }
            width={520}
            closable={false}
            maskClosable={false}
        >
            <div
                style={{
                    marginBottom: 16,
                    padding: 12,
                    background: '#fffbeb',
                    borderRadius: 8,
                    border: '1px solid #fcd34d'
                }}
            >
                <p style={{margin: 0, color: '#92400e'}}>
                    <strong>⚠️ 重要提示：</strong>请妥善保存此 API Key，关闭后将无法再次查看。如果丢失，您需要重新生成。
                </p>
            </div>
            <div style={{marginBottom: 16}}>
                <label style={{display: 'block', marginBottom: 8, fontWeight: 500}}>API Key</label>
                <div style={{display: 'flex', gap: 12}}>
                    <Input.TextArea
                        value={newApiKey}
                        readOnly
                        autoSize={{minRows: 2, maxRows: 3}}
                        style={{fontFamily: 'Monaco, Menlo, monospace', fontSize: 13}}
                    />
                    <Button type='primary' onClick={handleCopyApiKey}>
                        复制
                    </Button>
                </div>
            </div>
            <div style={{padding: 12, background: '#f8fafc', borderRadius: 8}}>
                <p style={{margin: 0, color: '#64748b', fontSize: 14}}>
                    使用方式：在客户端（如 Cline、Cursor）中配置 API 端点和此 Key
                </p>
            </div>
        </Modal>
    );

    // Provider Key 下拉选项
    const providerKeyOptions = providerKeys.map((key) => ({
        value: key.name,
        label: key.name
    }));

    // 渲染测试连通性按钮
    const renderTestConnectionButton = () => {
        const statusConfig = {
            idle: {
                icon: <ApiOutlined />,
                text: '测试连通性',
                className: 'test-connection-btn'
            },
            loading: {
                icon: <LoadingOutlined />,
                text: '测试中...',
                className: 'test-connection-btn loading'
            },
            success: {
                icon: <CheckCircleOutlined />,
                text: `连接成功 · ${testConnectionResult.latency}ms`,
                className: 'test-connection-btn success'
            },
            error: {
                icon: <CloseCircleOutlined />,
                text: '连接失败',
                className: 'test-connection-btn error'
            }
        };

        const config = statusConfig[testConnectionStatus];

        return (
            <div style={{display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 4}}>
                <Button
                    onClick={handleTestConnection}
                    disabled={testConnectionStatus === 'loading'}
                    icon={config.icon}
                    className={config.className}
                >
                    {config.text}
                </Button>
                {testConnectionStatus === 'error' && testConnectionResult.message && (
                    <div className='test-connection-tip'>
                        {testConnectionResult.message}
                        {testConnectionResult.attemptedUrls && testConnectionResult.attemptedUrls.length > 0 && (
                            <div className='test-connection-tip-urls'>
                                {testConnectionResult.attemptedUrls.map((u, i) => (
                                    <div key={i}>尝试 {i + 1}: {u}</div>
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </div>
        );
    };

    // 渲染添加路由弹窗（精简版 - 只保留4个字段）
    const renderAddRouteModal = () => {
        // 检查是否有可用的现有路由
        const hasExistingRoutes = tools.some((tool) => tool.routes.length > 0);

        return (
            <Modal
                title='添加路由'
                open={addRouteModalVisible}
                onCancel={handleCloseAddRouteModal}
                width={520}
                destroyOnClose
                footer={
                    <div style={{display: 'flex', justifyContent: 'space-between'}}>
                        {renderTestConnectionButton()}
                        <Space>
                            <Button onClick={handleCloseAddRouteModal}>取消</Button>
                            <Button type='primary' onClick={handleSubmitAddRoute} loading={addRouteLoading}>
                                确定
                            </Button>
                        </Space>
                    </div>
                }
            >
                {/* 使用现有路由按钮 */}
                {hasExistingRoutes && (
                    <div className='use-existing-route-section'>
                        <Button
                            icon={<CopyOutlined />}
                            onClick={handleOpenExistingRoutesModal}
                            className='use-existing-route-btn'
                        >
                            使用现有路由配置
                        </Button>
                        <span className='use-existing-route-hint'>从其他工具复制路由配置到当前工具</span>
                    </div>
                )}

                <Form form={addRouteForm} layout='vertical' autoComplete='off'>
                    <Form.Item
                        name='name'
                        label='路由名称'
                        rules={[
                            {required: true, message: '请输入路由名称'},
                            {max: 50, message: '路由名称最多50个字符'}
                        ]}
                        extra='用于标识此路由配置，如：gpt-4o-main'
                    >
                        <Input placeholder='请输入路由名称' maxLength={50} />
                    </Form.Item>

                    <Form.Item
                        name='provider_key_name'
                        label='供应商 Key'
                        rules={[{required: true, message: '请选择供应商 Key'}]}
                        extra='在「供应商密钥管理」中配置的密钥'
                    >
                        <LLMGateSelect
                            placeholder='请选择供应商 Key'
                            options={providerKeyOptions}
                            showSearch
                            filterOption={(input, option) =>
                                String(option?.label ?? '')
                                    .toLowerCase()
                                    .includes(input.toLowerCase())
                            }
                        />
                    </Form.Item>

                    <Form.Item
                        name='base_url'
                        label='Base URL（接口地址）'
                        rules={[
                            {required: true, message: '请输入接口地址'},
                            {
                                validator: (_, value) => {
                                    if (!value) return Promise.resolve();
                                    // 简单验证是否为有效 URL
                                    if (/^https?:\/\/.+/.test(value.trim())) {
                                        return Promise.resolve();
                                    }
                                    return Promise.reject(new Error('请输入有效的 URL，需以 http:// 或 https:// 开头'));
                                }
                            }
                        ]}
                        extra='例如：https://your-provider-host/v1'
                    >
                        <Input placeholder='https://your-provider-host/v1' />
                    </Form.Item>

                    <Form.Item
                        name='model'
                        label='模型名称'
                        rules={[{required: true, message: '请输入模型名称'}]}
                        extra='如：claude-opus-4-5, gpt-5.2'
                    >
                        <Input placeholder='请输入模型名称' />
                    </Form.Item>
                </Form>
            </Modal>
        );
    };

    // 渲染现有路由选择弹窗
    const renderExistingRoutesModal = () => {
        const selectableRoutes = getAllSelectableRoutes();

        return (
            <Modal
                title='选择现有路由'
                open={existingRoutesModalVisible}
                onCancel={() => setExistingRoutesModalVisible(false)}
                footer={null}
                width={600}
                destroyOnClose
                className='existing-routes-modal'
            >
                {/* 搜索框 */}
                <Input
                    prefix={<SearchOutlined style={{color: '#94a3b8'}} />}
                    placeholder='搜索路由名称、模型或接口地址...'
                    value={existingRoutesSearchText}
                    onChange={(e) => setExistingRoutesSearchText(e.target.value)}
                    allowClear
                    style={{marginBottom: 16}}
                />

                {/* 路由列表 */}
                <div className='existing-routes-list'>
                    {selectableRoutes.length === 0 ? (
                        <Empty description='没有找到匹配的路由' image={Empty.PRESENTED_IMAGE_SIMPLE} />
                    ) : (
                        selectableRoutes.map(({tool, routes}) => (
                            <div key={tool.id} className='tool-routes-group'>
                                <div className='tool-group-header'>
                                    <Icon icon='heroicons:cube' style={{color: '#6366f1'}} />
                                    <span className='tool-group-name'>{tool.name}</span>
                                    <Tag color='blue'>{routes.length} 个路由</Tag>
                                </div>
                                <div className='routes-list'>
                                    {routes.map((route) => (
                                        <div
                                            key={route.id}
                                            className='route-select-item'
                                            onClick={() => handleSelectExistingRoute(route, tool.id)}
                                        >
                                            <div className='route-select-info'>
                                                <div className='route-select-name'>
                                                    {route.name}
                                                    {route.enabled && (
                                                        <Tag color='green' style={{marginLeft: 8}}>
                                                            Active
                                                        </Tag>
                                                    )}
                                                </div>
                                                <div className='route-select-details'>
                                                    <span className='route-detail-item'>
                                                        <Icon icon='heroicons:server' />
                                                        {route.endpoint}
                                                    </span>
                                                    <span className='route-detail-item'>
                                                        <Icon icon='heroicons:cpu-chip' />
                                                        {route.modelName}
                                                    </span>
                                                </div>
                                            </div>
                                            <Button type='link' size='small' icon={<CopyOutlined />}>
                                                选择
                                            </Button>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </Modal>
        );
    };

    // 渲染拖拽复制确认弹窗
    const renderDragCopyModal = () => (
        <Modal
            title='确认复制路由'
            open={dragCopyModalVisible}
            onOk={handleConfirmDragCopy}
            onCancel={() => {
                setDragCopyModalVisible(false);
                setDragCopyData(null);
            }}
            confirmLoading={dragCopyLoading}
            okText='确认添加'
            cancelText='取消'
            width={480}
        >
            {dragCopyData && (
                <div className='drag-copy-content'>
                    <p className='drag-copy-desc'>
                        是否要将路由 <strong>「{dragCopyData.sourceRoute.name}」</strong>
                        <br />从 <Tag color='blue'>{dragCopyData.sourceToolName}</Tag>
                        复制到 <Tag color='green'>{dragCopyData.targetToolName}</Tag>？
                    </p>
                    <div className='drag-copy-details'>
                        <h4>复制的路由配置：</h4>
                        <ul>
                            <li>
                                <span className='label'>供应商 Key：</span>
                                <span className='value'>{dragCopyData.sourceRoute.provider}</span>
                            </li>
                            <li>
                                <span className='label'>接口地址：</span>
                                <span className='value'>{dragCopyData.sourceRoute.endpoint}</span>
                            </li>
                            <li>
                                <span className='label'>模型名称：</span>
                                <span className='value'>{dragCopyData.sourceRoute.modelName}</span>
                            </li>
                        </ul>
                    </div>
                </div>
            )}
        </Modal>
    );

    // ==================== 渲染页面状态 ====================

    // 渲染加载状态
    if (loading && tools.length === 0) {
        return (
            <div className='tool-management'>
                <div className='loading-container'>
                    <Spin size='large' tip='正在加载工具列表...' />
                </div>
            </div>
        );
    }

    // 渲染错误状态
    if (error && tools.length === 0) {
        return (
            <div className='tool-management'>
                <Result
                    status='error'
                    title='加载失败'
                    subTitle={error}
                    extra={
                        <Button type='primary' icon={<ReloadOutlined />} onClick={fetchTools}>
                            重新加载
                        </Button>
                    }
                />
            </div>
        );
    }

    // 渲染空状态
    if (!loading && tools.length === 0) {
        return (
            <div className='tool-management'>
                <div className='empty-container'>
                    <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description='暂无工具'>
                        <p className='empty-hint'>点击下方按钮创建您的第一个工具</p>
                        <Button type='primary' icon={<PlusOutlined />} onClick={handleOpenCreateModal}>
                            创建工具
                        </Button>
                    </Empty>
                </div>

                {/* 创建工具弹窗 */}
                {renderCreateModal()}
                {renderApiKeyModal()}
            </div>
        );
    }

    // 正常渲染
    return (
        <div className='tool-management'>
            {/* 顶部操作栏 */}
            <div className='toolbar'>
                <div className='tool-count'>
                    共 <span className='count-number'>{tools.length}</span> 个工具
                </div>
                <Button
                    type='primary'
                    icon={<PlusOutlined />}
                    onClick={handleOpenCreateModal}
                    className='add-tool-btn'
                    ref={addToolBtnRef as React.RefObject<HTMLButtonElement>}
                >
                    添加新工具
                </Button>
            </div>

            {/* 工具列表 */}
            <div className='tool-list'>
                {tools
                    .slice()
                    .sort((a, b) => Number(a.id) - Number(b.id))
                    .map((tool) => (
                        <ToolCard
                            key={tool.id}
                            tool={tool}
                            providerKeys={providerKeys}
                            onEdit={handleEditTool}
                            onDelete={handleDeleteTool}
                            onAddRoute={handleAddRoute}
                            onDeleteRoute={handleDeleteRoute}
                            onToggleRoute={handleToggleRoute}
                            onUpdateRoute={handleUpdateRoute}
                            onRegenerateKey={handleRegenerateKey}
                            onProviderKeysRefresh={refreshProviderKeys}
                            onRouteDrop={handleRouteDrop}
                            onRouteReorder={handleRouteReorder}
                        />
                    ))}

                {/* 添加新工具占位卡片 */}
                <div className='add-tool-placeholder' onClick={handleOpenCreateModal}>
                    <div className='placeholder-icon'>
                        <Icon icon='heroicons:plus' />
                    </div>
                    <p className='placeholder-title'>添加新工具</p>
                </div>
            </div>

            {/* 弹窗 */}
            {renderCreateModal()}
            {renderEditModal()}
            {renderApiKeyModal()}
            {renderAddRouteModal()}
            {renderExistingRoutesModal()}
            {renderDragCopyModal()}
        </div>
    );
};

export default ToolManagement;
