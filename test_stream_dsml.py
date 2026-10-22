import re as _re, json, logging
from typing import Dict, List, Any, Optional
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("t")
import os
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'main.py')).read()
ns = {'re': _re, 'json': json, 'logging': logging, 'Dict': Dict, 'List': List,
      'Any': Any, 'Optional': Optional, 'logger': logger,
      'secrets': __import__('secrets'), 'string': __import__('string'),
      'uuid': __import__('uuid'), 'time': __import__('time')}

def grab_def(name):
    m = _re.search(rf"^def {name}\(.*?(?=^def |^class |^@|^[A-Za-z_]+ = |^_[A-Za-z_]+ = )", src, _re.S | _re.M)
    return m.group(0) if m else None

def grab_const(name):
    m = _re.search(rf"^{name} = .*$", src, _re.M)
    return m.group(0) if m else None

# 常量
for c in ['_DSML_BAR', '_DSML_TOKEN', '_DSML_END_RE']:
    code = grab_const(c)
    if code:
        exec(code, ns)
    elif c == '_DSML_END_RE':
        exec('_DSML_END_RE = re.compile("")', ns)

# 函数
for fn in ['remove_think_blocks', '_detect_dsml_start', '_has_dsml_end',
           '_extract_dsml_json_object', '_coerce_dsml_value',
           '_convert_dsml_to_function_calls', 'parse_function_calls_xml']:
    code = grab_def(fn)
    assert code, "MISSING " + fn
    exec(code, ns)

# 检测器类
cls = _re.search(r"^class StreamingFunctionCallDetector:.*?(?=^# DeepSeek|^def parse_function_calls_xml)", src, _re.S | _re.M).group(0)
exec(cls, ns)
Detector = ns['StreamingFunctionCallDetector']
parse = ns['parse_function_calls_xml']

T = "<Function_AB12_Start/>"
DSML = ('<|X| calls>\n<|X| invoke name="bash">\n'
        '<|X| parameter name="command">cat /tmp/x/a.txt<|X| parameter>\n'
        '<|X| invoke>\n<|X| calls>').replace('|X|', '\uff5c\uff5cDSML\uff5c\uff5c')

print("=== 流式检测器：DSML 逐字符分片 ===")
det = Detector(T)
yielded = ""
detected = False
for ch in DSML:
    d, y = det.process_chunk(ch)
    yielded += y
    if d:
        detected = True
print("  是否检测到:", detected, "| 状态:", det.state)
print("  吐出的正文:", repr(yielded))
print("  解析结果:", parse(det.content_buffer, T))

print("\n=== 流式检测器：正常XML触发信号分片 ===")
normal = T + '\n<function_calls><function_call><tool>bash</tool><args_json>{"command":"ls"}</args_json></function_call></function_calls>'
det2 = Detector(T)
y2 = ""
d2 = False
# 按 3 字符分片
for i in range(0, len(normal), 3):
    d, y = det2.process_chunk(normal[i:i+3])
    y2 += y
    d2 = d2 or d
print("  是否检测到:", d2, "| 状态:", det2.state)
print("  解析结果:", parse(det2.content_buffer, T))

print("\n=== 流式检测器：普通文本不应误触发 ===")
det3 = Detector(T)
d3, y3 = det3.process_chunk("这是一个普通回答，没有工具调用。")
print("  是否检测到:", d3, "| 正文:", repr(y3))
