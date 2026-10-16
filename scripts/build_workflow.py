"""Build a Dify DSL using JSON syntax, which is also valid YAML.

Only standard Python libraries are needed. Plugin identifiers are pinned in
config/plugins.json. No files outside this repository are required.
"""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_CONFIG = ROOT / "config" / "plugins.json"
IDS = {key: str(1800000000000 + i) for i, key in enumerate([
    "start", "planner", "guard", "route", "clarify", "iteration", "item", "database", "capture",
    "aggregate", "summary", "chart", "body", "chart_route", "line", "bar", "pie", "line_reply", "bar_reply", "pie_reply",
], 1)}
IDS["iteration_start"] = IDS["iteration"] + "start"


def ref(key, field):
    return "{{#" + IDS[key] + "." + field + "#}}"


def variable(name, key, field, typ="string"):
    return {"variable": name, "value_selector": [IDS[key], field], "value_type": typ}


def node(key, title, typ, x, y, extra=None, parent=None):
    data = {"title": title, "type": typ, "selected": False, "desc": ""}
    data.update(extra or {})
    result = {"id": IDS[key], "type": "custom", "data": data, "position": {"x": x, "y": y},
              "positionAbsolute": {"x": x, "y": y}, "width": 242, "height": 90,
              "sourcePosition": "right", "targetPosition": "left", "selected": False}
    if parent:
        result["parentId"] = IDS[parent]
        data.update(isInIteration=True, isInLoop=False, iteration_id=IDS[parent])
        result["extent"] = "parent"
        result["zIndex"] = 1002
        result["positionAbsolute"] = {"x": 1400 + x, "y": 200 + y}
    return result


def code_node(key, title, script, outputs, variables, x, y, parent=None):
    return node(key, title, "code", x, y, {
        "code_language": "python3", "code": (ROOT / "nodes" / script).read_text(encoding="utf-8"),
        "outputs": {name: {"type": typ, "children": None} for name, typ in outputs.items()}, "variables": variables,
    }, parent)


def llm_node(key, title, prompt, user, x, y):
    return node(key, title, "llm", x, y, {
        "context": {"enabled": False, "variable_selector": []},
        "model": {"provider": "langgenius/deepseek/deepseek", "name": "deepseek-v4-flash", "mode": "chat",
                  "completion_params": {"temperature": 0.1}},
        "reasoning_format": "separated", "structured_output_enabled": False,
        "vision": {"enabled": False},
        "prompt_template": [
            {"id": key + "-system", "role": "system", "text": (ROOT / "prompts" / prompt).read_text(encoding="utf-8")},
            {"id": key + "-user", "role": "user", "text": user},
        ],
    })


def condition(case_id, key, field, value):
    return {"case_id": case_id, "id": case_id, "logical_operator": "and", "conditions": [{
        "id": case_id + "-condition", "variable_selector": [IDS[key], field],
        "comparison_operator": "is", "value": value, "varType": "string",
    }]}


def main():
    plugins = json.loads(PLUGIN_CONFIG.read_text(encoding="utf-8"))
    if not isinstance(plugins, list) or len(plugins) != 3 or not all(isinstance(p, str) for p in plugins):
        raise ValueError("config/plugins.json 必须包含三个插件版本标识")
    plugin_for = {p.split(":", 1)[0]: p for p in plugins}
    nodes = [
        node("start", "用户提问", "start", 100, 200, {"variables": []}),
        llm_node("planner", "经营问题与SQL规划", "sql_planner.md", "用户问题：{{#sys.query#}}", 420, 200),
        code_node("guard", "解析与SQL检查", "sql_guard.py", {"result": "array[object]", "ready": "string", "message": "string", "diagnostic": "string"}, [variable("input_string", "planner", "text")], 740, 200),
        node("route", "可以执行？", "if-else", 1060, 200, {"cases": [condition("true", "guard", "ready", "1")]}),
        node("clarify", "澄清或不支持", "answer", 1400, 650, {"answer": ref("guard", "message"), "variables": []}),
        node("iteration", "按计划查询数据库", "iteration", 1400, 200, {
            "iterator_selector": [IDS["guard"], "result"], "iterator_input_type": "array[object]",
            "output_selector": [IDS["capture"], "result"], "output_type": "array[object]",
            "is_parallel": False, "parallel_nums": 3, "flatten_output": False,
            "error_handle_mode": "terminated", "start_node_id": IDS["iteration_start"], "width": 1220, "height": 300,
        }),
        node("iteration_start", "", "iteration-start", 30, 90, {}, "iteration"),
        code_node("item", "提取单项计划", "query_item.py", {"title": "string", "sql": "string", "metric_note": "string"}, [variable("item", "iteration", "item", "object")], 120, 70, "iteration"),
    ]
    nodes[5].update(width=1220, height=300, zIndex=1)
    nodes[6].update(type="custom-iteration-start", width=44, height=48, draggable=False, selectable=False)
    nodes.append(node("database", "执行只读SQL", "tool", 460, 70, {
        "provider_id": "hjlarry/database/database", "provider_type": "builtin", "provider_name": "hjlarry/database/database",
        "plugin_id": "hjlarry/database", "plugin_unique_identifier": plugin_for["hjlarry/database"],
        "tool_name": "sql_execute", "tool_label": "SQL Execute", "tool_description": "查询独立电商演示数据库",
        "tool_node_version": "2", "is_team_authorization": True,
        "tool_configurations": {
            "format": {"type": "constant", "value": "json"},
            "config_options": {"type": "mixed", "value": json.dumps({"connect_args": {"connect_timeout": 5, "read_timeout": 8}, "pool_pre_ping": True})},
        },
        "tool_parameters": {"db_uri": {"type": "mixed", "value": "{{#env.DB_URI#}}"}, "query": {"type": "mixed", "value": ref("item", "sql")}},
    }, "iteration"))
    nodes.extend([
        code_node("capture", "保留SQL与实际结果", "capture_result.py", {"result": "object"}, [variable("db_json", "database", "json", "array[object]"), variable("title", "item", "title"), variable("sql", "item", "sql"), variable("metric_note", "item", "metric_note")], 800, 70, "iteration"),
        code_node("aggregate", "组织查询证据", "aggregate_results.py", {"result": "string"}, [variable("items", "iteration", "output", "array[object]")], 2720, 200),
        llm_node("summary", "基于实际结果分析", "summary.md", "用户问题：{{#sys.query#}}\n实际查询结果：\n" + ref("aggregate", "result"), 3040, 200),
        code_node("chart", "正文与图表参数检查", "chart_parameters.py", {name: "string" for name in ["results", "ECHarts", "chartType", "chartTitle", "chartData", "chartXAxis"]}, [variable("text", "summary", "text")], 3360, 200),
        node("body", "输出经营分析", "answer", 3680, 200, {"answer": ref("chart", "results"), "variables": []}),
        node("chart_route", "是否需要图表", "if-else", 4000, 200, {"cases": [
            condition("no-chart", "chart", "ECHarts", "0"), condition("line", "chart", "chartType", "线性图"),
            condition("bar", "chart", "chartType", "柱状图"), condition("pie", "chart", "chartType", "饼状图"),
        ]}),
    ])
    for key, tool_name, title, y in [("line", "line_chart", "线性图表", 80), ("bar", "bar_chart", "柱状图", 280), ("pie", "pie_chart", "饼图", 480)]:
        parameters = {"title": "chartTitle", "data": "chartData", "categories" if key == "pie" else "x_axis": "chartXAxis"}
        nodes.append(node(key, title, "tool", 4350, y, {
            "provider_id": "langgenius/echarts/echarts", "provider_type": "builtin", "provider_name": "langgenius/echarts/echarts",
            "plugin_id": "langgenius/echarts", "plugin_unique_identifier": plugin_for["langgenius/echarts"],
            "tool_name": tool_name, "tool_label": title, "tool_node_version": "2", "tool_configurations": {},
            "tool_parameters": {name: {"type": "mixed", "value": ref("chart", field)} for name, field in parameters.items()},
        }))
        nodes.append(node(key + "_reply", "输出" + title, "answer", 4670, y, {"answer": "\n\n" + ref(key, "text"), "variables": []}))

    by_id = {item["id"]: item for item in nodes}
    edges = []

    def edge(a, b, handle="source", parent=None):
        data = {"sourceType": by_id[IDS[a]]["data"]["type"], "targetType": by_id[IDS[b]]["data"]["type"], "isInIteration": bool(parent), "isInLoop": False}
        if parent:
            data["iteration_id"] = IDS[parent]
        edges.append({"id": f"{IDS[a]}-{handle}-{IDS[b]}", "source": IDS[a], "target": IDS[b], "sourceHandle": handle, "targetHandle": "target", "type": "custom", "data": data, "zIndex": 1002 if parent else 0})

    for a, b in [("start", "planner"), ("planner", "guard"), ("guard", "route")]:
        edge(a, b)
    edge("route", "iteration", "true")
    edge("route", "clarify", "false")
    for a, b in [("iteration_start", "item"), ("item", "database"), ("database", "capture")]:
        edge(a, b, parent="iteration")
    for a, b in [("iteration", "aggregate"), ("aggregate", "summary"), ("summary", "chart"), ("chart", "body"), ("body", "chart_route")]:
        edge(a, b)
    for key in ["line", "bar", "pie"]:
        edge("chart_route", key, key)
        edge(key, key + "_reply")

    workflow = {
        "kind": "app", "version": "0.5.0",
        "app": {"name": "商析助手｜电商经营分析", "description": "基于模拟订单数据的自然语言经营分析：查询规划、SQL检查、多表统计、结果汇总与图表。演示日期2026-10-16。", "icon": "📊", "icon_background": "#E4FBCC", "mode": "advanced-chat", "use_icon_as_answer_icon": False},
        "dependencies": [{"type": "marketplace", "current_identifier": None, "value": {"marketplace_plugin_unique_identifier": p, "version": None}} for p in plugins],
        "workflow": {
            "conversation_variables": [],
            "environment_variables": [{"id": "c1c0e508-5f66-4c34-bbbc-389bd6bcf7db", "name": "DB_URI", "description": "填入 commerce_reader 的 MySQL 连接串；不要使用 root", "value_type": "secret", "value": "", "selector": ["env", "DB_URI"]}],
            "features": {"opening_statement": "你好，我是商析助手。可以查询销售额、商品排行、客户贡献及订单退款情况，并展示图表。\n当前为模拟数据，覆盖2026-04-01至2026-10-15；相对时间以2026-10-16为基准。",
                         "suggested_questions": ["查询2026年9月各品类销售额，用柱状图展示。", "最近7天每天的有效销售额是多少？用线性图展示。", "统计2026年9月各渠道销售额占比，用饼图展示。", "查询最近30天购买金额最高的前10位客户。", "查询2026年9月的销售额、有效订单数和客单价，不需要图表。"],
                         "suggested_questions_after_answer": {"enabled": False}, "retriever_resource": {"enabled": False},
                         "sensitive_word_avoidance": {"enabled": False}, "speech_to_text": {"enabled": False},
                         "text_to_speech": {"enabled": False, "language": "", "voice": ""}, "file_upload": {"enabled": False}},
            "graph": {"nodes": nodes, "edges": edges, "viewport": {"x": 0, "y": 0, "zoom": .45}},
        },
    }
    out = ROOT / "workflow"
    out.mkdir(exist_ok=True)
    path = out / "商析助手-电商经营分析.yml"
    path.write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8")
    # Round-trip through the JSON subset rather than a hand-written YAML emitter.
    assert json.loads(path.read_text(encoding="utf-8")) == workflow
    print(f"DSL generated: {path}; {len(nodes)} nodes / {len(edges)} edges")


if __name__ == "__main__":
    main()
