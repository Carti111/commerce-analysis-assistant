def main(item: dict) -> dict:
    return {
        "title": item["title"],
        "sql": item["sql"],
        "metric_note": item.get("metric_note", ""),
    }
