"""
集成测试工具类

提供测试输出格式化、随机数据生成、测试结果打印等功能
确保测试可在任何环境下重复运行
"""
import uuid
import string
import random
from datetime import datetime
from typing import Any, Dict, Optional
from dataclasses import dataclass
from enum import Enum


class TestStatus(Enum):
    """测试状态"""
    PASS = "✅ PASS"
    FAIL = "❌ FAIL"
    SKIP = "⏭️ SKIP"


@dataclass
class TestResult:
    """测试结果数据"""
    test_point: str
    request_params: Dict[str, Any]
    expected_result: Any
    actual_result: Any
    status: TestStatus
    error_message: Optional[str] = None


class TestPrinter:
    """
    测试打印工具
    
    格式化输出测试点、请求参数、期望结果、实际结果
    """
    
    SEPARATOR = "=" * 80
    SUB_SEPARATOR = "-" * 60
    
    @classmethod
    def print_test_header(cls, test_class: str, test_method: str):
        """打印测试头部"""
        print(f"\n{cls.SEPARATOR}")
        print(f"🧪 测试类: {test_class}")
        print(f"📋 测试方法: {test_method}")
        print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(cls.SEPARATOR)
    
    @classmethod
    def print_test_point(cls, test_point: str, description: str = ""):
        """打印测试点"""
        print(f"\n{cls.SUB_SEPARATOR}")
        print(f"🎯 测试点: {test_point}")
        if description:
            print(f"📝 说明: {description}")
        print(cls.SUB_SEPARATOR)
    
    @classmethod
    def print_request(cls, method: str, url: str, params: Dict[str, Any] = None, headers: Dict[str, str] = None, body: Dict[str, Any] = None):
        """打印请求信息"""
        print(f"\n📤 请求信息:")
        print(f"   方法: {method}")
        print(f"   URL: {url}")
        if params:
            print(f"   查询参数: {cls._format_dict(params)}")
        if headers:
            # 隐藏敏感信息
            safe_headers = cls._mask_sensitive_headers(headers)
            print(f"   请求头: {cls._format_dict(safe_headers)}")
        if body:
            # 隐藏敏感字段
            safe_body = cls._mask_sensitive_body(body)
            print(f"   请求体: {cls._format_dict(safe_body)}")
    
    @classmethod
    def print_expected(cls, expected: Any, description: str = ""):
        """打印期望结果"""
        print(f"\n📊 期望结果:")
        if description:
            print(f"   说明: {description}")
        print(f"   值: {cls._format_value(expected)}")
    
    @classmethod
    def print_actual(cls, actual: Any, status_code: int = None):
        """打印实际结果"""
        print(f"\n📋 实际结果:")
        if status_code is not None:
            print(f"   状态码: {status_code}")
        print(f"   响应: {cls._format_value(actual)}")
    
    @classmethod
    def print_result(cls, status: TestStatus, message: str = ""):
        """打印测试结果"""
        print(f"\n{status.value}")
        if message:
            print(f"   {message}")
    
    @classmethod
    def print_error(cls, error: Exception):
        """打印错误信息"""
        print(f"\n❌ 错误: {type(error).__name__}: {str(error)}")
    
    @classmethod
    def print_test_summary(cls, results: list):
        """打印测试摘要"""
        passed = sum(1 for r in results if r.status == TestStatus.PASS)
        failed = sum(1 for r in results if r.status == TestStatus.FAIL)
        skipped = sum(1 for r in results if r.status == TestStatus.SKIP)
        
        print(f"\n{cls.SEPARATOR}")
        print(f"📊 测试摘要")
        print(cls.SEPARATOR)
        print(f"   总计: {len(results)}")
        print(f"   通过: {passed} ✅")
        print(f"   失败: {failed} ❌")
        print(f"   跳过: {skipped} ⏭️")
        print(cls.SEPARATOR)
    
    @staticmethod
    def _format_dict(d: Dict, max_length: int = 200) -> str:
        """格式化字典，限制长度"""
        import json
        try:
            formatted = json.dumps(d, ensure_ascii=False, indent=2)
            if len(formatted) > max_length:
                return formatted[:max_length] + "..."
            return formatted
        except:
            return str(d)[:max_length]
    
    @staticmethod
    def _format_value(value: Any, max_length: int = 500) -> str:
        """格式化任意值"""
        import json
        try:
            if isinstance(value, dict):
                formatted = json.dumps(value, ensure_ascii=False, indent=2)
            elif isinstance(value, (list, tuple)):
                formatted = json.dumps(value, ensure_ascii=False, indent=2)
            else:
                formatted = str(value)
            
            if len(formatted) > max_length:
                return formatted[:max_length] + "..."
            return formatted
        except:
            return str(value)[:max_length]
    
    @staticmethod
    def _mask_sensitive_headers(headers: Dict[str, str]) -> Dict[str, str]:
        """隐藏敏感请求头"""
        sensitive_keys = ["authorization", "x-api-key", "api-key"]
        result = {}
        for k, v in headers.items():
            if k.lower() in sensitive_keys:
                if len(v) > 20:
                    result[k] = v[:10] + "****" + v[-6:]
                else:
                    result[k] = "****"
            else:
                result[k] = v
        return result
    
    @staticmethod
    def _mask_sensitive_body(body: Dict[str, Any]) -> Dict[str, Any]:
        """隐藏敏感请求体字段"""
        sensitive_keys = ["api_key", "password", "secret", "token"]
        result = {}
        for k, v in body.items():
            if any(sk in k.lower() for sk in sensitive_keys):
                if isinstance(v, str) and len(v) > 10:
                    result[k] = v[:6] + "****" + v[-4:]
                else:
                    result[k] = "****"
            else:
                result[k] = v
        return result


class RandomDataGenerator:
    """
    随机数据生成器
    
    生成唯一的测试数据，确保测试可重复运行
    """
    
    @staticmethod
    def unique_id(prefix: str = "") -> str:
        """生成唯一ID"""
        unique_part = uuid.uuid4().hex[:12]
        if prefix:
            return f"{prefix}_{unique_part}"
        return unique_part
    
    @staticmethod
    def username() -> str:
        """生成唯一用户名（符合 RegisterRequest 格式要求：字母数字下划线连字符）"""
        return f"testuser_{uuid.uuid4().hex[:8]}"

    @staticmethod
    def password() -> str:
        """生成测试密码（至少8位）"""
        return f"TestPass_{uuid.uuid4().hex[:8]}"
    
    @staticmethod
    def email(prefix: str = "test") -> str:
        """生成唯一邮箱"""
        return f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    
    @staticmethod
    def user_name(prefix: str = "测试用户") -> str:
        """生成唯一用户名"""
        return f"{prefix}_{uuid.uuid4().hex[:6]}"
    
    @staticmethod
    def tool_name(prefix: str = "测试工具") -> str:
        """生成唯一工具名"""
        return f"{prefix}_{uuid.uuid4().hex[:8]}"
    
    @staticmethod
    def provider_key_name(prefix: str = "test_key") -> str:
        """生成唯一Provider Key名称"""
        return f"{prefix}_{uuid.uuid4().hex[:8]}"
    
    @staticmethod
    def api_key() -> str:
        """生成模拟API Key"""
        return f"sk-test-{uuid.uuid4().hex}"
    
    @staticmethod
    def route_name(prefix: str = "route") -> str:
        """生成唯一路由名称"""
        return f"{prefix}_{uuid.uuid4().hex[:6]}"
    
    @staticmethod
    def random_string(length: int = 10, include_digits: bool = True) -> str:
        """生成随机字符串"""
        chars = string.ascii_letters
        if include_digits:
            chars += string.digits
        return ''.join(random.choices(chars, k=length))
    
    @staticmethod
    def random_int(min_val: int = 1, max_val: int = 1000) -> int:
        """生成随机整数"""
        return random.randint(min_val, max_val)


class TestDataFactory:
    """
    测试数据工厂
    
    生成各种测试所需的数据结构
    """
    
    @staticmethod
    def login_data(
        username: str = None,
        password: str = None
    ) -> Dict[str, Any]:
        """生成登录数据"""
        return {
            "username": username or RandomDataGenerator.username(),
            "password": password or RandomDataGenerator.password()
        }

    @staticmethod
    def register_data(
        username: str = None,
        password: str = None,
        email: str = None
    ) -> Dict[str, Any]:
        """生成注册数据"""
        return {
            "username": username or RandomDataGenerator.username(),
            "password": password or RandomDataGenerator.password(),
            "email": email or RandomDataGenerator.email()
        }
    
    @staticmethod
    def tool_data(
        name: str = None,
        description: str = None
    ) -> Dict[str, Any]:
        """生成工具数据"""
        return {
            "name": name or RandomDataGenerator.tool_name(),
            "description": description or "自动生成的测试工具描述"
        }
    
    @staticmethod
    def provider_key_data(
        name: str = None,
        api_key: str = None
    ) -> Dict[str, Any]:
        """生成Provider Key数据"""
        return {
            "name": name or RandomDataGenerator.provider_key_name(),
            "api_key": api_key or RandomDataGenerator.api_key()
        }
    
    @staticmethod
    def route_data(
        name: str = None,
        provider: str = "openai",
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4",
        provider_key_name: str = None,
        api_path: str = "/chat/completions",
        set_active: bool = False
    ) -> Dict[str, Any]:
        """生成路由数据"""
        return {
            "name": name or RandomDataGenerator.route_name(),
            "provider": provider,
            "base_url": base_url,
            "model": model,
            "provider_key_name": provider_key_name or RandomDataGenerator.provider_key_name(),
            "api_path": api_path,
            "set_active": set_active
        }
    
    @staticmethod
    def chat_completion_data(
        model: str = None,
        messages: list = None,
        stream: bool = False,
        max_tokens: int = 100
    ) -> Dict[str, Any]:
        """生成Chat Completion请求数据"""
        default_messages = [
            {"role": "user", "content": "Hello, this is a test message."}
        ]
        data = {
            "messages": messages or default_messages,
            "stream": stream,
            "max_tokens": max_tokens
        }
        if model:
            data["model"] = model
        return data


class AssertHelper:
    """
    断言辅助类
    
    提供带打印输出的断言方法
    """
    
    @staticmethod
    def assert_status_code(response, expected_codes, test_point: str = ""):
        """断言状态码"""
        if isinstance(expected_codes, int):
            expected_codes = [expected_codes]
        
        actual_code = response.status_code
        passed = actual_code in expected_codes
        
        TestPrinter.print_expected(
            f"状态码 in {expected_codes}",
            f"测试点: {test_point}" if test_point else ""
        )
        TestPrinter.print_actual(response.json() if response.text else {}, actual_code)
        
        if passed:
            TestPrinter.print_result(TestStatus.PASS, f"状态码 {actual_code} 符合期望")
        else:
            TestPrinter.print_result(TestStatus.FAIL, f"状态码 {actual_code} 不在期望范围 {expected_codes}")
        
        assert passed, f"期望状态码 {expected_codes}，实际 {actual_code}"
        return passed
    
    @staticmethod
    def assert_field_exists(data: dict, field: str, test_point: str = ""):
        """断言字段存在"""
        passed = field in data
        
        TestPrinter.print_expected(f"字段 '{field}' 存在", test_point)
        TestPrinter.print_actual(f"字段 '{field}' {'存在' if passed else '不存在'}")
        
        if passed:
            TestPrinter.print_result(TestStatus.PASS)
        else:
            TestPrinter.print_result(TestStatus.FAIL, f"响应中缺少字段 '{field}'")
        
        assert passed, f"响应中缺少字段 '{field}'"
        return passed
    
    @staticmethod
    def assert_field_value(data: dict, field: str, expected_value: Any, test_point: str = ""):
        """断言字段值"""
        actual_value = data.get(field)
        passed = actual_value == expected_value
        
        TestPrinter.print_expected(f"字段 '{field}' = {expected_value}", test_point)
        TestPrinter.print_actual(f"字段 '{field}' = {actual_value}")
        
        if passed:
            TestPrinter.print_result(TestStatus.PASS)
        else:
            TestPrinter.print_result(TestStatus.FAIL, f"字段值不匹配")
        
        assert passed, f"期望 {field}={expected_value}，实际 {actual_value}"
        return passed
    
    @staticmethod
    def assert_field_in_list(data: dict, field: str, expected_list: list, test_point: str = ""):
        """断言字段值在列表中"""
        actual_value = data.get(field)
        passed = actual_value in expected_list
        
        TestPrinter.print_expected(f"字段 '{field}' in {expected_list}", test_point)
        TestPrinter.print_actual(f"字段 '{field}' = {actual_value}")
        
        if passed:
            TestPrinter.print_result(TestStatus.PASS)
        else:
            TestPrinter.print_result(TestStatus.FAIL)
        
        assert passed, f"期望 {field} in {expected_list}，实际 {actual_value}"
        return passed
    
    @staticmethod
    def assert_list_not_empty(data: list, test_point: str = ""):
        """断言列表不为空"""
        passed = isinstance(data, list) and len(data) > 0
        
        TestPrinter.print_expected("列表不为空", test_point)
        TestPrinter.print_actual(f"列表长度: {len(data) if isinstance(data, list) else 'N/A'}")
        
        if passed:
            TestPrinter.print_result(TestStatus.PASS)
        else:
            TestPrinter.print_result(TestStatus.FAIL)
        
        assert passed, "列表为空或不是列表类型"
        return passed
    
    @staticmethod
    def assert_contains_item(data: list, field: str, value: Any, test_point: str = ""):
        """断言列表包含指定项"""
        passed = any(item.get(field) == value for item in data if isinstance(item, dict))
        
        TestPrinter.print_expected(f"列表包含 {field}={value} 的项", test_point)
        TestPrinter.print_actual(f"检查 {len(data)} 个项目")
        
        if passed:
            TestPrinter.print_result(TestStatus.PASS)
        else:
            TestPrinter.print_result(TestStatus.FAIL)
        
        assert passed, f"列表中未找到 {field}={value} 的项"
        return passed
