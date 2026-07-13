/**
 * 模型探测器组件
 * 用于批量探测 LLM Provider 端点支持的模型列表
 */
import React, {useState, useCallback, useMemo, useRef} from 'react';
import {Modal, Button, Input, message, Spin, Empty, Tag} from 'antd';
import {
    PlusOutlined,
    DeleteOutlined,
    CaretRightOutlined,
    CaretDownOutlined,
    CheckCircleOutlined,
    CloseCircleOutlined,
    LoadingOutlined
} from '@ant-design/icons';
import {Icon} from '@iconify/react';
import LLMGateSelect from '../LLMGateSelect';
import {probeModels} from '@/api';
import type {ApiProviderKey, ProbeResult} from '../../types';
import './index.less';

interface CustomTarget {
    id: string;
    base_url: string;
    provider_key_name: string;
}

interface ResultItem extends ProbeResult {
    expanded: boolean;
}

interface ModelDetectorProps {
    visible: boolean;
    onClose: () => void;
    providerKeys: ApiProviderKey[];
}

const ModelDetector: React.FC<ModelDetectorProps> = ({visible, onClose, providerKeys}) => {
    // 自定义地址状态
    const [customTargets, setCustomTargets] = useState<CustomTarget[]>([]);

    // 探测状态
    const [probing, setProbing] = useState(false);
    const [results, setResults] = useState<ResultItem[]>([]);

    // 结果区域引用，用于自动滚动
    const resultsRef = useRef<HTMLDivElement>(null);

    // Provider Key 下拉选项
    const providerKeyOptions = useMemo(
        () =>
            providerKeys.map((key) => ({
                value: key.name,
                label: key.name
            })),
        [providerKeys]
    );

    // 添加自定义地址
    const handleAddCustomTarget = useCallback(() => {
        setCustomTargets((prev) => [
            ...prev,
            {
                id: `custom-${Date.now()}`,
                base_url: '',
                provider_key_name: ''
            }
        ]);
    }, []);

    // 删除自定义地址
    const handleRemoveCustomTarget = useCallback((id: string) => {
        setCustomTargets((prev) => prev.filter((t) => t.id !== id));
    }, []);

    // 更新自定义地址
    const handleUpdateCustomTarget = useCallback(
        (id: string, field: 'base_url' | 'provider_key_name', value: string) => {
            setCustomTargets((prev) => prev.map((t) => (t.id === id ? {...t, [field]: value} : t)));
        },
        []
    );

    // 切换结果展开/折叠
    const handleToggleExpand = useCallback((base_url: string) => {
        setResults((prev) => prev.map((r) => (r.base_url === base_url ? {...r, expanded: !r.expanded} : r)));
    }, []);

    // 开始探测
    const handleProbe = useCallback(async () => {
        // 构建探测目标列表
        const targets: {base_url: string; provider_key_name: string}[] = [];

        // 添加自定义端点
        customTargets.forEach((t) => {
            if (t.base_url && t.provider_key_name) {
                targets.push({
                    base_url: t.base_url.trim(),
                    provider_key_name: t.provider_key_name
                });
            }
        });

        // 验证
        if (targets.length === 0) {
            message.warning('请添加至少一个探测目标，并配置 Provider Key');
            return;
        }

        setProbing(true);
        setResults([]);

        try {
            const response = await probeModels({targets});
            setResults(
                response.data.results.map((r) => ({
                    ...r,
                    expanded: false
                }))
            );
            // 滚动到结果区域
            setTimeout(() => {
                resultsRef.current?.scrollIntoView({behavior: 'smooth', block: 'start'});
            }, 100);
        } catch (error: any) {
            message.error(error.response?.data?.message || '探测失败');
        } finally {
            setProbing(false);
        }
    }, [customTargets]);

    // 重置状态
    const handleReset = useCallback(() => {
        setCustomTargets([]);
        setResults([]);
    }, []);

    // 关闭弹窗
    const handleClose = useCallback(() => {
        handleReset();
        onClose();
    }, [onClose, handleReset]);

    // 从 URL 中提取简短名称
    const getShortName = (url: string) => {
        try {
            const urlObj = new URL(url);
            const pathParts = urlObj.pathname.split('/').filter(Boolean);
            // 返回路径的最后两部分（如 api/claude）
            if (pathParts.length >= 2) {
                return pathParts.slice(-2, -1).join('/');
            }
            return urlObj.hostname;
        } catch {
            return url;
        }
    };

    // 渲染结果项
    const renderResultItem = (result: ResultItem) => {
        const shortName = getShortName(result.base_url);
        const modelCount = result.data?.data?.length || 0;

        return (
            <div key={result.base_url} className={`result-item ${result.success ? 'success' : 'error'}`}>
                <div className='result-header' onClick={() => result.success && handleToggleExpand(result.base_url)}>
                    <div className='result-expand'>
                        {result.success && modelCount > 0 ? (
                            result.expanded ? (
                                <CaretDownOutlined />
                            ) : (
                                <CaretRightOutlined />
                            )
                        ) : (
                            <span className='expand-placeholder' />
                        )}
                    </div>
                    <div className='result-name' title={result.base_url}>
                        {shortName}
                    </div>
                    <div className='result-status'>
                        {result.success ? (
                            <CheckCircleOutlined className='status-icon success' />
                        ) : (
                            <CloseCircleOutlined className='status-icon error' />
                        )}
                    </div>
                    <div className='result-latency'>{result.latency_ms ? `${result.latency_ms}ms` : '-'}</div>
                    <div className='result-models'>
                        {result.success ? (
                            <Tag color='blue'>{modelCount} 个模型</Tag>
                        ) : (
                            <Tag color='red'>{result.error_code || '失败'}</Tag>
                        )}
                    </div>
                </div>
                {result.expanded && result.data?.data && (
                    <div className='result-model-list'>
                        {result.data.data.map((model) => (
                            <div key={model.id} className='model-item'>
                                <Icon icon='heroicons:cpu-chip' className='model-icon' />
                                <span className='model-name'>{model.id}</span>
                                {model.owned_by && <span className='model-owner'>({model.owned_by})</span>}
                            </div>
                        ))}
                    </div>
                )}
            </div>
        );
    };

    return (
        <Modal
            title={
                <div className='detector-modal-title'>
                    <Icon icon='heroicons:signal' className='title-icon' />
                    <span>模型探测器</span>
                </div>
            }
            open={visible}
            onCancel={handleClose}
            width={700}
            destroyOnClose
            className='model-detector-modal'
            footer={
                <div className='detector-footer'>
                    <Button onClick={handleClose}>取消</Button>
                    <Button
                        type='primary'
                        onClick={handleProbe}
                        loading={probing}
                        icon={probing ? <LoadingOutlined /> : <Icon icon='heroicons:signal' />}
                    >
                        {probing ? '探测中...' : '开始探测'}
                    </Button>
                </div>
            }
        >
            {/* 自定义端点区域 */}
            <div className='detector-section custom-section'>
                <div className='section-header'>
                    <div className='section-title'>
                        <Icon icon='heroicons:globe-alt' className='section-icon' />
                        <span>Custom Endpoints</span>
                    </div>
                    <Button
                        type='link'
                        icon={<PlusOutlined />}
                        onClick={handleAddCustomTarget}
                        className='add-custom-btn'
                    >
                        添加
                    </Button>
                </div>
                <div className='section-content'>
                    {customTargets.length === 0 ? (
                        <div className='custom-empty'>
                            <span>暂无自定义端点，点击「添加」按钮添加</span>
                        </div>
                    ) : (
                        <div className='custom-list'>
                            {customTargets.map((target) => (
                                <div key={target.id} className='custom-item'>
                                    <Input
                                        placeholder='https://api.example.com/v1'
                                        value={target.base_url}
                                        onChange={(e) =>
                                            handleUpdateCustomTarget(target.id, 'base_url', e.target.value)
                                        }
                                        className='custom-url-input'
                                    />
                                    <LLMGateSelect
                                        placeholder='Provider Key'
                                        value={target.provider_key_name || undefined}
                                        onChange={(value) =>
                                            handleUpdateCustomTarget(target.id, 'provider_key_name', value as string)
                                        }
                                        options={providerKeyOptions}
                                        style={{width: 160}}
                                        showSearch
                                        filterOption={(input, option) =>
                                            String(option?.label ?? '')
                                                .toLowerCase()
                                                .includes(input.toLowerCase())
                                        }
                                    />
                                    <Button
                                        type='text'
                                        danger
                                        icon={<DeleteOutlined />}
                                        onClick={() => handleRemoveCustomTarget(target.id)}
                                        className='remove-custom-btn'
                                    />
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {/* 探测结果区域 */}
            {(probing || results.length > 0) && (
                <div className='detector-section results-section' ref={resultsRef}>
                    <div className='section-header'>
                        <div className='section-title'>
                            <Icon icon='heroicons:clipboard-document-list' className='section-icon' />
                            <span>探测结果</span>
                        </div>
                    </div>
                    <div className='section-content'>
                        {probing ? (
                            <div className='results-loading'>
                                <Spin />
                                <span>正在探测中...</span>
                            </div>
                        ) : results.length === 0 ? (
                            <Empty description='暂无结果' image={Empty.PRESENTED_IMAGE_SIMPLE} />
                        ) : (
                            <div className='results-list'>{results.map(renderResultItem)}</div>
                        )}
                    </div>
                </div>
            )}
        </Modal>
    );
};

export default ModelDetector;
