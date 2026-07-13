/**
 * 统计界面组件
 * 文件位置：src/view/LLMGate/components/UsageStatistics/index.tsx
 */
import React, {useState, useEffect, useRef, useCallback} from 'react';
import {Spin, message, Tooltip, Button} from 'antd';
import {Icon} from '@iconify/react';
import {StatCard, ToolUsageData, TimeFilter, TokenStats} from '../../types';
import {getToolIcon, getModelProviderIcon} from '../../utils/iconMapping';
import * as llmGateApi from '@/api';
import RecentRecords from './components/RecentRecords';
import './index.less';

type FilterType = TimeFilter;

const UsageStatistics: React.FC = () => {
    // ===== 状态管理 =====
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [pullDistance, setPullDistance] = useState(0);

    // 下拉刷新相关 refs
    const containerRef = useRef<HTMLDivElement>(null);
    const startYRef = useRef(0);
    const isPullingRef = useRef(false);

    // 下拉刷新阈值（像素）
    const PULL_THRESHOLD = 60;
    const [requestStats, setRequestStats] = useState<StatCard[]>([]);
    const [usageStats, setUsageStats] = useState<StatCard[]>([]);
    const [toolUsageData, setToolUsageData] = useState<ToolUsageData[]>([]);
    const [tokenStatsRaw, setTokenStatsRaw] = useState<TokenStats | null>(null);

    const [toolFilter, setToolFilter] = useState<FilterType>('all');
    const [expandedTools, setExpandedTools] = useState<string[]>(['1', '2']);

    const filterOptions: {key: FilterType; label: string}[] = [
        {key: 'all', label: '全部'},
        {key: 'today', label: '今日'},
        {key: 'week', label: '本周'},
        {key: 'month', label: '本月'}
    ];

    // ===== 工具函数 =====
    const formatNumber = (num: number): string => {
        return num.toLocaleString();
    };

    const formatLargeNumber = (num: number): string => {
        if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
        if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
        return num.toLocaleString();
    };

    // 格式化百分比变化率
    const formatChangeRate = (rate: number): string => {
        const sign = rate >= 0 ? '+' : '';
        return `${sign}${rate.toFixed(1)}%`;
    };

    // 根据变化率计算上期数值
    const calculatePreviousValue = (current: number, changeRate: number): number => {
        // 特殊情况：上期值为0，本期有数据
        if (changeRate === 100.0 && current > 0) {
            return 0;
        }
        // 特殊情况：上期和本期都为0
        if (changeRate === 0 && current === 0) {
            return 0;
        }
        // 标准反推公式: previous = current / (1 + changeRate / 100)
        return Math.round(current / (1 + changeRate / 100));
    };

    const getIconColorClass = (color: string): string => {
        const colorMap: Record<string, string> = {
            blue: 'icon-blue',
            green: 'icon-green',
            red: 'icon-red',
            purple: 'icon-purple',
            orange: 'icon-orange',
            cyan: 'icon-cyan'
        };
        return colorMap[color] || 'icon-blue';
    };

    // ===== 数据获取 =====
    const fetchUsageData = async () => {
        try {
            setLoading(true);
            const response = await llmGateApi.getUsageOverview(toolFilter);

            const {request_stats, token_stats, tool_usage} = response.data;

            // 保存原始 token_stats 用于环比 Tooltip
            setTokenStatsRaw(token_stats);

            // 转换请求统计
            setRequestStats([
                {
                    icon: 'heroicons:chart-bar',
                    iconColor: 'blue',
                    value: formatLargeNumber(request_stats.total_requests),
                    label: '总请求数'
                },
                {
                    icon: 'heroicons:check-circle',
                    iconColor: 'green',
                    value: formatLargeNumber(request_stats.success_requests),
                    label: '成功请求'
                },
                {
                    icon: 'heroicons:x-circle',
                    iconColor: 'red',
                    value: formatLargeNumber(request_stats.error_requests),
                    label: '异常请求'
                }
            ]);

            // 转换Token统计（添加环比数据）
            setUsageStats([
                {
                    icon: 'heroicons:cube',
                    iconColor: 'purple',
                    value: formatLargeNumber(token_stats.total_tokens),
                    label: '总用量 (Tokens)'
                },
                {
                    icon: 'heroicons:calendar',
                    iconColor: 'orange',
                    value: formatLargeNumber(token_stats.month_tokens),
                    label: '近一个月用量 (Tokens)',
                    trend:
                        token_stats.month_change_rate !== undefined
                            ? {
                                  type: token_stats.month_change_rate >= 0 ? 'up' : 'down',
                                  value: formatChangeRate(token_stats.month_change_rate)
                              }
                            : undefined
                },
                {
                    icon: 'heroicons:clock',
                    iconColor: 'cyan',
                    value: formatLargeNumber(token_stats.today_tokens),
                    label: '今日用量 (Tokens)',
                    trend:
                        token_stats.today_change_rate !== undefined
                            ? {
                                  type: token_stats.today_change_rate >= 0 ? 'up' : 'down',
                                  value: formatChangeRate(token_stats.today_change_rate)
                              }
                            : undefined
                }
            ]);

            // 转换工具用量数据
            setToolUsageData(
                tool_usage.map((tool) => {
                    const toolIconInfo = getToolIcon(tool.tool_name);
                    return {
                        id: String(tool.tool_id),
                        name: tool.tool_name,
                        icon: toolIconInfo.icon,
                        iconBgColor: toolIconInfo.iconBgColor,
                        isImageUrl: toolIconInfo.isImageUrl,
                        routeCount: tool.route_count,
                        description: tool.description,
                        requestCount: tool.request_count,
                        tokenCount: formatLargeNumber(tool.total_tokens),
                        // 修复: usage_percentage 已是百分比形式(0-100)，无需再乘100
                        percentage: Math.min(Math.round(tool.usage_percentage), 100),
                        routes: tool.routes.map((route, rIndex) => ({
                            id: `${tool.tool_id}-${rIndex}`,
                            name: route.route_name,
                            modelName: route.model,
                            endpoint: route.api_path,
                            isActive: route.is_active,
                            requestCount: route.total_tokens
                        }))
                    };
                })
            );

            // 默认展开前两个工具
            if (tool_usage.length > 0) {
                const expandIds = tool_usage.slice(0, 2).map((t) => String(t.tool_id));
                setExpandedTools(expandIds);
            }
        } catch {
            message.error('获取统计数据失败');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchUsageData();
    }, [toolFilter]);

    // ===== 下拉刷新处理 =====
    const handleRefresh = useCallback(async () => {
        if (refreshing || loading) return;

        setRefreshing(true);
        try {
            await fetchUsageData();
            message.success('数据已刷新');
        } catch {
            // 错误已在 fetchUsageData 中处理
        } finally {
            setRefreshing(false);
            setPullDistance(0);
        }
    }, [refreshing, loading, toolFilter]);

    // 监听滚动容器的触摸/鼠标事件 - 使用 ref 避免频繁重建监听器
    useEffect(() => {
        const container = containerRef.current;
        if (!container) return;

        // 获取实际的滚动容器（父级的 .main-content）
        const scrollContainer = container.closest('.main-content') as HTMLElement;
        if (!scrollContainer) return;

        let isAtTop = true;
        let currentPullDistance = 0;

        const handleScroll = () => {
            isAtTop = scrollContainer.scrollTop <= 0;
        };

        const handleTouchStart = (e: TouchEvent) => {
            if (isAtTop) {
                startYRef.current = e.touches[0].clientY;
                isPullingRef.current = true;
            }
        };

        const handleTouchMove = (e: TouchEvent) => {
            if (!isPullingRef.current || !isAtTop) return;

            const currentY = e.touches[0].clientY;
            const diff = currentY - startYRef.current;

            if (diff > 0) {
                // 阻止默认滚动行为
                e.preventDefault();
                // 使用阻尼效果
                currentPullDistance = Math.min(diff * 0.5, PULL_THRESHOLD * 1.5);
                setPullDistance(currentPullDistance);
            }
        };

        const handleTouchEnd = () => {
            if (!isPullingRef.current) return;

            isPullingRef.current = false;

            if (currentPullDistance >= PULL_THRESHOLD) {
                // 触发刷新
                setRefreshing(true);
                fetchUsageData()
                    .then(() => {
                        message.success('数据已刷新');
                        setRefreshing(false);
                        setPullDistance(0);
                    })
                    .catch(() => {
                        setRefreshing(false);
                        setPullDistance(0);
                    });
            } else {
                setPullDistance(0);
            }
            currentPullDistance = 0;
        };

        // 鼠标事件支持（桌面端）
        const handleMouseDown = (e: MouseEvent) => {
            if (isAtTop) {
                startYRef.current = e.clientY;
                isPullingRef.current = true;
            }
        };

        const handleMouseMove = (e: MouseEvent) => {
            if (!isPullingRef.current || !isAtTop) return;

            const diff = e.clientY - startYRef.current;

            if (diff > 0) {
                currentPullDistance = Math.min(diff * 0.5, PULL_THRESHOLD * 1.5);
                setPullDistance(currentPullDistance);
            }
        };

        const handleMouseUp = () => {
            if (!isPullingRef.current) return;

            isPullingRef.current = false;

            if (currentPullDistance >= PULL_THRESHOLD) {
                // 触发刷新
                setRefreshing(true);
                fetchUsageData()
                    .then(() => {
                        message.success('数据已刷新');
                        setRefreshing(false);
                        setPullDistance(0);
                    })
                    .catch(() => {
                        setRefreshing(false);
                        setPullDistance(0);
                    });
            } else {
                setPullDistance(0);
            }
            currentPullDistance = 0;
        };

        // 添加事件监听 - 直接绑定到滚动容器上
        scrollContainer.addEventListener('scroll', handleScroll, {passive: true});
        scrollContainer.addEventListener('touchstart', handleTouchStart, {passive: true});
        scrollContainer.addEventListener('touchmove', handleTouchMove, {passive: false});
        scrollContainer.addEventListener('touchend', handleTouchEnd, {passive: true});
        scrollContainer.addEventListener('mousedown', handleMouseDown);
        window.addEventListener('mousemove', handleMouseMove);
        window.addEventListener('mouseup', handleMouseUp);

        // 初始检查滚动位置
        handleScroll();

        return () => {
            scrollContainer.removeEventListener('scroll', handleScroll);
            scrollContainer.removeEventListener('touchstart', handleTouchStart);
            scrollContainer.removeEventListener('touchmove', handleTouchMove);
            scrollContainer.removeEventListener('touchend', handleTouchEnd);
            scrollContainer.removeEventListener('mousedown', handleMouseDown);
            window.removeEventListener('mousemove', handleMouseMove);
            window.removeEventListener('mouseup', handleMouseUp);
        };
    }, []); // 空依赖数组，只在组件挂载时设置一次

    // ===== 交互处理 =====
    const toggleToolExpand = (toolId: string) => {
        setExpandedTools((prev) => (prev.includes(toolId) ? prev.filter((id) => id !== toolId) : [...prev, toolId]));
    };

    const handleToolFilterChange = (filter: FilterType) => {
        setToolFilter(filter);
    };

    // ===== 渲染环比 Tooltip 内容 =====
    const renderTrendTooltip = (label: string, stat: StatCard) => {
        if (!tokenStatsRaw || !stat.trend) return null;

        let current = 0;
        let previous = 0;
        let periodLabel = '';
        let previousPeriodLabel = '';

        if (label.includes('今日')) {
            current = tokenStatsRaw.today_tokens;
            previous = calculatePreviousValue(current, tokenStatsRaw.today_change_rate);
            periodLabel = '今日';
            previousPeriodLabel = '昨日';
        } else if (label.includes('月')) {
            current = tokenStatsRaw.month_tokens;
            previous = calculatePreviousValue(current, tokenStatsRaw.month_change_rate);
            periodLabel = '本月';
            previousPeriodLabel = '上月';
        }

        return (
            <div className='trend-tooltip-content'>
                <div className='tooltip-row'>
                    <span className='tooltip-label'>{periodLabel}用量:</span>
                    <span className='tooltip-value'>{formatLargeNumber(current)} Tokens</span>
                </div>
                <div className='tooltip-row'>
                    <span className='tooltip-label'>{previousPeriodLabel}用量:</span>
                    <span className='tooltip-value'>{formatLargeNumber(previous)} Tokens</span>
                </div>
                <div className='tooltip-row tooltip-change'>
                    <span className='tooltip-label'>环比变化:</span>
                    <span className={`tooltip-value ${stat.trend.type === 'up' ? 'up' : 'down'}`}>
                        {stat.trend.value}
                    </span>
                </div>
            </div>
        );
    };

    // ===== 渲染函数 =====
    const renderStatCard = (stat: StatCard, index: number) => {
        const cardContent = (
            <div className='stat-card' key={index}>
                <div className='stat-header'>
                    <div className={`stat-icon ${getIconColorClass(stat.iconColor)}`}>
                        <Icon icon={stat.icon} />
                    </div>
                    {stat.trend && (
                        <span className={`stat-trend ${stat.trend.type}`}>
                            <Icon
                                icon={
                                    stat.trend.type === 'up'
                                        ? 'heroicons:arrow-trending-up'
                                        : 'heroicons:arrow-trending-down'
                                }
                            />
                            {stat.trend.value}
                        </span>
                    )}
                </div>
                <div className='stat-value'>{stat.value}</div>
                <div className='stat-label'>{stat.label}</div>
            </div>
        );

        // 如果有趋势数据，包裹 Tooltip
        if (stat.trend) {
            return (
                <Tooltip
                    key={index}
                    title={renderTrendTooltip(stat.label, stat)}
                    placement='top'
                    classNames={{root: 'trend-tooltip'}}
                >
                    {cardContent}
                </Tooltip>
            );
        }

        return cardContent;
    };

    const renderToolUsageItem = (tool: ToolUsageData) => {
        const isExpanded = expandedTools.includes(tool.id);
        const progressBarClass = tool.name.includes('Claude')
            ? 'claude'
            : tool.name.includes('OpenAI')
              ? 'openai'
              : 'default';

        // 获取完整的工具图标配置（包含 iconColor）
        const toolIconInfo = getToolIcon(tool.name);

        return (
            <div key={tool.id} className='tool-usage-wrapper'>
                <div className='tool-usage-item' onClick={() => toggleToolExpand(tool.id)}>
                    <div className='tool-icon' style={{background: toolIconInfo.iconBgColor}}>
                        {toolIconInfo.isImageUrl ? (
                            <img
                                src={toolIconInfo.icon}
                                alt={tool.name}
                                style={{width: 24, height: 24, objectFit: 'contain'}}
                            />
                        ) : (
                            <Icon icon={toolIconInfo.icon} style={{color: toolIconInfo.iconColor}} />
                        )}
                    </div>
                    <div className='tool-info'>
                        <div className='tool-name'>{tool.name}</div>
                        <div className='tool-routes'>
                            {tool.routeCount} 个路由 · {tool.description}
                        </div>
                    </div>
                    <div className='tool-stats'>
                        <div className='tool-stat'>
                            <div className='tool-stat-value'>{formatNumber(tool.requestCount)}</div>
                            <div className='tool-stat-label'>请求数</div>
                        </div>
                        <div className='tool-stat'>
                            <div className='tool-stat-value'>{tool.tokenCount}</div>
                            <div className='tool-stat-label'>Tokens</div>
                        </div>
                    </div>
                    <div className='usage-bar-container'>
                        <div className='usage-bar-bg'>
                            <div className={`usage-bar ${progressBarClass}`} style={{width: `${tool.percentage}%`}} />
                        </div>
                        <div className='usage-percentage'>{tool.percentage}%</div>
                    </div>
                    <Icon
                        icon={isExpanded ? 'heroicons:chevron-up' : 'heroicons:chevron-down'}
                        className='expand-icon'
                    />
                </div>

                {/* 展开的路由详情 */}
                {isExpanded && (
                    <div className='route-details'>
                        {tool.routes.map((route) => {
                            const routeIconInfo = getModelProviderIcon(route.modelName);
                            return (
                                <div key={route.id} className='sub-route-item'>
                                    <div className='sub-route-info'>
                                        <div className='sub-route-icon' style={{color: routeIconInfo.color}}>
                                            <Icon icon={routeIconInfo.icon} />
                                        </div>
                                        <div>
                                            <div className='sub-route-name'>{route.name}</div>
                                            <div className='sub-route-model'>
                                                {route.endpoint} · {route.modelName}
                                            </div>
                                        </div>
                                    </div>
                                    <div className='sub-route-count'>{formatNumber(route.requestCount)}</div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        );
    };

    // ===== 渲染下拉刷新指示器 =====
    const renderPullRefreshIndicator = () => {
        if (!pullDistance && !refreshing) return null;

        const progress = Math.min(pullDistance / PULL_THRESHOLD, 1);
        const shouldRefresh = pullDistance >= PULL_THRESHOLD;
        const rotation = progress * 180;

        return (
            <div
                className={`pull-refresh-indicator ${refreshing ? 'refreshing' : ''} ${shouldRefresh ? 'ready' : ''}`}
                style={{
                    height: refreshing ? 50 : pullDistance,
                    opacity: refreshing ? 1 : Math.min(progress * 1.5, 1)
                }}
            >
                <div className='pull-refresh-content'>
                    {refreshing ? (
                        <>
                            <Spin size='small' />
                            <span className='pull-refresh-text'>刷新中...</span>
                        </>
                    ) : (
                        <>
                            <Icon
                                icon='heroicons:arrow-down'
                                className='pull-refresh-arrow'
                                style={{transform: `rotate(${rotation}deg)`}}
                            />
                            <span className='pull-refresh-text'>{shouldRefresh ? '松开刷新' : '下拉刷新数据'}</span>
                        </>
                    )}
                </div>
            </div>
        );
    };

    // ===== 渲染布局 =====
    return (
        <div className='usage-statistics' ref={containerRef}>
            {/* 下拉刷新指示器 */}
            {renderPullRefreshIndicator()}

            {loading ? (
                <div
                    className='loading-wrapper'
                    style={{minHeight: 200, display: 'flex', alignItems: 'center', justifyContent: 'center'}}
                >
                    <Spin tip='加载中...' />
                </div>
            ) : (
                <>
                    {/* 请求统计 */}
                    <div className='stats-section'>
                        <div className='section-header'>
                            <h2 className='section-title'>请求统计</h2>
                            <Button
                                type='text'
                                icon={<Icon icon='heroicons:arrow-path' className={refreshing ? 'spinning' : ''} />}
                                onClick={handleRefresh}
                                loading={refreshing}
                                className='refresh-btn'
                            >
                                同步数据
                            </Button>
                        </div>
                        <div className='stats-grid'>{requestStats.map(renderStatCard)}</div>
                    </div>

                    {/* 用量统计 */}
                    <div className='stats-section'>
                        <h2 className='section-title'>用量统计</h2>
                        <div className='stats-grid'>{usageStats.map(renderStatCard)}</div>
                    </div>

                    {/* 按工具分类使用量 */}
                    <div className='usage-section'>
                        <div className='usage-header'>
                            <h3 className='usage-title'>按工具分类使用量</h3>
                            <div className='filter-tabs'>
                                {filterOptions.map((option) => (
                                    <button
                                        key={option.key}
                                        className={`filter-tab ${toolFilter === option.key ? 'active' : ''}`}
                                        onClick={() => handleToolFilterChange(option.key)}
                                    >
                                        {option.label}
                                    </button>
                                ))}
                            </div>
                        </div>
                        <div className='tool-usage-list'>{toolUsageData.map(renderToolUsageItem)}</div>
                    </div>

                    {/* 最近请求记录 */}
                    <RecentRecords />
                </>
            )}
        </div>
    );
};

export default UsageStatistics;
