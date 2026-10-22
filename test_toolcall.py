#!/usr/bin/env python3
"""Toolify + genspark2api 工具调用端到端实测。

两轮验证：
  轮1：带 tools 请求 -> 期望返回 OpenAI 格式 tool_calls
  轮2：回传 tool result -> 期望模型基于结果给出最终文本回答
"""
import json
import os
import sys
import time

import httpx

BASE = os.environ.get("TC_BASE", "http://127.0.0.1:8010/v1")
KEY = os.environ.get("TC_KEY", "sk-toolify-genspark")
MODEL = os.environ.get("TC_MODEL") or (sys.argv[1] if len(sys.argv) > 1 else "gpt-5.4-nano")

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "获取指定城市的当前天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名，如 北京"},
                    "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                },
                "required": ["city"],
            },
        },
    }
]

H = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}


def main():
    # ---- 轮 1 ----
    body1 = {
        "model": MODEL,
        "messages": [{"role": "user", "content": "北京现在天气怎么样？请用工具查询。"}],
        "tools": TOOLS,
        "tool_choice": "auto",
        "stream": False,
    }
    t0 = time.time()
    r = httpx.post(f"{BASE}/chat/completions", json=body1, headers=H, timeout=300)
    dt = time.time() - t0
    print(f"[轮1] HTTP {r.status_code}  耗时 {dt:.1f}s")
    if r.status_code != 200:
        print("响应体:", r.text[:1200])
        return 1
    d = r.json()
    msg = d["choices"][0]["message"]
    tc = msg.get("tool_calls")
    fr = d["choices"][0].get("finish_reason")
    print(f"[轮1] finish_reason = {fr}")
    print(f"[轮1] content = {repr((msg.get('content') or '')[:300])}")
    print(f"[轮1] tool_calls = {json.dumps(tc, ensure_ascii=False) if tc else None}")
    if not tc:
        print("❌ 未返回 tool_calls —— 工具调用未生效")
        return 2
    print("✅ 轮1 返回了 tool_calls")

    # ---- 轮 2：回传工具结果 ----
    call = tc[0]
    msgs = list(body1["messages"])
    msgs.append({"role": "assistant", "content": msg.get("content"), "tool_calls": tc})
    msgs.append({
        "role": "tool",
        "tool_call_id": call["id"],
        "name": call["function"]["name"],
        "content": json.dumps({"city": "北京", "temperature": 18, "unit": "celsius",
                               "condition": "多云"}, ensure_ascii=False),
    })
    body2 = {"model": MODEL, "messages": msgs, "tools": TOOLS, "stream": False}
    t0 = time.time()
    r2 = httpx.post(f"{BASE}/chat/completions", json=body2, headers=H, timeout=300)
    dt2 = time.time() - t0
    print(f"\n[轮2] HTTP {r2.status_code}  耗时 {dt2:.1f}s")
    if r2.status_code != 200:
        print("响应体:", r2.text[:1200])
        return 3
    d2 = r2.json()
    msg2 = d2["choices"][0]["message"]
    print(f"[轮2] finish_reason = {d2['choices'][0].get('finish_reason')}")
    print(f"[轮2] content = {(msg2.get('content') or '')[:500]}")
    print(f"[轮2] tool_calls = {json.dumps(msg2.get('tool_calls'), ensure_ascii=False) if msg2.get('tool_calls') else None}")
    ok = bool(msg2.get("content")) and not msg2.get("tool_calls")
    print("✅ 轮2 基于工具结果给出了最终回答" if ok else "⚠️ 轮2 未按预期收敛")
    return 0 if ok else 4


if __name__ == "__main__":
    sys.exit(main())
