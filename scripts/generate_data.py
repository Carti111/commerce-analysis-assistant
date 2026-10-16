"""Reproducible synthetic commerce fixture. Writes files; never connects to a database."""
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import hashlib
import json
import random

ROOT = Path(__file__).resolve().parents[1]
SEED = 20261016
START = date(2026, 4, 1)
END = date(2026, 10, 15)


def money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def sql_value(value):
    if value is None:
        return "NULL"
    if isinstance(value, (int, Decimal)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def insert_sql(table, columns, rows):
    chunks = []
    for index in range(0, len(rows), 200):
        values = ["(" + ", ".join(sql_value(row[column]) for column in columns) + ")" for row in rows[index:index + 200]]
        chunks.append(f"INSERT INTO {table} ({', '.join(columns)}) VALUES\n" + ",\n".join(values) + ";")
    return "\n\n".join(chunks)


def main():
    rng = random.Random(SEED)
    regions = [("华东", "杭州"), ("华南", "广州"), ("华北", "北京"), ("华中", "武汉"), ("西南", "成都"), ("西北", "西安")]
    customers = []
    for cid in range(1, 241):
        region, city = regions[(cid - 1) % len(regions)]
        customers.append({"customer_id": cid, "customer_name": f"演示客户{cid:04d}", "region": region, "city": city,
                          "registered_at": (date(2025, 12, 1) + timedelta(days=rng.randrange(120))).isoformat()})
    catalog = [
        ("数码配件", ["无线鼠标", "机械键盘", "蓝牙耳机", "充电宝", "手机支架", "数据线", "USB扩展坞", "平板保护套"], [89, 239, 169, 129, 39, 29, 119, 69]),
        ("家居日用", ["保温杯", "收纳盒", "台灯", "毛巾套装", "香薰", "旅行水杯", "厨房置物架", "抱枕"], [79, 49, 139, 59, 69, 89, 99, 45]),
        ("运动户外", ["瑜伽垫", "跳绳", "运动水壶", "登山包", "弹力带", "速干毛巾", "露营灯", "护膝"], [99, 39, 59, 199, 49, 35, 129, 79]),
        ("办公文具", ["笔记本", "中性笔套装", "文件夹", "桌面收纳架", "便签纸", "订书机", "笔袋", "日程本"], [29, 19, 15, 69, 12, 25, 35, 45]),
    ]
    products = []
    for category, names, prices in catalog:
        for name, price in zip(names, prices):
            products.append({"product_id": len(products) + 1, "product_name": name, "category": category,
                             "list_price": money(price), "cost_price": money(Decimal(price) * Decimal(str(rng.uniform(.38, .65))))})
    dates = rng.choices(list(range((END - START).days + 1)), weights=[1 + index / 140 for index in range((END - START).days + 1)], k=1200)
    dates.sort()
    orders, items = [], []
    for oid, offset in enumerate(dates, 1):
        day = START + timedelta(days=offset)
        ordered_at = datetime.combine(day, datetime.min.time()) + timedelta(hours=rng.randrange(8, 23), minutes=rng.randrange(60))
        cid = rng.choices(range(1, 221), weights=[3 if i < 30 else 1 for i in range(1, 221)])[0]
        status = rng.choices(["paid", "completed", "cancelled", "refunded"], weights=[8, 77, 9, 6])[0]
        if day < END - timedelta(days=7) and status == "paid":
            status = "completed"
        picked = rng.sample(products, rng.randint(1, 4))
        paid = Decimal("0.00")
        for product in picked:
            quantity = rng.choices([1, 2, 3], weights=[7, 2, 1])[0]
            discount = rng.choice([Decimal("1"), Decimal("0.95"), Decimal("0.90"), Decimal("0.85")])
            line = money(product["list_price"] * quantity * discount) if status != "cancelled" else Decimal("0.00")
            paid += line
            items.append({"item_id": len(items) + 1, "order_id": oid, "product_id": product["product_id"], "quantity": quantity,
                          "unit_price": product["list_price"], "unit_cost": product["cost_price"], "line_paid_amount": line})
        orders.append({"order_id": oid, "customer_id": cid, "ordered_at": ordered_at.isoformat(sep=" "),
                       "paid_at": None if status == "cancelled" else (ordered_at + timedelta(minutes=rng.randrange(1, 20))).isoformat(sep=" "),
                       "status": status, "channel": rng.choices(["app", "web", "mini_program"], [6, 2, 2])[0],
                       "paid_amount": paid, "refund_amount": paid if status == "refunded" else Decimal("0.00")})
    dataset = {"customers": customers, "products": products, "orders": orders, "order_items": items}
    out = ROOT / "database"
    out.mkdir(parents=True, exist_ok=True)
    statements = ["-- Synthetic data, seed=20261016. Import after 01_schema.sql, once only.", "USE commerce_ai_demo;", "SET NAMES utf8mb4;", "START TRANSACTION;"]
    for table, rows in dataset.items():
        statements.append(insert_sql(table, list(rows[0]), rows))
    statements.append("COMMIT;")
    seed = "\n\n".join(statements) + "\n"
    (out / "02_seed.sql").write_text(seed, encoding="utf-8", newline="\n")
    # JSON fixture uses decimal strings to avoid monetary binary floating point drift.
    (out / "fixture.json").write_text(json.dumps(dataset, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    manifest = {"synthetic": True, "seed": SEED, "start_date": START.isoformat(), "end_date": END.isoformat(),
                "demo_today": "2026-10-16", "counts": {table: len(rows) for table, rows in dataset.items()},
                "valid_sales_statuses": ["paid", "completed"], "seed_sql_sha256": hashlib.sha256(seed.encode()).hexdigest()}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
