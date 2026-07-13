"""
集成测试包

包含使用真实 API 的集成测试用例
这些测试仅在 develop 模式下运行：pytest tests/integration/ --test-mode=develop

注意：
- 集成测试会连接真实数据库（debug 数据库）
- 测试数据会写入 debug_ 前缀的表中
- 不影响生产数据库
- 线上第一次测试成功后会删库重建，所以测试数据不会保留

测试特点：
1. 每个测试都打印测试点、请求参数、期望结果、实际结果
   - 通过打印而不是看代码即可清晰了解测试过程
   
2. 测试数据使用随机字符生成，支持任何测试环境
   - 工具名、用户名等使用 UUID 确保唯一性
   - 无论多少次测试，只要接口逻辑正确，测试就是 pass
   
3. 全方位测试接口
   - 认证 API：登录、获取用户信息、Token 验证
   - Provider Keys API：CRUD、数据验证、授权
   - Tools API：CRUD、路由管理、激活切换
   - Chat API：流式/非流式响应、请求验证、参数传递

4. 支持 debug 和线上环境
   - 在 debug 数据库下测试成功
   - 线上环境也可以测试（数据会被清理）

使用方式：
    # 运行所有集成测试
    pytest tests/integration/ --test-mode=develop -v
    
    # 运行特定测试文件
    pytest tests/integration/test_auth_integration.py --test-mode=develop -v
    
    # 运行特定测试类
    pytest tests/integration/test_tools_integration.py::TestToolsCRUDIntegration --test-mode=develop -v
    
    # 运行特定测试方法
    pytest tests/integration/test_chat_integration.py::TestChatCompletionsStreamIntegration::test_chat_stream_request_forwarding --test-mode=develop -v

测试文件说明：
- test_utils.py: 测试工具类（打印、随机数据生成、断言辅助）
- test_auth_integration.py: 认证 API 集成测试
- test_provider_keys_integration.py: Provider Keys API 集成测试
- test_tools_integration.py: 工具管理 API 集成测试
- test_chat_integration.py: Chat Completions API 集成测试（流式/非流式）

前提条件：
1. 启动本地开发服务器: python run.py
2. 确保 debug 模式已开启（scripts/llm_gate_env.json 中 LLM_GATE_DEBUG=true）
3. 对于 Chat API 测试，需要配置有效的 Provider Key（如 OpenAI API Key）
"""

from tests.integration.test_utils import (
    TestPrinter,
    TestStatus,
    TestResult,
    RandomDataGenerator,
    TestDataFactory,
    AssertHelper
)

__all__ = [
    "TestPrinter",
    "TestStatus", 
    "TestResult",
    "RandomDataGenerator",
    "TestDataFactory",
    "AssertHelper"
]
