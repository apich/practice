"""对比 DeepSeek 和 mimo 的 API 响应格式"""
import requests
import json

# 测试 DeepSeek
print("=" * 60)
print("测试 DeepSeek API")
print("=" * 60)

try:
    resp = requests.post(
        "https://api.deepseek.com/anthropic/v1/messages",
        headers={
            "x-api-key": "sk-b9c70bd512bf4cbbb31a89f3b9959534",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "deepseek-v4-flash",
            "max_tokens": 30,
            "stream": True,
            "messages": [{"role": "user", "content": "Say hi"}]
        },
        timeout=30,
        stream=True
    )
    print(f"状态码: {resp.status_code}")

    for line in resp.iter_lines():
        if line:
            decoded = line.decode("utf-8")
            if "usage" in decoded.lower() or "message_start" in decoded or "message_delta" in decoded:
                print(decoded)
except Exception as e:
    print(f"错误: {e}")

print()

# 测试 mimo
print("=" * 60)
print("测试 mimo API")
print("=" * 60)

try:
    resp = requests.post(
        "https://api.xiaomimimo.com/anthropic/v1/messages",
        headers={
            "x-api-key": "sk-cu50r5o6t4szqhl25vt2ambcmpaio1db1u3vfhi4zwnndbmm",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "mimo-v2.5-pro",
            "max_tokens": 30,
            "stream": True,
            "messages": [{"role": "user", "content": "Say hi"}]
        },
        timeout=30,
        stream=True
    )
    print(f"状态码: {resp.status_code}")

    for line in resp.iter_lines():
        if line:
            decoded = line.decode("utf-8")
            if "usage" in decoded.lower() or "message_start" in decoded or "message_delta" in decoded:
                print(decoded)
except Exception as e:
    print(f"错误: {e}")
