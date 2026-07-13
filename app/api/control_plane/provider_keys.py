"""
Provider Key 路由 - Provider Key 管理

提供 API 密钥的创建、查询、更新、删除功能
"""
from typing import List

from fastapi import APIRouter, Depends, status

from app.core.dependencies import get_current_user, get_provider_key_service, get_tool_service, get_cache_service
from app.core.exceptions import APIException
from app.core.error_codes import ErrorCode
from app.schemas.provider_key import ProviderKeyCreate, ProviderKeyUpdate, ProviderKeyResponse
from app.services.provider_key_service import ProviderKeyService
from app.services.tool_service import ToolService
from app.services.cache_service import CacheService

router = APIRouter()


@router.post("/", response_model=ProviderKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_provider_key(key_data: ProviderKeyCreate, current_user=Depends(get_current_user), provider_key_service: ProviderKeyService = Depends(get_provider_key_service)) -> ProviderKeyResponse:
    """
    创建Provider Key
    
    API Key将使用AES-256加密后存储。
    """
    # 检查同名密钥是否已存在
    existing = await provider_key_service.get_provider_key_by_name(current_user.id, key_data.name)
    if existing:
        raise APIException(code=ErrorCode.PROVIDER_KEY_NAME_DUPLICATE)
    
    provider_key = await provider_key_service.create_provider_key(current_user.id, key_data.model_dump())
    response = ProviderKeyResponse(id=provider_key.id, user_id=provider_key.user_id, name=provider_key.name, status=provider_key.status, created_at=provider_key.created_at)
    return response


@router.get("/", response_model=List[ProviderKeyResponse])
async def list_provider_keys(current_user=Depends(get_current_user), provider_key_service: ProviderKeyService = Depends(get_provider_key_service)) -> List[ProviderKeyResponse]:
    """获取用户所有Provider Keys"""
    keys = await provider_key_service.get_provider_keys_by_user(current_user.id)
    response = []
    for k in keys:
        key_response = ProviderKeyResponse(id=k.id, user_id=k.user_id, name=k.name, status=k.status, created_at=k.created_at)
        response.append(key_response)
    return response


@router.get("/{key_id}", response_model=ProviderKeyResponse)
async def get_provider_key(key_id: int, current_user=Depends(get_current_user), provider_key_service: ProviderKeyService = Depends(get_provider_key_service)) -> ProviderKeyResponse:
    """获取Provider Key详情"""
    provider_key = await provider_key_service.get_provider_key_by_id(key_id)
    if not provider_key or provider_key.user_id != current_user.id:
        raise APIException(code=ErrorCode.PROVIDER_KEY_NOT_FOUND)
    
    response = ProviderKeyResponse(id=provider_key.id, user_id=provider_key.user_id, name=provider_key.name, status=provider_key.status, created_at=provider_key.created_at)
    return response


@router.put("/{key_id}", response_model=ProviderKeyResponse)
async def update_provider_key(key_id: int, key_data: ProviderKeyUpdate, current_user=Depends(get_current_user), provider_key_service: ProviderKeyService = Depends(get_provider_key_service), tool_service: ToolService = Depends(get_tool_service), cache_service: CacheService = Depends(get_cache_service)) -> ProviderKeyResponse:
    """
    更新Provider Key
    
    更新 API Key 或状态后，所有使用该密钥的工具的缓存将被失效。
    """
    # 检查密钥是否存在且属于当前用户
    provider_key = await provider_key_service.get_provider_key_by_id(key_id)
    if not provider_key or provider_key.user_id != current_user.id:
        raise APIException(code=ErrorCode.PROVIDER_KEY_NOT_FOUND)
    
    # 更新密钥
    updated_key = await provider_key_service.update_provider_key(key_id, key_data.model_dump(exclude_unset=True))
    if not updated_key:
        raise APIException(code=ErrorCode.INTERNAL_ERROR, message="密钥更新失败")
    
    # 查找所有使用该 Provider Key 的工具并失效它们的缓存
    # 缓存中存储了解密后的 api_key，更新后需要重新加载
    affected_tools = await tool_service.get_tools_by_provider_key_name(current_user.id, provider_key.name)
    if affected_tools:
        token_hashes = [tool.token_hash for tool in affected_tools]
        await cache_service.invalidate_route_configs_batch(token_hashes)
    
    response = ProviderKeyResponse(id=updated_key.id, user_id=updated_key.user_id, name=updated_key.name, status=updated_key.status, created_at=updated_key.created_at)
    return response


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider_key(key_id: int, current_user=Depends(get_current_user), provider_key_service: ProviderKeyService = Depends(get_provider_key_service), tool_service: ToolService = Depends(get_tool_service), cache_service: CacheService = Depends(get_cache_service)):
    """
    删除Provider Key
    
    删除前会先失效所有使用该密钥的工具的缓存。
    注意：如果有工具正在使用该密钥，删除后这些工具将无法正常工作。
    """
    # 检查密钥是否存在且属于当前用户
    provider_key = await provider_key_service.get_provider_key_by_id(key_id)
    if not provider_key or provider_key.user_id != current_user.id:
        raise APIException(code=ErrorCode.PROVIDER_KEY_NOT_FOUND)
    
    # 查找所有使用该 Provider Key 的工具并失效它们的缓存
    # 这样做是为了确保缓存中不会残留已删除密钥的解密值
    affected_tools = await tool_service.get_tools_by_provider_key_name(current_user.id, provider_key.name)
    if affected_tools:
        token_hashes = [tool.token_hash for tool in affected_tools]
        await cache_service.invalidate_route_configs_batch(token_hashes)
    
    # 执行删除
    success = await provider_key_service.delete_provider_key(key_id)
    if not success:
        raise APIException(code=ErrorCode.INTERNAL_ERROR, message="密钥删除失败")
