import re as _re
import json
import logging
from typing import Dict, List, Any, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("t")

import os
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'main.py')).read()

ns = {'re': _re, 'json': json, 'logging': logging,
      'Dict': Dict, 'List': List, 'Any': Any, 'Optional': Optional, 'logger': logger}

# 注入模块级 DSML 常量（逐行抓取，避免连带执行其它定义）
for _c in ('_DSML_BAR', '_DSML_TOKEN', '_DSML_END_RE'):
    _m = _re.search(rf"^{_c} = .*$", src, _re.M)
    if _m:
        exec(_m.group(0), ns)

def grab(name):
    m = _re.search(rf"^def {name}\(.*?(?=^def |^class |^@|^[A-Za-z_]+ = )", src, _re.S | _re.M)
    return m.group(0) if m else None

for fn in ['remove_think_blocks', '_extract_dsml_json_object', '_convert_dsml_to_function_calls',
           '_coerce_dsml_value', 'parse_function_calls_xml']:
    code = grab(fn)
    if code is None:
        print("MISSING", fn)
        raise SystemExit(1)
    exec(code, ns)

parse = ns['parse_function_calls_xml']
T = "<Function_AB12_Start/>"

def show(title, content, trigger=T):
    r = parse(content, trigger)
    print("\n--- %s ---" % title)
    if r is None:
        print("  结果: None")
    else:
        for x in r:
            print("  %s %s" % (x['name'], x['args']))

# 1. 正常单组
show("单组标准XML",
     T + '\n<function_calls><function_call><tool>bash</tool>'
         '<args_json>{"command":"ls"}</args_json></function_call></function_calls>')

# 2. 多组（claude 丢步场景）
multi = (T + '\n<function_calls><function_call><tool>bash</tool>'
         '<args_json>{"command":"mkdir -p /tmp/x"}</args_json></function_call></function_calls>\n'
         + T + '\n<function_calls><function_call><tool>write</tool>'
         '<args_json><![CDATA[{"filePath":"/tmp/x/a.txt","content":"hello"}]]></args_json></function_call></function_calls>')
show("多组: 两组应全解析", multi)

# 3. 单组含两个 call
show("单组含两个call",
     T + '\n<function_calls><function_call><tool>bash</tool><args_json>{"command":"ls"}</args_json></function_call>'
         '<function_call><tool>write</tool><args_json>{"filePath":"a","content":"b"}</args_json></function_call></function_calls>')

# 4. DSML 双竖线（ds4.1 真实，无触发信号）
dsml = ('<|__DSML__| calls>\n<|__DSML__| invoke name="bash">\n'
        '<|__DSML__| parameter name="command">cat /tmp/x/a.txt<|__DSML__| parameter>\n'
        '<|__DSML__| invoke>\n<|__DSML__| calls>')
dsml = dsml.replace('|__DSML__|', '｜｜DSML｜｜')
show("DSML 双竖线(无触发信号)", dsml)

# 5. DSML 单竖线 + 裸 parameter
dsml2 = ('<｜DSML｜ calls>\n<｜DSML｜ invoke name="bash">\n'
         '<parameter name="command">cat /tmp/x/a.txt</parameter>\n'
         '</｜DSML｜ invoke>\n</｜DSML｜ calls>')
show("DSML 单竖线+裸parameter", dsml2)

# 6. DSML 带触发信号前缀
show("DSML 带触发信号", T + "\n" + dsml)

# 7. DSML 两个 invoke
dsml3 = ('<｜DSML｜ calls>\n<｜DSML｜ invoke name="bash">\n'
         '<｜DSML｜ parameter name="command">mkdir -p /tmp/x</｜DSML｜ parameter>\n</｜DSML｜ invoke>\n'
         '<｜DSML｜ invoke name="write">\n'
         '<｜DSML｜ parameter name="filePath">/tmp/x/a.txt</｜DSML｜ parameter>\n'
         '<｜DSML｜ parameter name="content">hello</｜DSML｜ parameter>\n</｜DSML｜ invoke>\n</｜DSML｜ calls>')
show("DSML 两个invoke", dsml3)

# 8. 无工具调用的纯文本
show("纯文本无工具", "你好，我已经完成了任务。")
