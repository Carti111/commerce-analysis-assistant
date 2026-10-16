"""Keep the query metadata together with the database plugin's JSON result."""


def main(db_json: list, title: str, sql: str, metric_note: str) -> dict:
    # hjlarry/database JSON output is normally [{"result": [row, ...]}].
    if not isinstance(db_json, list) or not db_json:
        raise ValueError("数据库工具未返回预期的 JSON 数组，请检查插件输出")
    rows = []
    for message in db_json:
        if not isinstance(message, dict) or not isinstance(message.get("result"), list):
            raise ValueError("数据库返回结构不符合 {result: [...]} 约定，不能当作空结果处理")
        rows.extend(message["result"])
    if len(rows) > 100:
        raise ValueError("数据库结果超过 100 行限制")
    return {"result": {
        "title": title, "sql": sql, "metric_note": metric_note,
        "row_count": len(rows), "rows": rows,
    }}
