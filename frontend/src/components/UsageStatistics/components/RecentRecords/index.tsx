/**
 * 最近请求记录组件
 */
import React, {useState, useEffect, useCallback} from 'react';
import {Spin, message, Tooltip, Empty} from 'antd';
import {Icon} from '@iconify/react';
import {UsageRecord, calculateRecordCost} from '../../../../types';
import * as llmGateApi from '@/api';
const styles = require('./index.module.less');

type LimitType = 10 | 20 | 50;

const RecentRecords: React.FC = () => {
    // ===== 状态管理 =====
    const [loading, setLoading] = useState(true);
    const [records, setRecords] = useState<UsageRecord[]>([]);
    const [total, setTotal] = useState(0);
    const [limit, setLimit] = useState<LimitType>(10);

    const limitOptions: {key: LimitType; label: string}[] = [
        {key: 10, label: '10条'},
        {key: 20, label: '20条'},
        {key: 50, label: '50条'}
    ];

    // ===== 工具函数 =====
    /**
     * 格式化时间为相对时间或 HH:mm:ss
     */
    const formatTime = (dateStr: string | null): string => {
        if (!dateStr) return '-';
        const date = new Date(dateStr);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffMin = Math.floor(diffMs / 60000);
        const diffHour = Math.floor(diffMs / 3600000);

        if (diffMin < 1) return '刚刚';
        if (diffMin < 60) return `${diffMin}分钟前`;
        if (diffHour < 24) return `${diffHour}小时前`;

        // 超过24小时显示具体时间
        return date.toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });
    };

    /**
     * 格式化日期
     */
    const formatDate = (dateStr: string | null): string => {
        if (!dateStr) return '';
        const date = new Date(dateStr);
        const now = new Date();
        const isToday = date.toDateString() === now.toDateString();

        if (isToday) return '今天';

        const yesterday = new Date(now);
        yesterday.setDate(yesterday.getDate() - 1);
        if (date.toDateString() === yesterday.toDateString()) return '昨天';

        return date.toLocaleDateString('zh-CN', {
            month: '2-digit',
            day: '2-digit'
        });
    };

    /**
     * 格式化 Token 数量
     */
    const formatTokens = (num: number): string => {
        if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
        if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
        return num.toLocaleString();
    };

    /**
     * 获取模型图标
     */
    const getModelIcon = (model: string): string => {
        const lowerModel = model.toLowerCase();
        if (lowerModel.includes('claude')) return 'simple-icons:anthropic';
        if (lowerModel.includes('gpt') || lowerModel.includes('openai')) return 'simple-icons:openai';
        if (lowerModel.includes('gemini')) return 'simple-icons:google';
        if (lowerModel.includes('llama')) return 'simple-icons:meta';
        return 'heroicons:cpu-chip';
    };

    /**
     * 获取模型图标背景色
     */
    const getModelIconBgClass = (model: string): string => {
        const lowerModel = model.toLowerCase();
        if (lowerModel.includes('claude')) return styles.iconClaude;
        if (lowerModel.includes('gpt') || lowerModel.includes('openai')) return styles.iconOpenai;
        if (lowerModel.includes('gemini')) return styles.iconGemini;
        return styles.iconDefault;
    };

    // ===== 数据获取 =====
    const fetchRecords = async () => {
        try {
            setLoading(true);
            const response = await llmGateApi.getUsageRecords({limit});
            setRecords(response.data.records);
            setTotal(response.data.total);
        } catch (error) {
            message.error('获取请求记录失败');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchRecords();
    }, [limit]);

    // ===== 成本计算 =====
    /**
     * 格式化成本显示
     */
    const formatCost = (cost: number | null): string => {
        if (cost === null) return '-';
        if (cost < 0.0001) return '<$0.0001';
        if (cost < 0.01) return `$${cost.toFixed(4)}`;
        return `$${cost.toFixed(4)}`;
    };

    /**
     * 计算所有记录的总成本
     */
    const calculateTotalCost = useCallback((): number => {
        return records.reduce((sum, record) => {
            const cost = calculateRecordCost(record);
            return sum + (cost || 0);
        }, 0);
    }, [records]);

    // ===== 交互处理 =====
    const handleLimitChange = (newLimit: LimitType) => {
        setLimit(newLimit);
    };

    // ===== 渲染函数 =====
    const renderRecordItem = (record: UsageRecord) => {
        const isSuccess = record.status === 'success';

        return (
            <div key={record.id} className={styles.recordItem}>
                <div className={styles.recordMain}>
                    {/* 状态指示器 */}
                    <div className={`${styles.statusIndicator} ${isSuccess ? styles.success : styles.error}`}>
                        <Icon icon={isSuccess ? 'heroicons:check-circle-solid' : 'heroicons:x-circle-solid'} />
                    </div>

                    {/* 模型图标 */}
                    <div className={`${styles.modelIcon} ${getModelIconBgClass(record.model)}`}>
                        <Icon icon={getModelIcon(record.model)} />
                    </div>

                    {/* 模型信息 */}
                    <div className={styles.recordInfo}>
                        <div className={styles.modelName}>{record.model}</div>
                        <div className={styles.recordMeta}>
                            <span className={styles.toolName}>{record.tool_name || '未知工具'}</span>
                            <span className={styles.separator}>·</span>
                            <span className={styles.routeName}>{record.route_name}</span>
                        </div>
                        {!isSuccess && record.error_message && (
                            <div className={styles.errorMessage}>
                                <Icon icon="heroicons:exclamation-triangle" />
                                <span>{record.error_message}</span>
                            </div>
                        )}
                    </div>
                </div>

                {/* Token 用量 */}
                <div className={styles.recordStats}>
                    <Tooltip
                        title={
                            <div className={styles.tokenTooltip}>
                                <div>Prompt: {record.prompt_tokens.toLocaleString()}</div>
                                <div>Completion: {record.completion_tokens.toLocaleString()}</div>
                                {(record.cache_creation_input_tokens > 0 ||
                                    record.cache_read_input_tokens > 0) && (
                                    <>
                                        <div className={styles.tokenDivider} />
                                        <div>Cache Write: {record.cache_creation_input_tokens.toLocaleString()}</div>
                                        <div>Cache Read: {record.cache_read_input_tokens.toLocaleString()}</div>
                                    </>
                                )}
                                {record.cached_tokens > 0 && (
                                    <>
                                        <div className={styles.tokenDivider} />
                                        <div>Cached: {record.cached_tokens.toLocaleString()}</div>
                                    </>
                                )}
                                <>
                                    <div className={styles.tokenDivider} />
                                    <div className={styles.costInfo}>
                                        预估成本: {formatCost(calculateRecordCost(record))}
                                    </div>
                                </>
                            </div>
                        }
                    >
                        <div className={styles.tokenCount}>
                            <Icon icon="heroicons:squares-2x2" />
                            <span>{formatTokens(record.total_tokens)}</span>
                            {(record.cache_creation_input_tokens > 0 ||
                                record.cache_read_input_tokens > 0 ||
                                record.cached_tokens > 0) && (
                                <span className={styles.cacheIndicator}>
                                    <Icon icon="heroicons:bolt" />
                                </span>
                            )}
                        </div>
                    </Tooltip>
                    <div className={styles.costBadge}>
                        <Icon icon="heroicons:currency-dollar" />
                        <span>{formatCost(calculateRecordCost(record))}</span>
                    </div>

                    <div className={styles.recordTime}>
                        <span className={styles.timeDate}>{formatDate(record.created_at)}</span>
                        <span className={styles.timeValue}>{formatTime(record.created_at)}</span>
                    </div>
                </div>
            </div>
        );
    };

    // ===== 渲染布局 =====
    return (
        <div className={styles.recentRecords}>
            <div className={styles.header}>
                <h3 className={styles.title}>
                    <Icon icon="heroicons:clock" />
                    <span>最近请求记录</span>
                    {!loading && <span className={styles.totalCount}>共 {total} 条</span>}
                    {!loading && (
                        <span className={styles.debugBadge}>
                            <Icon icon="heroicons:currency-dollar" />
                            总成本: ${calculateTotalCost().toFixed(4)}
                        </span>
                    )}
                </h3>
                <div className={styles.limitTabs}>
                    {limitOptions.map((option) => (
                        <button
                            key={option.key}
                            className={`${styles.limitTab} ${limit === option.key ? styles.active : ''}`}
                            onClick={() => handleLimitChange(option.key)}
                        >
                            {option.label}
                        </button>
                    ))}
                </div>
            </div>

            <div className={styles.content}>
                {loading ? (
                    <div className={styles.loadingWrapper}>
                        <Spin tip="加载中..." />
                    </div>
                ) : records.length === 0 ? (
                    <Empty
                        image={Empty.PRESENTED_IMAGE_SIMPLE}
                        description="暂无请求记录"
                    />
                ) : (
                    <div className={styles.recordList}>
                        {records.map(renderRecordItem)}
                    </div>
                )}
            </div>
        </div>
    );
};

export default RecentRecords;
