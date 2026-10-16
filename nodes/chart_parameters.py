import json
import math
import re


def main(text: str) -> dict:
    if not isinstance(text, str):
        raise ValueError("汇总节点必须返回字符串")
    text = text.strip().strip("\ufeff\u200b").strip()
    while re.match(r"<think\b[^>]*>", text, re.I):
        block = re.match(r"<think\b[^>]*>[\s\S]*?</think\s*>", text, re.I)
        if not block:
            raise ValueError("汇总模型输出被截断，思考标签未闭合")
        text = text[block.end():].strip().strip("\ufeff\u200b").strip()
    fence = re.fullmatch(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.I)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
    except ValueError as error:
        raise ValueError("汇总模型没有返回合法 JSON，请在运行详情中检查其输出") from error
    if not isinstance(data, dict) or not isinstance(data.get("results"), str) or not data["results"].strip():
        raise ValueError("汇总结果必须包含非空 results 正文")
    chart = {"results": data["results"], "ECHarts": str(data.get("ECHarts", "0"))}
    for key in ["chartType", "chartTitle", "chartData", "chartXAxis"]:
        chart[key] = data.get(key) or ""
        if not isinstance(chart[key], str):
            raise ValueError("图表字段必须是字符串")
    if chart["ECHarts"] not in {"0", "1"}:
        raise ValueError("ECHarts 只能是字符串 0 或 1")
    if chart["ECHarts"] == "0":
        for key in ["chartType", "chartTitle", "chartData", "chartXAxis"]:
            chart[key] = ""
        return chart
    if chart["chartType"] not in {"线性图", "柱状图", "饼状图"} or not chart["chartTitle"].strip():
        raise ValueError("图表类型或标题缺失")
    labels = chart["chartXAxis"].split(";")
    values = chart["chartData"].split(";")
    if not 1 <= len(values) <= 30 or len(values) != len(labels) or any(not label.strip() for label in labels):
        raise ValueError("图表标签与数值必须一一对应，最多 30 个点")
    try:
        numbers = [float(value) for value in values]
    except ValueError as error:
        raise ValueError("图表数值只能使用数字，以英文分号分隔") from error
    if not all(math.isfinite(number) for number in numbers):
        raise ValueError("图表数值不能包含 NaN 或无穷大")
    if chart["chartType"] == "饼状图" and (any(number < 0 for number in numbers) or sum(numbers) <= 0):
        raise ValueError("饼图数值必须非负且合计大于零")
    return chart
