"""
Embeddings API 调试脚本

测试 input 字段的 4 种输入格式：
  1. string          - 单个字符串
  2. array of string  - 字符串数组
  3. array of int     - token ID 数组
  4. array of array of int - 批量 token ID 数组

同时测试 encoding_format、dimensions 等可选参数。

用法:
    python debug_embeddings.py

需要:
    1. 服务已启动: python run.py
    2. 配置有效的 Tool Token (api_type 为 openai_embeddings)
"""
import json
import os

import httpx

# 配置
BASE_URL = "http://localhost:9981"
TOOL_TOKEN = os.environ.get("LLM_GATE_PROBE_TOOL_TOKEN", "")  # 从环境变量读取，避免硬编码


# 测试用例
TEST_CASES = [
    {
        "name": "1. 单个字符串",
        "payload": {
            "input": "Hello, world!",
        },
    },
    {
        "name": "2. 字符串数组",
        "payload": {
            "input": ["Hello, world!", "Goodbye, world!"],
        },
    },
    {
        "name": "3. token ID 数组 (整数)",
        "payload": {
            "input": [9906, 11, 1917, 0],  # "Hello, world!" 的近似 token IDs
        },
    },
    {
        "name": "4. 批量 token ID 数组 (二维整数数组)",
        "payload": {
            "input": [[9906, 11, 1917, 0], [15571, 29892, 3186, 0]],
        },
    },
    {
        "name": "5. encoding_format=base64",
        "payload": {
            "input": "Hello, world!",
            "encoding_format": "base64",
        },
    },
    {
        "name": "6. 指定 dimensions=256",
        "payload": {
            "input": "Hello, world!",
            "dimensions": 256,
        },
    },
]


def send_request(client, url, headers, payload):
    """发送单个请求并打印结果"""
    response = client.post(url, json=payload, headers=headers)
    status = response.status_code
    body = response.json()

    # 成功时只打印摘要（embedding 向量太长）
    if status == 200:
        data = body.get("data", [])
        usage = body.get("usage", {})
        summary = {
            "object": body.get("object"),
            "model": body.get("model"),
            "embedding_count": len(data),
            "first_embedding_dim": len(data[0]["embedding"]) if data else 0,
            "usage": usage,
        }
        return status, summary

    return status, body


def main():
    url = f"{BASE_URL}/v1/embeddings"
    headers = {
        "Authorization": f"Bearer {TOOL_TOKEN}",
        "Content-Type": "application/json",
    }

    passed = 0
    failed = 0

    with httpx.Client(timeout=30) as client:
        for case in TEST_CASES:
            name = case["name"]
            payload = case["payload"]

            print(f"\n{'=' * 60}")
            print(f"测试: {name}")
            print(f"Payload: {json.dumps(payload, ensure_ascii=False)}")
            print("-" * 60)

            try:
                status, result = send_request(client, url, headers, payload)
                print(f"Status: {status}")
                print(f"Result: {json.dumps(result, ensure_ascii=False, indent=2)}")

                if status == 200:
                    print("=> PASS")
                    passed += 1
                else:
                    print("=> FAIL")
                    failed += 1

            except httpx.RequestError as e:
                print(f"Request failed: {e}")
                print("=> FAIL")
                failed += 1
            except Exception as e:
                print(f"Error: {e}")
                print("=> FAIL")
                failed += 1

    print(f"\n{'=' * 60}")
    print(f"结果: {passed} passed, {failed} failed, 共 {passed + failed} 个测试")


if __name__ == "__main__":
    main()
