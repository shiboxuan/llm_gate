"""
工具管理路由 - 工具 CRUD 和路由管理

提供工具的创建、查询、更新、删除，以及路由的增删改和激活切换
"""
from typing import List

from fastapi import APIRouter, Depends, status

from app.core.dependencies import get_current_user, get_tool_service, get_route_service, get_cache_service
from app.core.exceptions import APIException
from app.core.error_codes import ErrorCode
from app.schemas.tool import ToolCreate, ToolResponse, ToolTokenResponse, ToolUpdate
from app.schemas.route import RouteCreate, RouteUpdate, RouteResponse, RouteConfigSchema, RouteReorderRequest
from app.services.tool_service import ToolService
from app.services.route_service import RouteService
from app.services.cache_service import CacheService
from app.models.tool import RouteConfig

router = APIRouter()


# ==================== 工具 CRUD ====================

@router.post("/", response_model=ToolTokenResponse, status_code=status.HTTP_201_CREATED)
async def create_tool(tool_data: ToolCreate, current_user=Depends(get_current_user), tool_service: ToolService = Depends(get_tool_service)) -> ToolTokenResponse:
    """
    创建工具
    
    创建成功后返回工具信息和明文Token。
    注意：明文Token仅在创建时返回一次，请妥善保存。
    """
    try:
        tool, token = await tool_service.create_tool(current_user.id, tool_data.model_dump())
    except ValueError as e:
        # 处理 (user_id, name) 联合唯一约束冲突
        raise APIException(code=ErrorCode.TOOL_NAME_DUPLICATE)
    
    # 转换 routes 为响应格式
    routes_response = _convert_routes_to_response(tool.routes, tool.active_route_name)
    
    response = ToolTokenResponse(id=tool.id, user_id=tool.user_id, name=tool.name, description=tool.description, api_type=tool.api_type, api_key=token, active_route_name=tool.active_route_name, routes=routes_response, status=tool.status, created_at=tool.created_at, updated_at=tool.updated_at)
    return response


@router.get("/", response_model=List[ToolResponse])
async def list_tools(current_user=Depends(get_current_user), tool_service: ToolService = Depends(get_tool_service)) -> List[ToolResponse]:
    """获取用户所有工具"""
    tools = await tool_service.get_tools_by_user(current_user.id)
    response = []
    for t in tools:
        routes_response = _convert_routes_to_response(t.routes, t.active_route_name)
        tool_response = ToolResponse(id=t.id, user_id=t.user_id, name=t.name, description=t.description, api_type=t.api_type, active_route_name=t.active_route_name, routes=routes_response, status=t.status, created_at=t.created_at, updated_at=t.updated_at)
        response.append(tool_response)
    return response


@router.get("/{tool_id}", response_model=ToolResponse)
async def get_tool(tool_id: int, current_user=Depends(get_current_user), tool_service: ToolService = Depends(get_tool_service)) -> ToolResponse:
    """获取工具详情"""
    tool = await tool_service.get_tool_by_id(tool_id)
    if not tool or tool.user_id != current_user.id:
        raise APIException(code=ErrorCode.TOOL_NOT_FOUND)
    
    routes_response = _convert_routes_to_response(tool.routes, tool.active_route_name)
    response = ToolResponse(id=tool.id, user_id=tool.user_id, name=tool.name, description=tool.description, api_type=tool.api_type, active_route_name=tool.active_route_name, routes=routes_response, status=tool.status, created_at=tool.created_at, updated_at=tool.updated_at)
    return response


@router.put("/{tool_id}", response_model=ToolResponse)
async def update_tool(tool_id: int, tool_data: ToolUpdate, current_user=Depends(get_current_user), tool_service: ToolService = Depends(get_tool_service), cache_service: CacheService = Depends(get_cache_service)) -> ToolResponse:
    """更新工具"""
    tool = await tool_service.get_tool_by_id(tool_id)
    if not tool or tool.user_id != current_user.id:
        raise APIException(code=ErrorCode.TOOL_NOT_FOUND)
    
    try:
        updated_tool = await tool_service.update_tool(tool_id, tool_data.model_dump(exclude_unset=True))
    except ValueError as e:
        # 处理 (user_id, name) 联合唯一约束冲突
        raise APIException(code=ErrorCode.TOOL_NAME_DUPLICATE)
    
    # 更新工具后使缓存失效（status、active_route_name 等字段变更都会影响路由配置）
    await cache_service.invalidate_route_config(tool.token_hash)
    
    routes_response = _convert_routes_to_response(updated_tool.routes, updated_tool.active_route_name)
    response = ToolResponse(id=updated_tool.id, user_id=updated_tool.user_id, name=updated_tool.name, description=updated_tool.description, api_type=updated_tool.api_type, active_route_name=updated_tool.active_route_name, routes=routes_response, status=updated_tool.status, created_at=updated_tool.created_at, updated_at=updated_tool.updated_at)
    return response


@router.delete("/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tool(tool_id: int, current_user=Depends(get_current_user), tool_service: ToolService = Depends(get_tool_service), cache_service: CacheService = Depends(get_cache_service)):
    """删除工具"""
    tool = await tool_service.get_tool_by_id(tool_id)
    if not tool or tool.user_id != current_user.id:
        raise APIException(code=ErrorCode.TOOL_NOT_FOUND)
    
    # 使缓存失效
    await cache_service.invalidate_route_config(tool.token_hash)
    
    await tool_service.delete_tool(tool_id)


@router.post("/{tool_id}/regenerate-key", response_model=ToolTokenResponse)
async def regenerate_tool_key(tool_id: int, current_user=Depends(get_current_user), tool_service: ToolService = Depends(get_tool_service), cache_service: CacheService = Depends(get_cache_service)) -> ToolTokenResponse:
    """重新生成工具Token"""
    tool = await tool_service.get_tool_by_id(tool_id)
    if not tool or tool.user_id != current_user.id:
        raise APIException(code=ErrorCode.TOOL_NOT_FOUND)
    
    old_hash = tool.token_hash
    updated_tool, new_token = await tool_service.regenerate_tool_token(tool_id)
    
    # 使旧缓存失效
    await cache_service.invalidate_route_config(old_hash)
    
    routes_response = _convert_routes_to_response(updated_tool.routes, updated_tool.active_route_name)
    response = ToolTokenResponse(id=updated_tool.id, user_id=updated_tool.user_id, name=updated_tool.name, description=updated_tool.description, api_type=updated_tool.api_type, api_key=new_token, active_route_name=updated_tool.active_route_name, routes=routes_response, status=updated_tool.status, created_at=updated_tool.created_at, updated_at=updated_tool.updated_at)
    return response


# ==================== 路由管理 ====================

@router.post("/{tool_id}/routes", response_model=ToolResponse)
async def add_route(tool_id: int, route_data: RouteCreate, current_user=Depends(get_current_user), tool_service: ToolService = Depends(get_tool_service), route_service: RouteService = Depends(get_route_service), cache_service: CacheService = Depends(get_cache_service)) -> ToolResponse:
    """添加路由"""
    tool = await tool_service.get_tool_by_id(tool_id)
    if not tool or tool.user_id != current_user.id:
        raise APIException(code=ErrorCode.TOOL_NOT_FOUND)
    
    # 检查路由名称是否已存在
    if route_data.name in tool.routes:
        raise APIException(code=ErrorCode.ROUTE_NAME_DUPLICATE)

    # 创建路由配置（v3.0 api_type 已移至 Tool 级别）
    route_config = RouteConfig(base_url=route_data.base_url, model=route_data.model, provider_key_name=route_data.provider_key_name)

    updated_tool = await route_service.add_route(tool_id, route_data.name, route_config, order=route_data.order)
    
    # 如果设置为活跃路由
    if route_data.set_active:
        updated_tool = await route_service.activate_route(tool_id, route_data.name)
        # 切换激活路由后使缓存失效
        await cache_service.invalidate_route_config(tool.token_hash)
    
    routes_response = _convert_routes_to_response(updated_tool.routes, updated_tool.active_route_name)
    response = ToolResponse(id=updated_tool.id, user_id=updated_tool.user_id, name=updated_tool.name, description=updated_tool.description, api_type=updated_tool.api_type, active_route_name=updated_tool.active_route_name, routes=routes_response, status=updated_tool.status, created_at=updated_tool.created_at, updated_at=updated_tool.updated_at)
    return response


@router.put("/{tool_id}/routes/reorder", response_model=ToolResponse)
async def reorder_routes(tool_id: int, reorder_data: RouteReorderRequest, current_user=Depends(get_current_user), tool_service: ToolService = Depends(get_tool_service), route_service: RouteService = Depends(get_route_service)) -> ToolResponse:
    """批量更新路由排序"""
    tool = await tool_service.get_tool_by_id(tool_id)
    if not tool or tool.user_id != current_user.id:
        raise APIException(code=ErrorCode.TOOL_NOT_FOUND)

    # 验证所有 route_name 都存在
    for route_name in reorder_data.orders.keys():
        if route_name not in tool.routes:
            raise APIException(code=ErrorCode.ROUTE_NOT_FOUND, message=f"路由 '{route_name}' 不存在")

    updated_tool = await route_service.reorder_routes(tool_id, reorder_data.orders)

    routes_response = _convert_routes_to_response(updated_tool.routes, updated_tool.active_route_name)
    response = ToolResponse(id=updated_tool.id, user_id=updated_tool.user_id, name=updated_tool.name, description=updated_tool.description, api_type=updated_tool.api_type, active_route_name=updated_tool.active_route_name, routes=routes_response, status=updated_tool.status, created_at=updated_tool.created_at, updated_at=updated_tool.updated_at)
    return response


@router.put("/{tool_id}/routes/{route_name:path}", response_model=ToolResponse)
async def update_route(tool_id: int, route_name: str, route_data: RouteUpdate, current_user=Depends(get_current_user), tool_service: ToolService = Depends(get_tool_service), route_service: RouteService = Depends(get_route_service), cache_service: CacheService = Depends(get_cache_service)) -> ToolResponse:
    """更新路由"""
    tool = await tool_service.get_tool_by_id(tool_id)
    if not tool or tool.user_id != current_user.id:
        raise APIException(code=ErrorCode.TOOL_NOT_FOUND)
    
    if route_name not in tool.routes:
        raise APIException(code=ErrorCode.ROUTE_NOT_FOUND)
    
    # 获取现有配置并合并更新（v3.0 api_type 已移至 Tool 级别）
    existing_config = tool.routes[route_name]
    update_data = route_data.model_dump(exclude_unset=True)

    new_config = RouteConfig(
        base_url=update_data.get("base_url", existing_config.base_url),
        model=update_data.get("model", existing_config.model),
        provider_key_name=update_data.get("provider_key_name", existing_config.provider_key_name),
        order=update_data.get("order", existing_config.order)
    )
    
    updated_tool = await route_service.update_route(tool_id, route_name, new_config)
    
    # 如果更新的是激活路由，使缓存失效
    if tool.active_route_name == route_name:
        await cache_service.invalidate_route_config(tool.token_hash)
    
    routes_response = _convert_routes_to_response(updated_tool.routes, updated_tool.active_route_name)
    response = ToolResponse(id=updated_tool.id, user_id=updated_tool.user_id, name=updated_tool.name, description=updated_tool.description, api_type=updated_tool.api_type, active_route_name=updated_tool.active_route_name, routes=routes_response, status=updated_tool.status, created_at=updated_tool.created_at, updated_at=updated_tool.updated_at)
    return response


@router.delete("/{tool_id}/routes/{route_name:path}", response_model=ToolResponse)
async def delete_route(tool_id: int, route_name: str, current_user=Depends(get_current_user), tool_service: ToolService = Depends(get_tool_service), route_service: RouteService = Depends(get_route_service)) -> ToolResponse:
    """删除路由"""
    tool = await tool_service.get_tool_by_id(tool_id)
    if not tool or tool.user_id != current_user.id:
        raise APIException(code=ErrorCode.TOOL_NOT_FOUND)
    
    if route_name not in tool.routes:
        raise APIException(code=ErrorCode.ROUTE_NOT_FOUND)
    
    # 如果删除的是激活路由，不允许删除
    if tool.active_route_name == route_name:
        raise APIException(code=ErrorCode.ROUTE_DELETE_FAILED, message="不能删除激活路由")
    
    updated_tool = await route_service.delete_route(tool_id, route_name)
    
    routes_response = _convert_routes_to_response(updated_tool.routes, updated_tool.active_route_name)
    response = ToolResponse(id=updated_tool.id, user_id=updated_tool.user_id, name=updated_tool.name, description=updated_tool.description, api_type=updated_tool.api_type, active_route_name=updated_tool.active_route_name, routes=routes_response, status=updated_tool.status, created_at=updated_tool.created_at, updated_at=updated_tool.updated_at)
    return response


@router.put("/{tool_id}/activate/{route_name:path}", response_model=ToolResponse)
async def activate_route(tool_id: int, route_name: str, current_user=Depends(get_current_user), tool_service: ToolService = Depends(get_tool_service), route_service: RouteService = Depends(get_route_service), cache_service: CacheService = Depends(get_cache_service)) -> ToolResponse:
    """切换激活路由"""
    tool = await tool_service.get_tool_by_id(tool_id)
    if not tool or tool.user_id != current_user.id:
        raise APIException(code=ErrorCode.TOOL_NOT_FOUND)
    
    if route_name not in tool.routes:
        raise APIException(code=ErrorCode.ROUTE_NOT_FOUND)
    
    updated_tool = await route_service.activate_route(tool_id, route_name)
    
    # 切换路由后需要使缓存失效
    await cache_service.invalidate_route_config(tool.token_hash)
    
    routes_response = _convert_routes_to_response(updated_tool.routes, updated_tool.active_route_name)
    response = ToolResponse(id=updated_tool.id, user_id=updated_tool.user_id, name=updated_tool.name, description=updated_tool.description, api_type=updated_tool.api_type, active_route_name=updated_tool.active_route_name, routes=routes_response, status=updated_tool.status, created_at=updated_tool.created_at, updated_at=updated_tool.updated_at)
    return response


# ==================== 辅助函数 ====================

def _convert_routes_to_response(routes: dict, active_route_name: str = None) -> List[RouteResponse]:
    """将路由字典转换为响应格式（v3.0 api_type 已移至 Tool 级别）"""
    result = []
    for name, config in routes.items():
        is_active = (name == active_route_name)
        if isinstance(config, RouteConfig):
            route_response = RouteResponse(name=name, base_url=config.base_url, model=config.model, provider_key_name=config.provider_key_name, is_active=is_active, order=config.order)
        else:
            # 兼容旧数据
            route_response = RouteResponse(name=name, base_url=config.get("base_url", ""), model=config.get("model", ""), provider_key_name=config.get("provider_key_name", ""), is_active=is_active, order=config.get("order", 0))
        result.append(route_response)
    # 按 order 升序排序
    return sorted(result, key=lambda x: x.order)
