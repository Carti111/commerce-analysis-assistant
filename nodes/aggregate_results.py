import json


def main(items: list) -> dict:
    if not isinstance(items, list) or not items:
        raise ValueError("没有可汇总的执行结果，不能生成经营结论")
    return {"result": json.dumps(items, ensure_ascii=False)}
