/**
 * 供应商密钥管理模块
 * 实现完整的 CRUD 功能：列表展示、创建、更新、删除
 */
import React, {useState, useEffect} from 'react';
import {Button, Input, message, Modal, Form, Alert, Spin, Empty, Tooltip} from 'antd';
import {
    PlusOutlined,
    EyeInvisibleOutlined,
    KeyOutlined,
    DeleteOutlined,
    EditOutlined,
    ExclamationCircleOutlined,
    ReloadOutlined
} from '@ant-design/icons';
import {Icon} from '@iconify/react';
import {ApiProviderKey} from '../../types';
import * as llmGateApi from '@/api';
import './index.less';

const ProviderKeyManagement: React.FC = () => {
    // ===== 状态管理 =====
    const [keys, setKeys] = useState<ApiProviderKey[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // 创建Modal状态
    const [createModalVisible, setCreateModalVisible] = useState(false);
    const [createLoading, setCreateLoading] = useState(false);
    const [form] = Form.useForm();

    // 编辑状态
    const [editingKeyId, setEditingKeyId] = useState<number | null>(null);
    const [newKeyValue, setNewKeyValue] = useState('');
    const [updateLoading, setUpdateLoading] = useState(false);

    // ===== 数据获取 =====
    const fetchKeys = async () => {
        try {
            setLoading(true);
            setError(null);

            const response = await llmGateApi.getProviderKeys();
            setKeys(response.data);
        } catch (err) {
            setError('获取密钥列表失败');
            message.error('获取密钥列表失败');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchKeys();
    }, []);

    // ===== 创建密钥 =====
    const handleCreate = async () => {
        try {
            const values = await form.validateFields();
            setCreateLoading(true);

            await llmGateApi.createProviderKey({
                name: values.name.trim(),
                api_key: values.api_key.trim()
            });
            message.success('密钥创建成功，已安全加密存储');
            fetchKeys();

            form.resetFields();
            setCreateModalVisible(false);
        } catch (error: any) {
            // 处理名称重复错误
            if (error?.response?.data?.code === 14004) {
                form.setFields([
                    {
                        name: 'name',
                        errors: ['密钥名称已存在，请使用其他名称']
                    }
                ]);
            }
        } finally {
            setCreateLoading(false);
        }
    };

    // ===== 编辑密钥 =====
    const handleStartEdit = (keyId: number) => {
        setEditingKeyId(keyId);
        setNewKeyValue('');
    };

    const handleCancelEdit = () => {
        setEditingKeyId(null);
        setNewKeyValue('');
    };

    const handleSaveKey = (keyId: number) => {
        if (!newKeyValue.trim()) {
            message.warning('请输入新的API Key');
            return;
        }

        Modal.confirm({
            title: '确定要更新此密钥吗？',
            content: '更新后，旧密钥将立即失效。使用此密钥的路由将自动使用新密钥。',
            okText: '确定更新',
            cancelText: '取消',
            onOk: async () => {
                try {
                    setUpdateLoading(true);

                    await llmGateApi.updateProviderKey(keyId, {
                        api_key: newKeyValue.trim()
                    });
                    message.success('密钥更新成功');

                    handleCancelEdit();
                } catch (error) {
                    message.error('更新失败，请重试');
                } finally {
                    setUpdateLoading(false);
                }
            }
        });
    };

    // ===== 删除密钥 =====
    const handleDeleteKey = (key: ApiProviderKey) => {
        Modal.confirm({
            title: '确定要删除此密钥吗？',
            icon: <ExclamationCircleOutlined />,
            content: (
                <div>
                    <p>
                        <strong>⚠️ 警告：</strong>
                    </p>
                    <ul style={{paddingLeft: 20}}>
                        <li>删除后，使用此密钥的路由将无法正常工作</li>
                        <li>请确保已更新相关路由的密钥配置</li>
                        <li>此操作不可恢复</li>
                    </ul>
                </div>
            ),
            okText: '确定删除',
            cancelText: '取消',
            okButtonProps: {danger: true},
            onOk: async () => {
                try {
                    await llmGateApi.deleteProviderKey(key.id);
                    setKeys((prev) => prev.filter((k) => k.id !== key.id));
                    message.success('密钥删除成功');
                } catch (error) {
                    message.error('删除失败，请重试');
                }
            }
        });
    };

    // ===== 格式化日期 =====
    const formatDate = (dateStr: string) => {
        return new Date(dateStr).toLocaleDateString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit'
        });
    };

    // ===== 渲染加载状态 =====
    if (loading && keys.length === 0) {
        return (
            <div className="provider-key-management">
                <div className="key-card loading">
                    <Spin size="large" tip="正在加载密钥列表..." />
                </div>
            </div>
        );
    }

    // ===== 渲染错误状态 =====
    if (error && keys.length === 0) {
        return (
            <div className="provider-key-management">
                <div className="key-card error">
                    <p>{error}</p>
                    <Button type="primary" icon={<ReloadOutlined />} onClick={fetchKeys}>
                        重新加载
                    </Button>
                </div>
            </div>
        );
    }

    return (
        <div className="provider-key-management">
            <div className="key-card">
                <h2 className="card-title">
                    <Icon icon="heroicons:key-solid" className="title-icon" />
                    供应商密钥配置
                </h2>
                <p className="card-description">
                    在这里配置您的 LLM 供应商 API 密钥，这些密钥将在路由配置中被引用。
                </p>

                {/* 密钥列表 */}
                <div className="key-list">
                    {keys.length === 0 ? (
                        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无密钥配置" />
                    ) : (
                        keys.map((keyItem) => (
                            <div key={keyItem.id} className="key-item">
                                <div className="key-item-header">
                                    <span className="key-name">{keyItem.name}</span>
                                    <span className={`key-status ${keyItem.status === 1 ? 'active' : 'inactive'}`}>
                                        {keyItem.status === 1 ? '启用' : '禁用'}
                                    </span>
                                </div>

                                <div className="key-input-wrapper">
                                    {editingKeyId === keyItem.id ? (
                                        <>
                                            <Input.Password
                                                value={newKeyValue}
                                                onChange={(e) => setNewKeyValue(e.target.value)}
                                                placeholder="请输入新的API Key"
                                                className="key-input"
                                                prefix={<KeyOutlined />}
                                            />
                                            <Button
                                                type="primary"
                                                size="small"
                                                onClick={() => handleSaveKey(keyItem.id)}
                                                loading={updateLoading}
                                                disabled={!newKeyValue.trim()}
                                            >
                                                保存
                                            </Button>
                                            <Button size="small" onClick={handleCancelEdit}>
                                                取消
                                            </Button>
                                        </>
                                    ) : (
                                        <>
                                            <Input
                                                type="password"
                                                value="••••••••••••••••••••••••"
                                                readOnly
                                                className="key-input"
                                                prefix={<KeyOutlined />}
                                            />
                                            <Tooltip title="密钥已加密存储，无法查看明文">
                                                <Button type="text" icon={<EyeInvisibleOutlined />} disabled />
                                            </Tooltip>
                                            <Tooltip title="更新密钥">
                                                <Button
                                                    type="text"
                                                    icon={<EditOutlined />}
                                                    onClick={() => handleStartEdit(keyItem.id)}
                                                />
                                            </Tooltip>
                                            <Tooltip title="删除密钥">
                                                <Button
                                                    type="text"
                                                    danger
                                                    icon={<DeleteOutlined />}
                                                    onClick={() => handleDeleteKey(keyItem)}
                                                />
                                            </Tooltip>
                                        </>
                                    )}
                                </div>

                                <div className="key-item-footer">
                                    <span className="create-time">创建时间：{formatDate(keyItem.created_at)}</span>
                                </div>
                            </div>
                        ))
                    )}
                </div>

                {/* 底部操作栏 */}
                <div className="card-footer">
                    <Button
                        type="primary"
                        icon={<PlusOutlined />}
                        onClick={() => setCreateModalVisible(true)}
                        className="add-config-btn"
                    >
                        增加配置
                    </Button>
                </div>
            </div>

            {/* 创建密钥Modal */}
            <Modal
                title="添加供应商密钥"
                open={createModalVisible}
                onOk={handleCreate}
                onCancel={() => {
                    form.resetFields();
                    setCreateModalVisible(false);
                }}
                confirmLoading={createLoading}
                okText="确定"
                cancelText="取消"
                destroyOnClose
            >
                <Alert
                    type="info"
                    message="安全提示"
                    description="API Key 将使用 AES-256 加密存储，提交后无法再次查看明文。"
                    showIcon
                    style={{marginBottom: 16}}
                />

                <Form form={form} layout="vertical">
                    <Form.Item
                        name="name"
                        label="密钥名称"
                        rules={[
                            {required: true, message: '请输入密钥名称'},
                            {max: 50, message: '密钥名称最多50个字符'},
                            {pattern: /^[a-zA-Z0-9_-]+$/, message: '只能包含字母、数字、下划线和连字符'}
                        ]}
                        extra="用于在路由配置中引用此密钥，如：my-openai-key"
                    >
                        <Input placeholder="请输入密钥名称" prefix={<KeyOutlined />} maxLength={50} />
                    </Form.Item>

                    <Form.Item
                        name="api_key"
                        label="API Key"
                        rules={[
                            {required: true, message: '请输入API Key'},
                            {min: 10, message: 'API Key长度不能少于10个字符'}
                        ]}
                        extra="从 LLM 服务提供商获取的 API 密钥"
                    >
                        <Input.Password placeholder="请输入API Key" />
                    </Form.Item>
                </Form>
            </Modal>
        </div>
    );
};

export default ProviderKeyManagement;
