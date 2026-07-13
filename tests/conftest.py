"""
测试配置和共享 Fixtures

提供所有测试文件共享的 fixtures
支持两种测试模式：
    - mock: 使用测试数据库（LLM_GATE_TEST_DATABASE_URL），不需要真实 LLM API（默认）
    - develop: 使用真实 API 请求，连接 LLM_GATE_DATABASE_URL 数据库

使用方式：
    pytest tests/ --test-mode=mock      # Mock 模式（默认）
    pytest tests/ --test-mode=develop   # Develop 模式（真实 API）

安全检测：
    - develop 模式下会自动检测环境变量 LLM_GATE_DEBUG，确保为 true
    - 如果不是 debug 环境，测试将被拒绝执行，防止线上数据污染
"""
import os
import uuid
import pytest
import asyncio
from unittest.mock import AsyncMock

from httpx import AsyncClient, ASGITransport

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.orm import Base
from app.services.user_service import UserService
from app.services.tool_service import ToolService
from app.services.route_service import RouteService
from app.services.provider_key_service import ProviderKeyService
from app.services.cache_service import CacheService
from app.services.usage_service import UsageService
from app.core.security import create_access_token, hash_password
from app.models.user import User
from app.models.tool import Tool, RouteConfig


# ==================== 环境安全检测 ====================

def _check_debug_environment() -> tuple[bool, str]:
    """
    检测当前是否为 debug 环境

    检查环境变量 LLM_GATE_DEBUG 是否为 true

    Returns:
        tuple[bool, str]: (是否为debug环境, 错误信息)
    """
    debug_value = os.environ.get("LLM_GATE_DEBUG")
    if debug_value is None:
        return False, "环境变量 LLM_GATE_DEBUG 未设置"
    is_debug = debug_value.lower() in ("true", "1", "yes")
    if not is_debug:
        return False, f"LLM_GATE_DEBUG={debug_value}，当前不是 debug 环境"
    return True, ""


# ==================== pytest 命令行选项 ====================

def pytest_addoption(parser):
    """添加命令行参数"""
    parser.addoption(
        "--test-mode",
        action="store",
        default="mock",
        choices=["mock", "develop"],
        help="测试模式: mock (使用测试数据库) 或 develop (使用真实 API)"
    )
    parser.addoption(
        "--skip-env-check",
        action="store_true",
        default=False,
        help="跳过环境安全检测（谨慎使用，仅用于特殊场景）"
    )
    parser.addoption(
        "--openai-api-key",
        action="store",
        default=None,
        help="OpenAI API Key，用于连接测试集成测试"
    )
    parser.addoption(
        "--anthropic-api-key",
        action="store",
        default=None,
        help="Anthropic API Key，用于连接测试集成测试"
    )


def pytest_configure(config):
    """配置 pytest"""
    # 注册自定义标记
    config.addinivalue_line("markers", "mock_only: 仅在 mock 模式下运行")
    config.addinivalue_line("markers", "develop_only: 仅在 develop 模式下运行")
    config.addinivalue_line("markers", "integration: 集成测试（使用真实 API）")

    # 获取测试模式
    test_mode = config.getoption("--test-mode", default="mock")
    skip_env_check = config.getoption("--skip-env-check", default=False)

    # develop 模式下进行环境安全检测
    if test_mode == "develop" and not skip_env_check:
        is_debug, error_msg = _check_debug_environment()

        if not is_debug:
            raise pytest.UsageError(
                f"\n"
                f"{'=' * 70}\n"
                f"⚠️  环境安全检测失败 - 测试已终止\n"
                f"{'=' * 70}\n"
                f"\n"
                f"错误原因: {error_msg}\n"
                f"\n"
                f"当前 develop 模式会连接真实数据库，为防止线上数据污染，\n"
                f"必须确保环境变量 LLM_GATE_DEBUG=true。\n"
                f"\n"
                f"解决方案:\n"
                f"  1. 确认 LLM_GATE_DEBUG 环境变量设置为 true\n"
                f"  2. 或使用 mock 模式运行测试: pytest tests/ --test-mode=mock\n"
                f"  3. 如果确认环境安全，可使用 --skip-env-check 跳过检测（不推荐）\n"
                f"\n"
                f"{'=' * 70}"
            )
        else:
            print(f"\n✅ 环境安全检测通过: LLM_GATE_DEBUG=true\n")


def pytest_collection_modifyitems(config, items):
    """根据测试模式过滤测试用例"""
    test_mode = config.getoption("--test-mode")

    skip_mock = pytest.mark.skip(reason="仅在 mock 模式下运行")
    skip_develop = pytest.mark.skip(reason="仅在 develop 模式下运行")

    for item in items:
        if "mock_only" in item.keywords and test_mode != "mock":
            item.add_marker(skip_mock)
        if "develop_only" in item.keywords and test_mode != "develop":
            item.add_marker(skip_develop)
        if "integration" in item.keywords and test_mode != "develop":
            item.add_marker(skip_develop)


@pytest.fixture(scope="session")
def test_mode(request):
    """获取当前测试模式"""
    mode = request.config.getoption("--test-mode")
    return mode


# ==================== 事件循环 ====================

@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环（session 级别复用）"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ==================== 测试数据库会话 ====================

@pytest.fixture
async def db_session(test_mode):
    """
    创建测试数据库会话

    mock 模式连接 LLM_GATE_TEST_DATABASE_URL（默认本地测试 PG），
    develop 模式连接 LLM_GATE_DATABASE_URL。
    如果数据库不可用，跳过测试。
    """
    if test_mode == "mock":
        db_url = os.environ.get(
            "LLM_GATE_TEST_DATABASE_URL",
            "postgresql+asyncpg://llm_gate:llm_gate@localhost:5432/llm_gate_test"
        )
    else:
        db_url = os.environ.get(
            "LLM_GATE_DATABASE_URL",
            "postgresql+asyncpg://llm_gate:llm_gate@localhost:5432/llm_gate"
        )

    engine = None
    try:
        engine = create_async_engine(db_url, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            yield session
    except Exception as e:
        pytest.skip(f"测试数据库不可用，跳过测试: {e}")
    finally:
        if engine is not None:
            await engine.dispose()


# ==================== Mock Redis ====================

@pytest.fixture
def mock_redis() -> AsyncMock:
    """
    创建 Mock Redis 客户端

    用于 CacheService 测试
    """
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    return redis


# ==================== 服务层 Fixtures ====================

@pytest.fixture
async def user_service(db_session) -> UserService:
    """创建用户服务实例"""
    service = UserService(db_session)
    return service


@pytest.fixture
async def tool_service(db_session) -> ToolService:
    """创建工具服务实例"""
    service = ToolService(db_session)
    return service


@pytest.fixture
async def route_service(db_session) -> RouteService:
    """创建路由服务实例"""
    service = RouteService(db_session)
    return service


@pytest.fixture
async def provider_key_service(db_session) -> ProviderKeyService:
    """创建 Provider Key 服务实例"""
    service = ProviderKeyService(db_session)
    return service


@pytest.fixture
def cache_service(mock_redis) -> CacheService:
    """创建缓存服务实例"""
    service = CacheService(mock_redis)
    return service


@pytest.fixture
async def usage_service(db_session) -> UsageService:
    """创建用量统计服务实例"""
    service = UsageService(db_session)
    return service


# ==================== API 测试 Fixtures ====================

@pytest.fixture
def test_user() -> User:
    """
    创建测试用户对象

    用于 API 测试中的依赖注入
    """
    user = User(id="user_001", username="testuser", password_hash="$2b$12$fakehash", email="test@example.com", is_admin=False, status=1)
    return user


@pytest.fixture
def test_user_disabled() -> User:
    """创建被禁用的测试用户"""
    user = User(id="user_disabled", username="disabled_user", password_hash="$2b$12$fakehash", email="disabled@example.com", is_admin=False, status=0)
    return user


@pytest.fixture
def test_user_2() -> User:
    """创建第二个测试用户（用于权限测试）"""
    user = User(id="user_002", username="admin_user", password_hash="$2b$12$fakehash", email="admin@example.com", is_admin=True, status=1)
    return user


@pytest.fixture
def auth_token(test_user) -> str:
    """创建有效的 JWT Token"""
    token = create_access_token(data={"sub": test_user.id, "username": test_user.username, "is_admin": test_user.is_admin})
    return token


@pytest.fixture
def auth_token_user2(test_user_2) -> str:
    """创建第二个用户的 JWT Token"""
    token = create_access_token(data={"sub": test_user_2.id, "username": test_user_2.username, "is_admin": test_user_2.is_admin})
    return token


@pytest.fixture
def auth_headers(auth_token) -> dict:
    """创建带有认证的请求头"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    return headers


@pytest.fixture
def auth_headers_user2(auth_token_user2) -> dict:
    """创建第二个用户的认证请求头"""
    headers = {"Authorization": f"Bearer {auth_token_user2}"}
    return headers


@pytest.fixture
def expired_auth_headers() -> dict:
    """创建过期的认证请求头"""
    from datetime import timedelta
    token = create_access_token(data={"sub": "user_001", "username": "testuser", "is_admin": False}, expires_delta=timedelta(seconds=-1))
    headers = {"Authorization": f"Bearer {token}"}
    return headers


@pytest.fixture
def invalid_auth_headers() -> dict:
    """创建无效的认证请求头"""
    headers = {"Authorization": "Bearer invalid_token_string"}
    return headers


# ==================== 测试数据 Fixtures ====================

@pytest.fixture
def sample_user_data() -> dict:
    """示例用户数据（用于 create_user）"""
    data = {
        "id": f"user_{uuid.uuid4().hex[:12]}",
        "username": "fixture_user",
        "password_hash": hash_password("fixturepassword123"),
        "email": "fixture@example.com",
        "is_admin": False,
        "status": 1
    }
    return data


@pytest.fixture
def sample_tool_data() -> dict:
    """示例工具数据"""
    data = {
        "name": "Fixture测试工具",
        "description": "这是一个测试工具"
    }
    return data


@pytest.fixture
def sample_route_config() -> dict:
    """示例路由配置数据"""
    data = {
        "base_url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4",
        "provider_key_name": "openai_key"
    }
    return data


@pytest.fixture
def sample_route_create_data() -> dict:
    """示例创建路由请求数据"""
    data = {
        "name": "production",
        "base_url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4",
        "provider_key_name": "openai_key",
        "set_active": False
    }
    return data


@pytest.fixture
def sample_provider_key_data() -> dict:
    """示例 Provider Key 数据"""
    data = {
        "name": "openai_key",
        "api_key": "sk-test-api-key-12345"
    }
    return data


@pytest.fixture
def sample_register_data() -> dict:
    """示例注册数据"""
    data = {
        "username": "new_register_user",
        "password": "newpassword123",
        "email": "newregister@example.com"
    }
    return data


@pytest.fixture
def sample_login_data() -> dict:
    """示例登录数据"""
    data = {
        "username": "testloginuser",
        "password": "testpassword123"
    }
    return data


# ==================== 工具测试 Fixtures ====================

@pytest.fixture
def test_tool() -> Tool:
    """创建测试工具对象"""
    tool = Tool(
        id=1,
        user_id="user_001",
        name="测试工具",
        description="这是一个测试工具",
        token_hash="hash_abc123",
        active_route_name="default",
        routes={
            "default": RouteConfig(
                base_url="https://api.openai.com/v1/chat/completions",
                model="gpt-4",
                provider_key_name="openai_key"
            )
        },
        status=1
    )
    return tool


@pytest.fixture
def test_tool_with_multiple_routes() -> Tool:
    """创建带有多个路由的测试工具"""
    tool = Tool(
        id=2,
        user_id="user_001",
        name="多路由工具",
        description="带有多个路由的工具",
        token_hash="hash_multi123",
        active_route_name="production",
        routes={
            "production": RouteConfig(
                base_url="https://api.openai.com/v1/chat/completions",
                model="gpt-4",
                provider_key_name="openai_key"
            ),
            "development": RouteConfig(
                base_url="https://api.openai.com/v1/chat/completions",
                model="gpt-3.5-turbo",
                provider_key_name="openai_key_dev"
            ),
            "testing": RouteConfig(
                base_url="https://api.anthropic.com/v1/messages",
                model="claude-3-opus",
                provider_key_name="anthropic_key"
            )
        },
        status=1
    )
    return tool


# ==================== 辅助函数 ====================

@pytest.fixture
def create_test_user(user_service):
    """
    创建测试用户的辅助函数

    返回一个异步函数，可用于在测试中创建用户
    """
    async def _create_user(user_data: dict = None):
        if user_data is None:
            user_data = {
                "id": f"user_{uuid.uuid4().hex[:12]}",
                "username": f"testuser_{uuid.uuid4().hex[:8]}",
                "password_hash": hash_password("testpassword123"),
                "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
                "is_admin": False,
                "status": 1
            }
        return await user_service.create_user(user_data)
    return _create_user


@pytest.fixture
def create_test_tool(tool_service):
    """
    创建测试工具的辅助函数

    返回一个异步函数，可用于在测试中创建工具
    """
    async def _create_tool(user_id: str, tool_data: dict = None):
        if tool_data is None:
            tool_data = {"name": "测试工具", "description": "测试描述"}
        return await tool_service.create_tool(user_id, tool_data)
    return _create_tool


@pytest.fixture
def create_test_provider_key(provider_key_service):
    """
    创建测试 Provider Key 的辅助函数

    返回一个异步函数，可用于在测试中创建 Provider Key
    """
    async def _create_key(user_id: str, key_data: dict = None):
        if key_data is None:
            key_data = {"name": "test_key", "api_key": "sk-test-key-12345"}
        return await provider_key_service.create_provider_key(user_id, key_data)
    return _create_key


# ==================== Develop 模式专用 Fixtures ====================

@pytest.fixture(scope="session")
def api_base_url():
    """
    获取 API 基础 URL

    用于 develop 模式下的真实 API 测试
    默认使用本地开发服务器地址（run.py 启动在 0.0.0.0:9981）
    """
    url = os.environ.get("TEST_API_BASE_URL", "http://0.0.0.0:9981")
    return url


@pytest.fixture(scope="session")
async def async_client(api_base_url):
    """
    创建异步 HTTP 客户端（session 级别）

    用于 develop 模式下调用真实 API
    """
    async with AsyncClient(base_url=api_base_url, timeout=30.0) as client:
        yield client


@pytest.fixture
async def api_client(test_mode, api_base_url):
    """
    根据测试模式返回合适的客户端

    - mock 模式: 返回 TestClient（使用 ASGI Transport）
    - develop 模式: 返回 AsyncClient（真实 HTTP 请求）

    注意：启用 follow_redirects=True 以处理 FastAPI 的尾斜杠重定向（307）
    """
    if test_mode == "mock":
        from app.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as client:
            yield client
    else:
        async with AsyncClient(base_url=api_base_url, timeout=30.0, follow_redirects=True) as client:
            yield client


@pytest.fixture
async def develop_auth_headers(test_mode, api_client):
    """
    获取 develop 模式下的认证头

    通过真实 API 注册/登录获取 token
    """
    if test_mode == "mock":
        # Mock 模式使用预设的测试用户 token
        token = create_access_token(data={"sub": "user_001", "username": "testuser", "is_admin": False})
        headers = {"Authorization": f"Bearer {token}"}
        return headers

    # Develop 模式：通过注册 API 获取真实 token（已存在则登录）
    register_data = {
        "username": "develop_test_user",
        "password": "developpassword123",
        "email": "develop_test@example.com"
    }
    response = await api_client.post("/api/auth/register", json=register_data)
    if response.status_code == 409:
        # 用户已存在，改用登录
        login_data = {"username": "develop_test_user", "password": "developpassword123"}
        response = await api_client.post("/api/auth/login", json=login_data)
    assert response.status_code == 200, f"认证失败: {response.text}"
    data = response.json()
    token = data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return headers
