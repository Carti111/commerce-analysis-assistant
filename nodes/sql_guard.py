"""Dify code node: constrained SELECT checks, not an SQL AST or permission boundary."""
import json
import re

TABLES = {"customers", "products", "orders", "order_items"}
FUNCTIONS = {
    "COUNT", "SUM", "AVG", "MIN", "MAX", "ROUND", "COALESCE", "NULLIF",
    "DATE", "DATE_FORMAT", "DATE_SUB", "DATE_ADD", "YEAR", "MONTH", "DAY",
    "IF", "IFNULL", "ABS", "CONCAT", "DATEDIFF", "FLOOR", "CEIL", "IN",
}
FORBIDDEN = {
    "INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", "ALTER", "CREATE",
    "GRANT", "REVOKE", "CALL", "EXECUTE", "PREPARE", "DEALLOCATE", "SET",
    "USE", "SHOW", "EXPLAIN", "DESCRIBE", "INTO", "OUTFILE", "DUMPFILE",
    "LOAD", "LOAD_FILE", "SLEEP", "BENCHMARK", "GET_LOCK", "RELEASE_LOCK",
    "LOCK", "UNLOCK", "FOR", "PROCEDURE", "UNION", "WITH", "CROSS", "NATURAL",
    "INFORMATION_SCHEMA", "PERFORMANCE_SCHEMA", "MYSQL", "SYS", "SQL_CALC_FOUND_ROWS",
}


def parse_json(text):
    if not isinstance(text, str):
        raise ValueError("模型输出必须是字符串")
    text = text.strip().strip("\ufeff\u200b").strip()
    while re.match(r"<think\b[^>]*>", text, re.I):
        block = re.match(r"<think\b[^>]*>[\s\S]*?</think\s*>", text, re.I)
        if not block:
            raise ValueError("思考标签未闭合，可能发生输出截断")
        text = text[block.end():].strip().strip("\ufeff\u200b").strip()
    fence = re.fullmatch(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.I)
    if fence:
        text = fence.group(1).strip().strip("\ufeff\u200b").strip()
    return json.loads(text)


def tokenize(sql):
    tokens = []
    i = 0
    while i < len(sql):
        c = sql[i]
        if c.isspace():
            i += 1
            continue
        if sql.startswith(("--", "/*"), i) or c == "#":
            raise ValueError("不接受模型生成的 SQL 注释")
        if c == "'":
            start = i
            i += 1
            while i < len(sql):
                if sql[i] == "\\":
                    i += 2
                elif sql[i] == "'":
                    if i + 1 < len(sql) and sql[i + 1] == "'":
                        i += 2
                    else:
                        i += 1
                        break
                else:
                    i += 1
            else:
                raise ValueError("SQL 字符串没有闭合")
            tokens.append(("string", sql[start:i]))
            continue
        if c == "`":
            end = sql.find("`", i + 1)
            if end < 0 or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", sql[i + 1:end]):
                raise ValueError("不支持该标识符")
            tokens.append(("word", sql[i + 1:end].upper()))
            i = end + 1
            continue
        word = re.match(r"[A-Za-z_][A-Za-z0-9_]*", sql[i:])
        if word:
            tokens.append(("word", word.group().upper()))
            i += len(word.group())
            continue
        number = re.match(r"\d+(?:\.\d+)?", sql[i:])
        if number:
            tokens.append(("number", number.group()))
            i += len(number.group())
            continue
        if c in "(),.+-*/%=<>!;":
            tokens.append(("symbol", c))
            i += 1
            continue
        raise ValueError("不支持的 SQL 字符，请使用单引号字符串和英文列别名")
    return tokens


def validate_sql(sql):
    if not isinstance(sql, str) or not sql.strip() or len(sql) > 6000:
        raise ValueError("SQL 为空或超过长度限制")
    sql = sql.strip()
    if sql.endswith(";"):
        sql = sql[:-1].rstrip()
    tokens = tokenize(sql)
    words = [value for kind, value in tokens if kind == "word"]
    if not tokens or tokens[0] != ("word", "SELECT") or words.count("SELECT") != 1:
        raise ValueError("当前版本仅支持单层 SELECT，不支持 CTE 或子查询")
    if any(token == ("symbol", ";") for token in tokens):
        raise ValueError("只允许一条 SQL 语句")
    if FORBIDDEN.intersection(words):
        raise ValueError("SQL 包含不允许的操作或关键字")
    if len(tokens) > 1 and tokens[1] == ("symbol", "*"):
        raise ValueError("请明确列名，不能 SELECT *")

    tables = []
    depth = 0
    in_from = False
    for index, (kind, value) in enumerate(tokens):
        if kind == "symbol":
            if value == "(":
                depth += 1
            elif value == ")":
                depth -= 1
                if depth < 0:
                    raise ValueError("SQL 括号不匹配")
            elif value == "," and in_from and depth == 0:
                raise ValueError("多表查询必须显式 JOIN，不能逗号连接")
        if kind != "word":
            continue
        if index + 1 < len(tokens) and tokens[index + 1] == ("symbol", "("):
            if value not in FUNCTIONS:
                raise ValueError("SQL 使用了不在允许列表中的函数")
        if value in {"WHERE", "GROUP", "ORDER", "HAVING", "LIMIT"}:
            in_from = False
        if value in {"FROM", "JOIN"}:
            in_from = True
            if index + 1 >= len(tokens) or tokens[index + 1][0] != "word":
                raise ValueError("FROM/JOIN 后必须是允许的表名")
            table = tokens[index + 1][1].lower()
            if table not in TABLES:
                raise ValueError("SQL 访问了未允许的表")
            if index + 2 < len(tokens) and tokens[index + 2] == ("symbol", "."):
                raise ValueError("不允许跨数据库查询")
            tables.append(table)
    if depth != 0 or not tables or words.count("FROM") != 1:
        raise ValueError("SQL 表引用或括号不符合支持范围")
    if words.count("JOIN") != words.count("ON") or words.count("JOIN") > 3:
        raise ValueError("每个 JOIN 必须有 ON 条件，最多关联四张表")

    limits = [i for i, token in enumerate(tokens) if token == ("word", "LIMIT")]
    if limits:
        tail = tokens[limits[0] + 1:]
        if len(limits) != 1 or len(tail) != 1 or tail[0][0] != "number" or not tail[0][1].isdigit():
            raise ValueError("仅支持 LIMIT 整数，不支持 OFFSET")
        if not 1 <= int(tail[0][1]) <= 100:
            raise ValueError("单次查询最多返回 100 行")
    else:
        sql += " LIMIT 100"
    # 5 秒限制为 MySQL SELECT 提示；只读账号仍是必须的权限边界。
    return "SELECT /*+ MAX_EXECUTION_TIME(5000) */" + sql[len("SELECT"):] + ";"


def main(input_string: str) -> dict:
    output = {"result": [], "ready": "0", "message": "", "diagnostic": ""}
    try:
        data = parse_json(input_string)
        if not isinstance(data, dict):
            raise ValueError("计划必须是 JSON 对象")
        status = data.get("status")
        if status in {"clarify", "unsupported"}:
            message = data.get("message")
            if not isinstance(message, str) or not message.strip():
                raise ValueError("澄清或不支持的问题必须返回 message")
            output["message"] = message[:500]
            return output
        queries = data.get("queries")
        if status != "ok" or not isinstance(queries, list) or not 1 <= len(queries) <= 3:
            raise ValueError("有效计划必须包含 1 至 3 条查询")
        result = []
        for item in queries:
            if not isinstance(item, dict):
                raise ValueError("查询计划项必须是对象")
            title = item.get("title")
            if not isinstance(title, str) or not title.strip():
                raise ValueError("查询计划必须有标题")
            result.append({
                "title": title[:100],
                "sql": validate_sql(item.get("sql")),
                "metric_note": str(item.get("metric_note", ""))[:500],
            })
        output.update(result=result, ready="1")
    except (ValueError, TypeError, KeyError) as error:
        output["message"] = "这次查询计划未通过检查，尚未执行数据库查询。请明确时间范围、指标和分析维度后重试。"
        output["diagnostic"] = str(error)[:500]
    return output
