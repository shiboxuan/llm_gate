"""
连接测试路由 - LLM Provider 连通性测试

提供 Route 配置的连通性测试功能，用于用户在保存配置前验证配置是否正确。
"""
from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user, get_provider_key_service, get_connection_test_service
from app.core.exceptions import APIException
from app.core.error_codes import ErrorCode
from app.logger_mgr import get_logger
from app.schemas.test import ConnectionTestRequest, ConnectionTestResponse, ModelsProbeRequest, ModelsProbeResponse, ModelsProbeResultItem
from app.services.provider_key_service import ProviderKeyService
from app.services.connection_test_service import ConnectionTestService

logger = get_logger("app.api.control_plane.test")

router = APIRouter()


@router.post("/connection", response_model=ConnectionTestResponse)
async def test_connection(request: ConnectionTestRequest, current_user=Depends(get_current_user), provider_key_service: ProviderKeyService = Depends(get_provider_key_service), connection_test_service: ConnectionTestService = Depends(get_connection_test_service)) -> ConnectionTestResponse:
    """
    测试 LLM Provider 连通性

    在保存 Route 配置前，验证配置是否正确。
    发送一个简单的测试请求到目标 Provider，检查连接是否正常。

    认证方式：
    - 需要用户 JWT Token

    请求参数：
    - api_type: API 类型（openai_chat, anthropic_messages 等）
    - base_url: API 基础 URL
    - model: 模型名称
    - provider_key_name: Provider Key 名称（用于获取 API Key）
    """
    # 1. 获取用户的 Provider Key
    api_key = await provider_key_service.get_decrypted_key_by_name(current_user.id, request.provider_key_name)
    if not api_key:
        raise APIException(code=ErrorCode.PROVIDER_KEY_NOT_FOUND, message=f"Provider Key '{request.provider_key_name}' 不存在")

    # 2. 执行连接测试
    result = await connection_test_service.test_connection(api_type=request.api_type, base_url=request.base_url, model=request.model, api_key=api_key)

    # 3. 构建响应
    response = ConnectionTestResponse(success=result.success, message=result.message, latency_ms=result.latency_ms, error_code=result.error_code, details=result.details)
    return response


@router.post("/models", response_model=ModelsProbeResponse)
async def probe_models(request: ModelsProbeRequest, current_user=Depends(get_current_user), provider_key_service: ProviderKeyService = Depends(get_provider_key_service), connection_test_service: ConnectionTestService = Depends(get_connection_test_service)) -> ModelsProbeResponse:
    """
    批量探测 Provider 支持的模型列表

    对每个 base_url 调用 GET /models 端点，返回各自的探测结果。
    单个失败不影响其他结果。

    认证方式：
    - 需要用户 JWT Token

    请求参数：
    - targets: 探测目标列表，每个包含 base_url 和 provider_key_name
    """
    results = []

    for target in request.targets:
        try:
            # 1. 获取解密的 API Key
            api_key = await provider_key_service.get_decrypted_key_by_name(current_user.id, target.provider_key_name)

            if not api_key:
                # provider_key 不存在，记录失败但继续处理其他目标
                item = ModelsProbeResultItem(base_url=target.base_url, success=False, message=f"Provider Key '{target.provider_key_name}' 不存在", error_code="PROVIDER_KEY_NOT_FOUND")
                results.append(item)
                continue

            # 2. 调用探测服务
            result = await connection_test_service.probe_models(base_url=target.base_url, api_key=api_key)

            item = ModelsProbeResultItem(base_url=result.base_url, success=result.success, message=result.message, latency_ms=result.latency_ms, data=result.data, error_code=result.error_code)
            results.append(item)

        except Exception as e:
            # 单个探测异常不影响其他探测
            logger.exception(f"[probe_models] 探测 {target.base_url} 时发生异常: {e}")
            item = ModelsProbeResultItem(base_url=target.base_url, success=False, message=f"探测异常：{str(e)}", error_code="INTERNAL_ERROR")
            results.append(item)

    response = ModelsProbeResponse(results=results)
    return response
