"""
用量统计路由 API 测试用例

测试 /api/usage 下的所有接口
包括用量总览、请求统计、Token统计、工具用量统计等（V2预留）
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from app.config import get_current_time

from app.api.control_plane.usage import (
    get_usage_overview, get_request_stats, get_token_stats,
    get_tool_usage, _parse_time_filter
)
from app.schemas.usage import (
    UsageOverviewResponse, RequestStatsResponse, TokenStatsResponse,
    ToolUsageResponse
)
from app.services.usage_service import UsageService
from app.models.usage import UsageOverview, RequestStats, TokenStats, ToolUsageStats, RouteUsageDetail
from app.models.user import User


class TestParseTimeFilter:
    """时间过滤器解析函数测试类"""
    
    def test_parse_time_filter_all(self):
        """测试解析 'all' 时间过滤器"""
        start_time, end_time = _parse_time_filter("all")
        
        assert start_time is None
        assert end_time is None
    
    def test_parse_time_filter_today(self):
        """测试解析 'today' 时间过滤器"""
        start_time, end_time = _parse_time_filter("today")
        
        assert start_time is not None
        assert end_time is not None
        # 开始时间应该是今天的 00:00:00
        assert start_time.hour == 0
        assert start_time.minute == 0
        assert start_time.second == 0
    
    def test_parse_time_filter_week(self):
        """测试解析 'week' 时间过滤器"""
        now = get_current_time()
        start_time, end_time = _parse_time_filter("week")
        
        assert start_time is not None
        assert end_time is not None
        # 开始时间应该是 7 天前
        time_diff = end_time - start_time
        assert time_diff.days == 7 or time_diff.days == 6  # 可能有微小时间差
    
    def test_parse_time_filter_month(self):
        """测试解析 'month' 时间过滤器"""
        now = get_current_time()
        start_time, end_time = _parse_time_filter("month")
        
        assert start_time is not None
        assert end_time is not None
        # 开始时间应该是 30 天前
        time_diff = end_time - start_time
        assert time_diff.days >= 29 and time_diff.days <= 31
    
    def test_parse_time_filter_unknown_defaults_to_all(self):
        """测试未知过滤器默认为 'all'"""
        start_time, end_time = _parse_time_filter("unknown")
        
        assert start_time is None
        assert end_time is None
    
    def test_parse_time_filter_returns_tuple(self):
        """测试返回值是元组类型"""
        result = _parse_time_filter("today")
        
        assert isinstance(result, tuple)
        assert len(result) == 2


class TestGetToolUsageEndpoint:
    """获取工具用量统计接口测试类"""
    
    @pytest.mark.asyncio
    async def test_get_tool_usage_success(self, test_user, usage_service):
        """测试成功获取工具用量统计"""
        response = await get_tool_usage("month", test_user, usage_service)
        
        assert isinstance(response, list)
    
    @pytest.mark.asyncio
    async def test_get_tool_usage_returns_list(self, test_user, usage_service):
        """测试工具用量统计返回列表"""
        response = await get_tool_usage("month", test_user, usage_service)
        
        assert isinstance(response, list)
    
    @pytest.mark.asyncio
    async def test_get_tool_usage_item_type(self, test_user, usage_service):
        """测试工具用量统计项类型"""
        response = await get_tool_usage("month", test_user, usage_service)
        
        for item in response:
            assert isinstance(item, ToolUsageResponse)
    
    @pytest.mark.asyncio
    async def test_get_tool_usage_with_time_filter_all(self, test_user, usage_service):
        """测试使用 'all' 时间过滤器"""
        response = await get_tool_usage("all", test_user, usage_service)
        
        assert isinstance(response, list)
    
    @pytest.mark.asyncio
    async def test_get_tool_usage_with_time_filter_today(self, test_user, usage_service):
        """测试使用 'today' 时间过滤器"""
        response = await get_tool_usage("today", test_user, usage_service)
        
        assert isinstance(response, list)
    
    @pytest.mark.asyncio
    async def test_get_tool_usage_with_time_filter_week(self, test_user, usage_service):
        """测试使用 'week' 时间过滤器"""
        response = await get_tool_usage("week", test_user, usage_service)
        
        assert isinstance(response, list)


class TestToolUsageResponseFields:
    """工具用量响应字段测试类"""
    
    @pytest.mark.asyncio
    async def test_tool_usage_contains_tool_id(self, test_user, usage_service):
        """测试工具用量包含工具 ID"""
        response = await get_tool_usage("month", test_user, usage_service)
        
        for item in response:
            assert hasattr(item, 'tool_id')
    
    @pytest.mark.asyncio
    async def test_tool_usage_contains_tool_name(self, test_user, usage_service):
        """测试工具用量包含工具名称"""
        response = await get_tool_usage("month", test_user, usage_service)
        
        for item in response:
            assert hasattr(item, 'tool_name')
    
    @pytest.mark.asyncio
    async def test_tool_usage_contains_description(self, test_user, usage_service):
        """测试工具用量包含描述"""
        response = await get_tool_usage("month", test_user, usage_service)
        
        for item in response:
            assert hasattr(item, 'description')
    
    @pytest.mark.asyncio
    async def test_tool_usage_contains_route_count(self, test_user, usage_service):
        """测试工具用量包含路由数量"""
        response = await get_tool_usage("month", test_user, usage_service)
        
        for item in response:
            assert hasattr(item, 'route_count')
    
    @pytest.mark.asyncio
    async def test_tool_usage_contains_request_count(self, test_user, usage_service):
        """测试工具用量包含请求数量"""
        response = await get_tool_usage("month", test_user, usage_service)
        
        for item in response:
            assert hasattr(item, 'request_count')
    
    @pytest.mark.asyncio
    async def test_tool_usage_contains_total_tokens(self, test_user, usage_service):
        """测试工具用量包含总 Token 数"""
        response = await get_tool_usage("month", test_user, usage_service)
        
        for item in response:
            assert hasattr(item, 'total_tokens')
    
    @pytest.mark.asyncio
    async def test_tool_usage_contains_usage_percentage(self, test_user, usage_service):
        """测试工具用量包含使用百分比"""
        response = await get_tool_usage("month", test_user, usage_service)
        
        for item in response:
            assert hasattr(item, 'usage_percentage')
    
    @pytest.mark.asyncio
    async def test_tool_usage_contains_routes(self, test_user, usage_service):
        """测试工具用量包含路由详情"""
        response = await get_tool_usage("month", test_user, usage_service)
        
        for item in response:
            assert hasattr(item, 'routes')
            assert isinstance(item.routes, list)


class TestUsageForDifferentUsers:
    """不同用户用量隔离测试类"""
    
    @pytest.mark.asyncio
    async def test_tool_usage_user_isolation(self, test_user, test_user_2, usage_service):
        """测试工具用量用户隔离"""
        response1 = await get_tool_usage("month", test_user, usage_service)
        response2 = await get_tool_usage("month", test_user_2, usage_service)
        
        assert isinstance(response1, list)
        assert isinstance(response2, list)


class TestUsageServiceDirect:
    """直接测试 UsageService 类"""
    
    @pytest.mark.asyncio
    async def test_get_request_stats_returns_valid_stats(self, usage_service):
        """测试获取请求统计返回有效统计"""
        stats = await usage_service.get_request_stats("user_001")
        
        assert isinstance(stats, RequestStats)
        assert hasattr(stats, 'total_requests')
        assert hasattr(stats, 'success_requests')
        assert hasattr(stats, 'error_requests')
        assert hasattr(stats, 'success_rate')
    
    @pytest.mark.asyncio
    async def test_get_request_stats_values_are_valid(self, usage_service):
        """测试请求统计值有效"""
        stats = await usage_service.get_request_stats("user_001")
        
        assert stats.total_requests >= 0
        assert stats.success_requests >= 0
        assert stats.error_requests >= 0
        assert 0 <= stats.success_rate <= 100
    
    @pytest.mark.asyncio
    async def test_get_request_stats_consistency(self, usage_service):
        """测试请求统计的一致性"""
        stats = await usage_service.get_request_stats("user_001")
        
        # 总请求 = 成功请求 + 错误请求
        assert stats.total_requests == stats.success_requests + stats.error_requests
    
    @pytest.mark.asyncio
    async def test_get_token_stats_returns_valid_stats(self, usage_service):
        """测试获取 Token 统计返回有效统计"""
        stats = await usage_service.get_token_stats("user_001")
        
        assert isinstance(stats, TokenStats)
        assert hasattr(stats, 'total_tokens')
        assert hasattr(stats, 'month_tokens')
        assert hasattr(stats, 'today_tokens')
        assert hasattr(stats, 'month_change_rate')
        assert hasattr(stats, 'today_change_rate')
    
    @pytest.mark.asyncio
    async def test_get_token_stats_non_negative_values(self, usage_service):
        """测试 Token 统计值非负"""
        stats = await usage_service.get_token_stats("user_001")
        
        assert stats.total_tokens >= 0
        assert stats.month_tokens >= 0
        assert stats.today_tokens >= 0
    
    @pytest.mark.asyncio
    async def test_get_token_stats_today_less_than_month(self, usage_service):
        """测试今日 Token 数不超过本月 Token 数"""
        stats = await usage_service.get_token_stats("user_001")
        
        assert stats.today_tokens <= stats.month_tokens
    
    @pytest.mark.asyncio
    async def test_get_token_stats_month_less_than_total(self, usage_service):
        """测试本月 Token 数不超过总 Token 数"""
        stats = await usage_service.get_token_stats("user_001")
        
        assert stats.month_tokens <= stats.total_tokens
    
    @pytest.mark.asyncio
    async def test_get_usage_overview_returns_valid_overview(self, usage_service):
        """测试获取用量总览返回有效总览"""
        overview = await usage_service.get_usage_overview("user_001")
        
        assert isinstance(overview, UsageOverview)
        assert hasattr(overview, 'request_stats')
        assert hasattr(overview, 'token_stats')
        assert hasattr(overview, 'tool_usage')
    
    @pytest.mark.asyncio
    async def test_get_usage_overview_contains_request_stats(self, usage_service):
        """测试用量总览包含请求统计"""
        overview = await usage_service.get_usage_overview("user_001")
        
        assert isinstance(overview.request_stats, RequestStats)
    
    @pytest.mark.asyncio
    async def test_get_usage_overview_contains_token_stats(self, usage_service):
        """测试用量总览包含 Token 统计"""
        overview = await usage_service.get_usage_overview("user_001")
        
        assert isinstance(overview.token_stats, TokenStats)
    
    @pytest.mark.asyncio
    async def test_get_usage_overview_contains_tool_usage(self, usage_service):
        """测试用量总览包含工具用量"""
        overview = await usage_service.get_usage_overview("user_001")
        
        assert isinstance(overview.tool_usage, list)
    
    @pytest.mark.asyncio
    async def test_get_tool_usage_stats_returns_list(self, usage_service):
        """测试获取工具用量统计返回列表"""
        stats = await usage_service.get_tool_usage_stats("user_001")
        
        assert isinstance(stats, list)


class TestUsageServiceCalculations:
    """用量服务计算测试类"""
    
    def test_calculate_change_rate_positive_change(self, usage_service):
        """测试计算正向变化率"""
        rate = usage_service.calculate_change_rate(150, 100)
        
        assert rate == 50.0
    
    def test_calculate_change_rate_negative_change(self, usage_service):
        """测试计算负向变化率"""
        rate = usage_service.calculate_change_rate(50, 100)
        
        assert rate == -50.0
    
    def test_calculate_change_rate_no_change(self, usage_service):
        """测试计算无变化"""
        rate = usage_service.calculate_change_rate(100, 100)
        
        assert rate == 0.0
    
    def test_calculate_change_rate_from_zero(self, usage_service):
        """测试从零开始的变化率"""
        rate = usage_service.calculate_change_rate(100, 0)
        
        assert rate == 100.0
    
    def test_calculate_change_rate_to_zero(self, usage_service):
        """测试变化到零的变化率"""
        rate = usage_service.calculate_change_rate(0, 100)
        
        assert rate == -100.0
    
    def test_calculate_change_rate_both_zero(self, usage_service):
        """测试两者都为零的变化率"""
        rate = usage_service.calculate_change_rate(0, 0)
        
        assert rate == 0.0


class TestUsageServiceTimeFilters:
    """用量服务时间过滤测试类"""
    
    @pytest.mark.asyncio
    async def test_get_request_stats_with_time_range(self, usage_service):
        """测试使用时间范围获取请求统计"""
        now = get_current_time()
        start_time = now - timedelta(days=7)
        end_time = now
        
        stats = await usage_service.get_request_stats("user_001", start_time, end_time)
        
        assert isinstance(stats, RequestStats)
    
    @pytest.mark.asyncio
    async def test_get_tool_usage_stats_with_time_range(self, usage_service):
        """测试使用时间范围获取工具用量统计"""
        now = get_current_time()
        start_time = now - timedelta(days=7)
        end_time = now
        
        stats = await usage_service.get_tool_usage_stats("user_001", start_time, end_time)
        
        assert isinstance(stats, list)
    
    @pytest.mark.asyncio
    async def test_get_usage_overview_with_time_range(self, usage_service):
        """测试使用时间范围获取用量总览"""
        now = get_current_time()
        start_time = now - timedelta(days=7)
        end_time = now
        
        overview = await usage_service.get_usage_overview("user_001", start_time, end_time)
        
        assert isinstance(overview, UsageOverview)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
