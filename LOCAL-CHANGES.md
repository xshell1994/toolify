# 本机改动（相对上游 Toolify）

本仓库是**本机在跑的 Toolify 快照**，不是干净的上游检出（上游 tarball/仓库已无 `.git`，
所以没有基线 commit 可比对）。这里记录相对上游加的补丁，免得日后重建时抓瞎。

## 唯一的改动主题：支持讯飞星火的 `<tool_call>` 方言

上游 Toolify 只会：
- 注入 `{trigger_signal}` + `<function_calls><function_call><tool>…</tool><args_json>…</args_json></function_call></function_calls>`；
- 检测 `trigger_signal` 后按这套 XML 解析。

而星火（`xinghuo.xfyun.cn`）**大多数时候根本不发 trigger signal**，直接吐它自己的方言：

```xml
<tool_call>read<arg_key>path</arg_key><arg_value>/etc/hostname</arg_value></tool_call>
```

并且会把工具名**首字母大写**（客户端注册的是小写），于是上游流程两条路都断：
解析器不认方言 → 判 `no_fc`；就算认出来，`validate_parsed_tools()` 严格匹配也会报
`Tool call #1: unknown tool 'Read'. Allowed tools: ['bash','edit','glob',…]`，
重试 3 次后把原始 content 原样透传给客户端。

## 改动清单（都在 `main.py`）

| # | 位置 | 改动 |
|---|---|---|
| 1 | `validate_parsed_tools()`（约 :425） | `allowed_names = sorted(list(allowed.keys()))` 之后加大小写归一：`canonical = {name.lower(): name for name in allowed}`；遍历 `parsed_tools`，若 `name not in allowed` 且 `canonical.get(name.strip().lower())` 命中，则 `call["name"] = fixed`（回填**注册名**，客户端才认） |
| 2 | 流式检测器 | 新增 `_SPARK_TOOL_CALL_MARK = "<tool_call>"` 与 `_detect_spark_start(text, pos) -> "match"｜"partial"｜"none"`（简化版同 `_detect_dsml_start`）；在 `StreamingFunctionCallDetector.process_chunk()` 的 `dsml_state` 分支之后加 `spark_state` 分支（match → `self.state = "tool_parsing"`；partial → `break`） |
| 3 | `parse_function_calls_xml()` | 新增 `_SPARK_CALL_RE`（`<tool_call>\s*([A-Za-z_][\w.\-]*)\s*((?:<arg_key>…</arg_key>\s*<arg_value>…</arg_value>\s*)*)</tool_call>`，`re.IGNORECASE`）、`_SPARK_ARG_RE`、`_convert_spark_to_function_calls(text) -> str`（照抄既有 `_convert_dsml_to_function_calls` 的写法：把每个 `<tool_call>` 转成标准 `<function_call>`，原块从正文剥离后拼 `<function_calls>…</function_calls>`）；在 DSML 归一化块之后加 `if _SPARK_TOOL_CALL_MARK in xml_string.lower(): normalized = _convert_spark_to_function_calls(xml_string)` |
| 4 | `_attempt_streaming_fc_retry()` | 新增 `_has_spark_tool_call(text)` / `_has_spark_tool_end(text)`；把开头的 `if find_last_trigger_signal_outside_think(...) == -1: return None` 移到 `attempt == 0` 的解析之后，改成 `... == -1 and not _has_spark_tool_call(current_content)` |
| 5 | `_early_close`（约 :2772） | 条件追加 `or _has_spark_tool_end(detector.content_buffer)` |

## 没入库的东西

- `config.yaml` —— 含本机凭据（上游 `api_key`、`client_authentication.allowed_keys`）。
  按 `config.example.yaml` 重建即可；本机那份额外加了一个上游：
  ```yaml
  - name: "spark"
    base_url: "http://127.0.0.1:9002/v1"
    api_key: "123"
    description: "iFlytek Spark X via local 9002 gateway (auto/fast/reason)"
    is_default: false
    models: ["spark-x-auto", "spark-x-fast", "spark-x-reason"]
  ```
- `*.bak-*`（main.py 的历史备份）、`toolify.log*`、`__pycache__/`。

## 配套

上限 9002 那层的实现、鉴权结论与端到端验证在另一个库：
`https://github.com/xshell1994/spark-9002-gateway`（README 的「工具调用 / Toolify 侧需要的补丁」两节是同源描述）。
