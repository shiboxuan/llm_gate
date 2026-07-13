#!/usr/bin/env python3
"""
Usage 对比测试脚本

测试目标：使用相同的提示词，通过不同的 API 端点发送请求，对比返回的 usage 数据。

支持的测试场景：
1. /chat/completions (OpenAI 格式)
2. /messages (Anthropic 格式 -> 转换模式)
3. /messages (Anthropic 格式 -> 原生模式，如果支持)

使用方式：
    # 设置环境变量
    export LLM_GATE_BASE_URL="http://localhost:3333"
    export LLM_GATE_TOOL_TOKEN_OPENAI="your-openai-tool-token"
    export LLM_GATE_TOOL_TOKEN_MESSAGES="your-messages-tool-token"
    
    # 运行测试
    python scripts/compare_usage_test.py
    
    # 或者直接通过参数传递
    python scripts/compare_usage_test.py \
        --base-url http://localhost:3333 \
        --openai-token xxx \
        --messages-token yyy

作者: LLM Gate Team
"""
import argparse
import asyncio
import json
import os
import sys
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

import httpx


@dataclass
class UsageResult:
    """用量结果"""
    endpoint: str
    api_type: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    response_text: str = ""
    raw_response: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class UsageComparisonTester:
    """Usage 对比测试器"""
    
    def __init__(self, base_url: str, openai_token: Optional[str] = None, messages_token: Optional[str] = None, anthropic_native_token: Optional[str] = None):
        """
        初始化测试器
        
        Args:
            base_url: LLM Gate 服务地址
            openai_token: 用于 /chat/completions 端点的 Tool Token
            messages_token: 用于 /messages 端点（格式转换模式）的 Tool Token
            anthropic_native_token: 用于 /messages 端点（原生模式）的 Tool Token
        """
        self.base_url = base_url.rstrip("/")
        self.openai_token = openai_token
        self.messages_token = messages_token
        self.anthropic_native_token = anthropic_native_token
        self.client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=120.0)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
    
    async def test_chat_completions(self, prompt: str, system_prompt: Optional[str] = None, stream: bool = False) -> UsageResult:
        """
        测试 /chat/completions 端点 (OpenAI 格式)
        
        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词（可选）
            stream: 是否使用流式响应
            
        Returns:
            UsageResult 对象
        """
        if not self.openai_token:
            return UsageResult(
                endpoint="/chat/completions",
                api_type="openai_chat",
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                error="未配置 openai_token"
            )
        
        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openai_token}",
            "Content-Type": "application/json"
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        body = {
            "model": "auto",  # 由路由配置决定实际模型
            "messages": messages,
            "max_tokens": 1000,
            "stream": stream
        }
        
        if stream:
            body["stream_options"] = {"include_usage": True}
        
        try:
            if stream:
                return await self._test_chat_stream(url, headers, body)
            else:
                return await self._test_chat_non_stream(url, headers, body)
        except Exception as e:
            return UsageResult(
                endpoint="/chat/completions",
                api_type="openai_chat",
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                error=str(e)
            )
    
    async def _test_chat_non_stream(self, url: str, headers: Dict, body: Dict) -> UsageResult:
        """非流式 chat/completions 测试"""
        response = await self.client.post(url, headers=headers, json=body)
        
        if response.status_code >= 400:
            return UsageResult(
                endpoint="/chat/completions",
                api_type="openai_chat",
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                error=f"HTTP {response.status_code}: {response.text[:500]}"
            )
        
        data = response.json()
        usage = data.get("usage", {})
        
        # 提取响应文本
        response_text = ""
        choices = data.get("choices", [])
        if choices:
            response_text = choices[0].get("message", {}).get("content", "")
        
        return UsageResult(
            endpoint="/chat/completions",
            api_type="openai_chat",
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            response_text=response_text,
            raw_response=data
        )
    
    async def _test_chat_stream(self, url: str, headers: Dict, body: Dict) -> UsageResult:
        """流式 chat/completions 测试"""
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        response_text = ""
        chunks = []
        
        async with self.client.stream("POST", url, headers=headers, json=body) as response:
            if response.status_code >= 400:
                error_body = await response.aread()
                return UsageResult(
                    endpoint="/chat/completions (stream)",
                    api_type="openai_chat",
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    error=f"HTTP {response.status_code}: {error_body.decode()[:500]}"
                )
            
            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    continue
                
                try:
                    chunk = json.loads(data_str)
                    chunks.append(chunk)
                    
                    # 收集响应文本
                    choices = chunk.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        if delta.get("content"):
                            response_text += delta.get("content")
                    
                    # 提取 usage（最后一个 chunk）
                    if chunk.get("usage"):
                        usage = chunk["usage"]
                        prompt_tokens = usage.get("prompt_tokens", 0)
                        completion_tokens = usage.get("completion_tokens", 0)
                        total_tokens = usage.get("total_tokens", 0)
                except json.JSONDecodeError:
                    continue
        
        return UsageResult(
            endpoint="/chat/completions (stream)",
            api_type="openai_chat",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            response_text=response_text,
            raw_response={"chunks_count": len(chunks), "last_chunk": chunks[-1] if chunks else {}}
        )
    
    async def test_messages(self, prompt: str, system_prompt: Optional[str] = None, stream: bool = False, native_mode: bool = False) -> UsageResult:
        """
        测试 /messages 端点 (Anthropic 格式)
        
        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词（可选）
            stream: 是否使用流式响应
            native_mode: 是否使用原生模式 Token（需要 anthropic_native_token）
            
        Returns:
            UsageResult 对象
        """
        token = self.anthropic_native_token if native_mode else self.messages_token
        mode_name = "原生模式" if native_mode else "转换模式"
        
        if not token:
            return UsageResult(
                endpoint=f"/messages ({mode_name})",
                api_type="anthropic_messages" if native_mode else "openai_chat",
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                error=f"未配置 {'anthropic_native_token' if native_mode else 'messages_token'}"
            )
        
        url = f"{self.base_url}/v1/messages"
        headers = {
            "x-api-key": token,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        body = {
            "model": "auto",  # 由路由配置决定实际模型
            "max_tokens": 1000,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "stream": stream
        }
        
        if system_prompt:
            body["system"] = system_prompt
        
        try:
            if stream:
                return await self._test_messages_stream(url, headers, body, native_mode)
            else:
                return await self._test_messages_non_stream(url, headers, body, native_mode)
        except Exception as e:
            return UsageResult(
                endpoint=f"/messages ({mode_name})",
                api_type="anthropic_messages" if native_mode else "openai_chat",
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                error=str(e)
            )
    
    async def _test_messages_non_stream(self, url: str, headers: Dict, body: Dict, native_mode: bool) -> UsageResult:
        """非流式 messages 测试"""
        mode_name = "原生模式" if native_mode else "转换模式"
        
        response = await self.client.post(url, headers=headers, json=body)
        
        if response.status_code >= 400:
            return UsageResult(
                endpoint=f"/messages ({mode_name})",
                api_type="anthropic_messages" if native_mode else "openai_chat",
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                error=f"HTTP {response.status_code}: {response.text[:500]}"
            )
        
        data = response.json()
        usage = data.get("usage", {})
        
        # Anthropic 格式使用 input_tokens/output_tokens
        prompt_tokens = usage.get("input_tokens", 0)
        completion_tokens = usage.get("output_tokens", 0)
        total_tokens = prompt_tokens + completion_tokens
        
        # 提取响应文本
        response_text = ""
        content = data.get("content", [])
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                response_text += block.get("text", "")
        
        return UsageResult(
            endpoint=f"/messages ({mode_name})",
            api_type="anthropic_messages" if native_mode else "openai_chat",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            response_text=response_text,
            raw_response=data
        )
    
    async def _test_messages_stream(self, url: str, headers: Dict, body: Dict, native_mode: bool) -> UsageResult:
        """流式 messages 测试"""
        mode_name = "原生模式" if native_mode else "转换模式"
        
        prompt_tokens = 0
        completion_tokens = 0
        response_text = ""
        chunks = []
        
        async with self.client.stream("POST", url, headers=headers, json=body) as response:
            if response.status_code >= 400:
                error_body = await response.aread()
                return UsageResult(
                    endpoint=f"/messages ({mode_name}, stream)",
                    api_type="anthropic_messages" if native_mode else "openai_chat",
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    error=f"HTTP {response.status_code}: {error_body.decode()[:500]}"
                )
            
            async for line in response.aiter_lines():
                if not line:
                    continue
                
                # 处理 SSE 格式
                if line.startswith("event:"):
                    continue
                
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if not data_str:
                        continue
                    
                    try:
                        chunk = json.loads(data_str)
                        chunks.append(chunk)
                        chunk_type = chunk.get("type")
                        
                        # message_start 包含 input_tokens
                        if chunk_type == "message_start":
                            message = chunk.get("message", {})
                            msg_usage = message.get("usage", {})
                            prompt_tokens = msg_usage.get("input_tokens", 0)
                        
                        # content_block_delta 包含文本
                        elif chunk_type == "content_block_delta":
                            delta = chunk.get("delta", {})
                            if delta.get("type") == "text_delta":
                                response_text += delta.get("text", "")
                        
                        # message_delta 包含 output_tokens
                        elif chunk_type == "message_delta":
                            delta_usage = chunk.get("usage", {})
                            completion_tokens = delta_usage.get("output_tokens", 0)
                    
                    except json.JSONDecodeError:
                        continue
        
        return UsageResult(
            endpoint=f"/messages ({mode_name}, stream)",
            api_type="anthropic_messages" if native_mode else "openai_chat",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            response_text=response_text,
            raw_response={"chunks_count": len(chunks)}
        )
    
    async def run_comparison(self, prompt: str, system_prompt: Optional[str] = None, test_stream: bool = True) -> List[UsageResult]:
        """
        运行完整的对比测试
        
        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词（可选）
            test_stream: 是否测试流式模式
            
        Returns:
            所有测试结果列表
        """
        results = []
        
        print(f"\n{'='*60}")
        print(f"测试提示词: {prompt[:100]}...")
        if system_prompt:
            print(f"系统提示词: {system_prompt[:100]}...")
        print(f"{'='*60}\n")
        
        # 测试 1: /chat/completions 非流式
        print("测试 1: /chat/completions (非流式)...")
        result = await self.test_chat_completions(prompt, system_prompt, stream=False)
        results.append(result)
        self._print_result(result)
        
        # 测试 2: /chat/completions 流式
        if test_stream:
            print("\n测试 2: /chat/completions (流式)...")
            result = await self.test_chat_completions(prompt, system_prompt, stream=True)
            results.append(result)
            self._print_result(result)
        
        # 测试 3: /messages 转换模式 非流式
        print("\n测试 3: /messages 转换模式 (非流式)...")
        result = await self.test_messages(prompt, system_prompt, stream=False, native_mode=False)
        results.append(result)
        self._print_result(result)
        
        # 测试 4: /messages 转换模式 流式
        if test_stream:
            print("\n测试 4: /messages 转换模式 (流式)...")
            result = await self.test_messages(prompt, system_prompt, stream=True, native_mode=False)
            results.append(result)
            self._print_result(result)
        
        # 测试 5: /messages 原生模式 非流式（如果配置了）
        if self.anthropic_native_token:
            print("\n测试 5: /messages 原生模式 (非流式)...")
            result = await self.test_messages(prompt, system_prompt, stream=False, native_mode=True)
            results.append(result)
            self._print_result(result)
            
            # 测试 6: /messages 原生模式 流式
            if test_stream:
                print("\n测试 6: /messages 原生模式 (流式)...")
                result = await self.test_messages(prompt, system_prompt, stream=True, native_mode=True)
                results.append(result)
                self._print_result(result)
        
        return results
    
    def _print_result(self, result: UsageResult):
        """打印单个测试结果"""
        if result.error:
            print(f"  ❌ 错误: {result.error}")
            return
        
        print(f"  端点: {result.endpoint}")
        print(f"  API类型: {result.api_type}")
        print(f"  ✅ Usage:")
        print(f"     - prompt_tokens: {result.prompt_tokens}")
        print(f"     - completion_tokens: {result.completion_tokens}")
        print(f"     - total_tokens: {result.total_tokens}")
        print(f"  响应长度: {len(result.response_text)} 字符")
        if result.response_text:
            print(f"  响应预览: {result.response_text[:100]}...")
    
    def print_comparison_summary(self, results: List[UsageResult]):
        """打印对比总结"""
        print(f"\n{'='*60}")
        print("对比总结")
        print(f"{'='*60}")
        
        # 过滤掉错误的结果
        valid_results = [r for r in results if not r.error]
        
        if not valid_results:
            print("没有成功的测试结果")
            return
        
        # 打印表格
        print(f"\n{'端点':<40} {'prompt':<10} {'completion':<12} {'total':<10}")
        print("-" * 72)
        
        for r in results:
            if r.error:
                print(f"{r.endpoint:<40} {'ERROR':<10} {'-':<12} {'-':<10}")
            else:
                print(f"{r.endpoint:<40} {r.prompt_tokens:<10} {r.completion_tokens:<12} {r.total_tokens:<10}")
        
        # 分析差异
        print(f"\n分析:")
        
        # 分组统计
        chat_results = [r for r in valid_results if "/chat/completions" in r.endpoint]
        messages_results = [r for r in valid_results if "/messages" in r.endpoint]
        
        if chat_results and messages_results:
            chat_avg_total = sum(r.total_tokens for r in chat_results) / len(chat_results)
            messages_avg_total = sum(r.total_tokens for r in messages_results) / len(messages_results)
            
            print(f"  - /chat/completions 平均 total_tokens: {chat_avg_total:.1f}")
            print(f"  - /messages 平均 total_tokens: {messages_avg_total:.1f}")
            
            if messages_avg_total > 0:
                ratio = chat_avg_total / messages_avg_total
                print(f"  - 比率 (chat/messages): {ratio:.2f}x")
                
                if ratio > 1.5:
                    print("  ⚠️ 警告: /chat/completions 的用量显著高于 /messages，可能存在问题")
                elif ratio < 0.67:
                    print("  ⚠️ 警告: /messages 的用量显著高于 /chat/completions，可能存在问题")
                else:
                    print("  ✅ 两个端点的用量比较接近，看起来正常")
        
        # 检查是否有 0 值
        zero_results = [r for r in valid_results if r.total_tokens == 0]
        if zero_results:
            print(f"\n  ⚠️ 警告: 以下端点返回的 total_tokens 为 0:")
            for r in zero_results:
                print(f"     - {r.endpoint}")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Usage 对比测试脚本")
    parser.add_argument("--base-url", default=os.environ.get("LLM_GATE_BASE_URL", "http://localhost:3333"), help="LLM Gate 服务地址")
    parser.add_argument("--openai-token", default=os.environ.get("LLM_GATE_TOOL_TOKEN_OPENAI"), help="用于 /chat/completions 的 Tool Token")
    parser.add_argument("--messages-token", default=os.environ.get("LLM_GATE_TOOL_TOKEN_MESSAGES"), help="用于 /messages 转换模式的 Tool Token")
    parser.add_argument("--anthropic-native-token", default=os.environ.get("LLM_GATE_TOOL_TOKEN_ANTHROPIC_NATIVE"), help="用于 /messages 原生模式的 Tool Token")
    parser.add_argument("--prompt", default="请用中文解释什么是递归，并给出一个Python示例代码。", help="测试提示词")
    parser.add_argument("--system-prompt", default=None, help="系统提示词（可选）")
    parser.add_argument("--no-stream", action="store_true", help="不测试流式模式")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("LLM Gate Usage 对比测试")
    print("=" * 60)
    print(f"Base URL: {args.base_url}")
    print(f"OpenAI Token: {'已配置' if args.openai_token else '未配置'}")
    print(f"Messages Token: {'已配置' if args.messages_token else '未配置'}")
    print(f"Anthropic Native Token: {'已配置' if args.anthropic_native_token else '未配置'}")
    print("=" * 60)
    
    if not args.openai_token and not args.messages_token:
        print("\n错误: 至少需要配置一个 Token")
        print("\n使用方式:")
        print("  export LLM_GATE_TOOL_TOKEN_OPENAI='your-token'")
        print("  export LLM_GATE_TOOL_TOKEN_MESSAGES='your-token'")
        print("  python scripts/compare_usage_test.py")
        sys.exit(1)
    
    async with UsageComparisonTester(
        base_url=args.base_url,
        openai_token=args.openai_token,
        messages_token=args.messages_token,
        anthropic_native_token=args.anthropic_native_token
    ) as tester:
        results = await tester.run_comparison(
            prompt=args.prompt,
            system_prompt=args.system_prompt,
            test_stream=not args.no_stream
        )
        
        tester.print_comparison_summary(results)


if __name__ == "__main__":
    asyncio.run(main())

    """
    
python3 scripts/compare_usage_test.py \
    --base-url http://localhost:9981 \
    --openai-token sk-your-openai-tool-token \
    --messages-token sk-your-messages-tool-token \
    --prompt "回复 10 个 1"

    """