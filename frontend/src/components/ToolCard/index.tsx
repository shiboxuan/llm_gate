/**
 * 工具卡片组件
 */
import React, {useState} from 'react';
import {Button, Switch, Popconfirm, Input, message, Tag} from 'antd';
import {EditOutlined, DeleteOutlined, PlusCircleOutlined, CloseOutlined, ReloadOutlined} from '@ant-design/icons';
import {Icon} from '@iconify/react';
import LLMGateSelect from '../LLMGateSelect';
import {ToolConfig, RouteConfig, ApiProviderKey, API_TYPE_COLORS, API_TYPE_LABELS} from '../../types';
import {getToolIcon, getModelProviderIcon} from '../../utils/iconMapping';
import './index.less';

interface ToolCardProps {
    tool: ToolConfig;
    providerKeys?: ApiProviderKey[];
    onEdit?: (tool: ToolConfig) => void;
    onDelete?: (toolId: string) => void;
    onAddRoute?: (toolId: string) => void;
    onDeleteRoute?: (toolId: string, routeId: string) => void;
    onToggleRoute?: (toolId: string, routeId: string, enabled: boolean) => void;
    onUpdateRoute?: (toolId: string, route: RouteConfig, field?: string, value?: string) => void;
    onRegenerateKey?: (toolId: string) => void;
    onProviderKeysRefresh?: () => void;
    // 拖拽复制路由功能（跨工具）
    onRouteDrop?: (sourceToolId: string, routeId: string, targetToolId: string) => void;
    // 拖拽排序功能（同工具内）
    onRouteReorder?: (toolId: string, routeId: string, newIndex: number) => void;
}

// 可编辑字段组件
interface EditableFieldProps {
    value: string;
    onSave: (newValue: string) => Promise<void>;
    className?: string;
}

const EditableField: React.FC<EditableFieldProps> = ({value, onSave, className}) => {
    const [editing, setEditing] = useState(false);
    const [tempValue, setTempValue] = useState(value);
    const [saving, setSaving] = useState(false);

    const handleStartEdit = () => {
        setTempValue(value);
        setEditing(true);
    };

    const handleSave = async () => {
        if (tempValue === value) {
            setEditing(false);
            return;
        }

        if (!tempValue.trim()) {
            message.warning('内容不能为空');
            setTempValue(value);
            setEditing(false);
            return;
        }

        setSaving(true);
        try {
            await onSave(tempValue.trim());
            setEditing(false);
        } catch {
            // 保存失败，回滚
            setTempValue(value);
            setEditing(false);
            message.error('保存失败，已回滚');
        } finally {
            setSaving(false);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') {
            handleSave();
        } else if (e.key === 'Escape') {
            setTempValue(value);
            setEditing(false);
        }
    };

    if (editing) {
        return (
            <Input
                size='small'
                value={tempValue}
                onChange={(e) => setTempValue(e.target.value)}
                onBlur={handleSave}
                onKeyDown={handleKeyDown}
                autoFocus
                disabled={saving}
                className='editable-input'
                style={{width: Math.max(tempValue.length * 7 + 20, 100)}}
            />
        );
    }

    return (
        <span className={`${className || ''} editable-field`} onClick={handleStartEdit} title='点击编辑'>
            {value}
        </span>
    );
};

const ToolCard: React.FC<ToolCardProps> = ({
    tool,
    providerKeys = [],
    onEdit,
    onDelete,
    onAddRoute,
    onDeleteRoute,
    onToggleRoute,
    onUpdateRoute,
    onRegenerateKey,
    onRouteDrop,
    onRouteReorder
}) => {
    // 路由开关 loading 状态
    const [loadingRouteIds, setLoadingRouteIds] = useState<Set<string>>(new Set());

    // 拖拽状态
    const [isDragOver, setIsDragOver] = useState(false);
    const [draggingRouteId, setDraggingRouteId] = useState<string | null>(null);

    // 同工具排序状态
    const [dropTargetIndex, setDropTargetIndex] = useState<number | null>(null);
    const [dragSourceToolId, setDragSourceToolId] = useState<string | null>(null);

    // ==================== 拖拽事件处理 ====================

    // 路由开始拖拽
    const handleRouteDragStart = (e: React.DragEvent, route: RouteConfig) => {
        e.dataTransfer.setData(
            'application/json',
            JSON.stringify({
                sourceToolId: tool.id,
                routeId: route.id,
                routeName: route.name
            })
        );
        // 同时设置 text/plain 用于同工具判断（dragenter 时可读取 types 但不能读取 data）
        e.dataTransfer.setData('text/source-tool-id', tool.id);
        // 同工具内为移动，跨工具为复制
        e.dataTransfer.effectAllowed = 'copyMove';
        setDraggingRouteId(route.id);
        setDragSourceToolId(tool.id);
    };

    // 路由拖拽结束
    const handleRouteDragEnd = () => {
        setDraggingRouteId(null);
        setDropTargetIndex(null);
        setDragSourceToolId(null);
    };

    // 工具卡片作为放置目标 - 拖拽进入
    const handleDragEnter = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();

        // 检查是否是路由拖拽
        if (e.dataTransfer.types.includes('application/json')) {
            setIsDragOver(true);
        }
    };

    // 工具卡片作为放置目标 - 拖拽悬停
    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();

        // 设置拖放效果
        if (e.dataTransfer.types.includes('application/json')) {
            // 同工具内为移动，跨工具为复制
            if (dragSourceToolId === tool.id) {
                e.dataTransfer.dropEffect = 'move';
            } else {
                e.dataTransfer.dropEffect = 'copy';
            }
        }
    };

    // 工具卡片作为放置目标 - 拖拽离开
    const handleDragLeave = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();

        // 检查是否真的离开了卡片（不是进入子元素）
        const relatedTarget = e.relatedTarget as HTMLElement;
        const currentTarget = e.currentTarget as HTMLElement;

        if (!currentTarget.contains(relatedTarget)) {
            setIsDragOver(false);
            setDropTargetIndex(null);
            setDragSourceToolId(null);
        }
    };

    // 工具卡片作为放置目标 - 放置
    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragOver(false);

        try {
            const data = JSON.parse(e.dataTransfer.getData('application/json'));
            const {sourceToolId, routeId} = data;

            if (sourceToolId === tool.id && dropTargetIndex !== null) {
                // 同工具：排序
                onRouteReorder?.(tool.id, routeId, dropTargetIndex);
            } else if (sourceToolId !== tool.id) {
                // 跨工具：复制
                onRouteDrop?.(sourceToolId, routeId, tool.id);
            }
        } catch (err) {
            console.error('拖拽数据解析失败', err);
        }

        setDropTargetIndex(null);
        setDragSourceToolId(null);
    };

    // 路由项 - 拖拽进入（用于确定插入位置）
    const handleRouteItemDragEnter = (e: React.DragEvent, index: number) => {
        e.preventDefault();
        e.stopPropagation();

        // 检查是否是同工具内的拖拽（通过 dataTransfer.types 判断）
        // 注意：dragenter 时无法读取 getData，只能通过 types 判断
        const types = Array.from(e.dataTransfer.types);
        if (types.includes('text/source-tool-id')) {
            // 如果当前有正在拖拽的路由且是同工具，显示插入指示器
            if (draggingRouteId) {
                setDropTargetIndex(index);
                setDragSourceToolId(tool.id);
            }
        }
    };

    // 路由项 - 拖拽悬停
    const handleRouteItemDragOver = (e: React.DragEvent, index: number) => {
        e.preventDefault();
        e.stopPropagation();

        // 同工具内拖拽时显示 move 效果
        if (draggingRouteId && dragSourceToolId === tool.id) {
            e.dataTransfer.dropEffect = 'move';
            setDropTargetIndex(index);
        }
    };

    // 编辑工具
    const handleEdit = () => {
        onEdit?.(tool);
    };

    // 删除工具
    const handleDelete = () => {
        onDelete?.(tool.id);
    };

    // 添加路由
    const handleAddRoute = () => {
        onAddRoute?.(tool.id);
    };

    // 删除路由
    const handleDeleteRoute = (routeId: string) => {
        onDeleteRoute?.(tool.id, routeId);
    };

    // 切换路由激活状态
    const handleToggleRoute = async (routeId: string, enabled: boolean) => {
        // 防止重复点击
        if (loadingRouteIds.has(routeId)) {
            return;
        }

        setLoadingRouteIds((prev) => new Set(prev).add(routeId));
        try {
            await onToggleRoute?.(tool.id, routeId, enabled);
        } finally {
            setLoadingRouteIds((prev) => {
                const next = new Set(prev);
                next.delete(routeId);
                return next;
            });
        }
    };

    // 更新供应商 Key
    const handleProviderKeyChange = (routeId: string, providerKeyName: string) => {
        const route = tool.routes.find((r) => r.id === routeId);
        if (route) {
            onUpdateRoute?.(tool.id, {...route, provider: providerKeyName}, 'provider_key_name', providerKeyName);
        }
    };

    // 更新接口地址
    const handleEndpointSave = async (routeId: string, newEndpoint: string) => {
        const route = tool.routes.find((r) => r.id === routeId);
        if (route) {
            await new Promise<void>((resolve, reject) => {
                try {
                    onUpdateRoute?.(tool.id, {...route, endpoint: newEndpoint}, 'base_url', newEndpoint);
                    resolve();
                } catch {
                    reject();
                }
            });
        }
    };

    // 更新模型名称
    const handleModelNameSave = async (routeId: string, newModelName: string) => {
        const route = tool.routes.find((r) => r.id === routeId);
        if (route) {
            await new Promise<void>((resolve, reject) => {
                try {
                    onUpdateRoute?.(tool.id, {...route, modelName: newModelName}, 'model', newModelName);
                    resolve();
                } catch {
                    reject();
                }
            });
        }
    };

    // 检查是否有激活的路由
    const hasActiveRoute = tool.routes.some((r) => r.enabled);

    // 获取状态显示
    const getStatusDisplay = () => {
        // 如果没有任何激活的路由，显示"未运行"
        if (!hasActiveRoute) {
            return (
                <span className='status-badge status-not-running'>
                    <span className='status-dot'></span>
                    未运行
                </span>
            );
        }

        switch (tool.status) {
            case 'running':
                return (
                    <span className='status-badge status-running'>
                        <span className='status-dot'></span>
                        运行中
                    </span>
                );
            case 'configuring':
                return (
                    <span className='status-badge status-configuring'>
                        <span className='status-dot pulse'></span>
                        配置中
                    </span>
                );
            case 'stopped':
                return (
                    <span className='status-badge status-stopped'>
                        <span className='status-dot'></span>
                        已停止
                    </span>
                );
            default:
                return null;
        }
    };

    // Provider Key 下拉选项
    const providerKeyOptions = providerKeys.map((key) => ({
        value: key.name,
        label: key.name
    }));

    // 获取工具图标配置（根据工具名称自动匹配）
    const toolIconInfo = getToolIcon(tool.name);

    // 获取当前工具的 API Type 配置
    const currentApiType = tool.apiType || 'openai_chat';
    const apiTypeColors = API_TYPE_COLORS[currentApiType];
    const apiTypeLabel = API_TYPE_LABELS[currentApiType];

    // 渲染工具图标
    const renderToolIcon = () => {
        if (toolIconInfo.isImageUrl) {
            return (
                <img src={toolIconInfo.icon} alt={tool.name} style={{width: 32, height: 32, objectFit: 'contain'}} />
            );
        }
        return <Icon icon={toolIconInfo.icon} style={{color: toolIconInfo.iconColor, fontSize: 28}} />;
    };

    return (
        <div
            className={`tool-card ${isDragOver ? 'drag-over' : ''}`}
            onDragEnter={handleDragEnter}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
        >
            {/* 工具头部 */}
            <div className='tool-header'>
                <div className='tool-info'>
                    <div className='tool-icon' style={{background: toolIconInfo.iconBgColor}}>
                        {renderToolIcon()}
                    </div>
                    <div className='tool-details'>
                        <div className='tool-title-row'>
                            <h3 className='tool-name'>{tool.name}</h3>
                            <Tag
                                className='api-type-tag'
                                style={{
                                    backgroundColor: apiTypeColors.bg,
                                    color: apiTypeColors.text,
                                    borderColor: apiTypeColors.border
                                }}
                            >
                                {apiTypeLabel}
                            </Tag>
                        </div>
                        <div className='tool-meta'>
                            <span className='tool-description'>{tool.description}</span>
                            {getStatusDisplay()}
                            <Button
                                size='small'
                                onClick={() => onRegenerateKey?.(tool.id)}
                                className='regenerate-btn'
                                icon={<ReloadOutlined />}
                            >
                                重新生成 Key
                            </Button>
                        </div>
                    </div>
                </div>
                <div className='tool-actions'>
                    <Button type='text' icon={<EditOutlined />} onClick={handleEdit} className='action-btn' />
                    <Popconfirm title='确定要删除此工具吗？' onConfirm={handleDelete} okText='确定' cancelText='取消'>
                        <Button type='text' icon={<DeleteOutlined />} className='action-btn delete-btn' />
                    </Popconfirm>
                </div>
            </div>

            {/* 路由区域 */}
            <div className='routes-section'>
                <div className='routes-header'>
                    <div className='routes-title'>
                        <span className='routes-dot'></span>
                        <span className='routes-label'>ROUTES</span>
                    </div>
                    <Button
                        type='link'
                        size='small'
                        icon={<PlusCircleOutlined />}
                        onClick={handleAddRoute}
                        className='add-route-btn'
                    >
                        添加
                    </Button>
                </div>
                <div className='routes-grid'>
                    {tool.routes.map((route, index) => {
                        // 根据模型名称获取提供商图标
                        const routeIconInfo = getModelProviderIcon(route.modelName);
                        const isDragging = draggingRouteId === route.id;
                        const isDropTarget = dropTargetIndex === index && dragSourceToolId === tool.id;

                        return (
                            <div
                                key={route.id}
                                className={`route-item ${route.enabled ? 'route-active' : ''} ${isDragging ? 'dragging' : ''} ${isDropTarget ? 'drop-target' : ''}`}
                                draggable
                                onDragStart={(e) => handleRouteDragStart(e, route)}
                                onDragEnd={handleRouteDragEnd}
                                onDragEnter={(e) => handleRouteItemDragEnter(e, index)}
                                onDragOver={(e) => handleRouteItemDragOver(e, index)}
                            >
                                <Popconfirm
                                    title='确定要删除此路由吗？'
                                    onConfirm={() => handleDeleteRoute(route.id)}
                                    okText='确定'
                                    cancelText='取消'
                                >
                                    <Button
                                        type='primary'
                                        danger
                                        size='small'
                                        icon={<CloseOutlined />}
                                        className='route-delete-btn'
                                    />
                                </Popconfirm>
                                <div className='route-header'>
                                    <div className='route-info'>
                                        <div
                                            className={`route-icon ${route.enabled ? 'active' : ''}`}
                                            style={route.enabled ? {} : {backgroundColor: `${routeIconInfo.color}15`}}
                                        >
                                            <Icon
                                                icon={routeIconInfo.icon}
                                                style={{
                                                    color: route.enabled ? routeIconInfo.color : routeIconInfo.color
                                                }}
                                            />
                                        </div>
                                        <span className='route-name'>{route.name}</span>
                                    </div>
                                    <Switch
                                        size='small'
                                        checked={route.enabled}
                                        loading={loadingRouteIds.has(route.id)}
                                        onChange={(checked) => handleToggleRoute(route.id, checked)}
                                    />
                                </div>
                                <div className='route-details'>
                                    <div className='route-field'>
                                        <span className='field-label'>供应商 Key</span>
                                        <LLMGateSelect
                                            size='small'
                                            value={route.provider}
                                            options={providerKeyOptions}
                                            onChange={(value) => handleProviderKeyChange(route.id, value)}
                                            className='provider-select'
                                            popupMatchSelectWidth={false}
                                            placeholder='选择 Key'
                                        />
                                    </div>
                                    <div className='route-field'>
                                        <span className='field-label'>接口地址</span>
                                        <EditableField
                                            value={route.endpoint}
                                            onSave={(newValue) => handleEndpointSave(route.id, newValue)}
                                            className='field-value'
                                        />
                                    </div>
                                    <div className='route-field'>
                                        <span className='field-label'>模型名称</span>
                                        <EditableField
                                            value={route.modelName}
                                            onSave={(newValue) => handleModelNameSave(route.id, newValue)}
                                            className='field-value'
                                        />
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
};

export default ToolCard;
