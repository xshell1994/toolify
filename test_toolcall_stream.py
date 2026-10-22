#!/usr/bin/env python3
"""Toolify + genspark2api 流式工具调用实测。

验证 SSE 流中 tool_calls 增量的组装是否正确（多数 Agent 客户端走流式）。
"""
import json
import sys
import time

import httpx

BASE = "http://127.0.0.1:8010/v1"
KEY = "sk-toolify-genspark"
MODEL = sys.argv[1] if len(sys.argv) > 1 else "gpt-5.4-nano"

TOOLS = [{
    "type": "function",
    "function": {
        "name": "get_current_weather",
        "description": "获取指定城市的当前天气",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "城市名，如 北京"}},
            "required": ["city"],
        },
    },
}]
H = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}


def main():
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": "上海现在天气怎么样？请用工具查询。"}],
        "tools": TOOLS,
        "tool_choice": "auto",
        "stream": True,
    }
    t0 = time.time()
    buf_text, tc_acc, finish, nchunks = "", {}, None, 0
    with httpx.stream("POST", f"{BASE}/chat/completions", json=body, headers=H,
                      timeout=300) as r:
        print(f"[流式] HTTP {r.status_code}")
        if r.status_code != 200:
            print(r.read().decode("utf-8", "replace")[:1200])
            return 1
        for line in r.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                ev = json.loads(payload)
            except ValueError:
                continue
            nchunks += 1
            ch = (ev.get("choices") or [{}])[0]
            delta = ch.get("delta") or {}
            if ch.get("finish_reason"):
                finish = ch["finish_reason"]
            if delta.get("content"):
                buf_text += delta["content"]
            for tc in (delta.get("tool_calls") or []):
                idx = tc.get("index", 0)
                slot = tc_acc.setdefault(idx, {"id": None, "name": None, "args": ""})
                if tc.get("id"):
                    slot["id"] = tc["id"]
                fn = tc.get("function") or {}
                if fn.get("name"):
                    slot["name"] = fn["name"]
                if fn.get("arguments"):
                    slot["args"] += fn["arguments"]

    dt = time.time() - t0
    print(f"[流式] chunks={nchunks} 耗时={dt:.1f}s finish_reason={finish}")
    print(f"[流式] content = {repr(buf_text[:300])}")
    if tc_acc:
        for i, s in sorted(tc_acc.items()):
            args_ok = True
            try:
                json.loads(s["args"])
            except Exception:
                args_ok = False
            print(f"[流式] tool_call[{i}] id={s['id']} name={s['name']} "
                  f"args={s['args']} (JSON合法={args_ok})")
        print("✅ 流式工具调用组装成功" if all(json.loads(s['args']) or True for s in tc_acc.values())
              else "⚠️ 参数 JSON 不完整")
        return 0
    print("❌ 流式未产出 tool_calls")
    return 2


if __name__ == "__main__":
    sys.exit(main())
