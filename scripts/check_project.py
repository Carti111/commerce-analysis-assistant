"""Local contract/fixture checks; no model calls and no database credentials required."""
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
import hashlib
import json
import re
import runpy
import unittest

ROOT = Path(__file__).resolve().parents[1]
GUARD = runpy.run_path(str(ROOT / "nodes" / "sql_guard.py"))
CHART = runpy.run_path(str(ROOT / "nodes" / "chart_parameters.py"))["main"]
CAPTURE = runpy.run_path(str(ROOT / "nodes" / "capture_result.py"))["main"]


def plan(sql):
    return json.dumps({"status": "ok", "queries": [{"title": "test", "sql": sql, "metric_note": "test"}]})


class ProjectChecks(unittest.TestCase):
    def test_all_reference_queries_pass_guard(self):
        cases = json.loads((ROOT / "evaluation" / "cases.json").read_text(encoding="utf-8"))
        for case in cases:
            if "reference_sql" not in case:
                continue
            with self.subTest(case=case["id"]):
                result = GUARD["main"](plan(case["reference_sql"]))
                self.assertEqual(result["ready"], "1", result["diagnostic"])
                self.assertIn("MAX_EXECUTION_TIME(5000)", result["result"][0]["sql"])

    def test_guard_rejects_write_or_bypass_queries(self):
        queries = [
            "DELETE FROM orders", "SELECT order_id FROM orders; DELETE FROM orders;",
            "SELECT order_id FROM orders UNION SELECT customer_id FROM customers",
            "SELECT user FROM mysql.user", "SELECT customer_name FROM information_schema.tables",
            "SELECT SLEEP(10) FROM orders", "SELECT LOAD_FILE('/etc/passwd') FROM orders",
            "SELECT paid_amount INTO OUTFILE '/tmp/result' FROM orders",
            "SELECT /* benign */ order_id FROM orders", "SELECT /*!50000 SLEEP(1) */ order_id FROM orders",
            "WITH temp AS (SELECT order_id FROM orders) SELECT order_id FROM temp",
            "SELECT o.order_id FROM orders o,order_items i",
            "SELECT o.order_id FROM orders o JOIN order_items i",
            "SELECT order_id FROM other_db.orders", "SELECT order_id FROM orders LIMIT 101",
            "SELECT order_id FROM orders LIMIT 10 OFFSET 10", "SELECT order_id FROM orders FOR UPDATE",
            "SELECT unknown_function(paid_amount) FROM orders", "SELECT @password FROM orders",
        ]
        for sql in queries:
            with self.subTest(sql=sql):
                self.assertEqual(GUARD["main"](plan(sql))["ready"], "0")

    def test_literals_are_not_keywords_or_comments(self):
        sql = "SELECT customer_name FROM customers WHERE customer_name='DROP -- <think>中文</think>' LIMIT 1;"
        result = GUARD["main"](plan(sql))
        self.assertEqual(result["ready"], "1", result["diagnostic"])
        self.assertIn("DROP -- <think>中文</think>", result["result"][0]["sql"])

    def test_missing_limit_is_added(self):
        self.assertTrue(GUARD["validate_sql"]("SELECT order_id FROM orders").endswith("LIMIT 100;"))

    def test_invalid_batch_never_executes_partial_plan(self):
        data = {"status": "ok", "queries": [{"title": "valid", "sql": "SELECT order_id FROM orders"}, {"title": "invalid", "sql": "DROP TABLE orders"}]}
        result = GUARD["main"](json.dumps(data))
        self.assertEqual(result["ready"], "0")
        self.assertEqual(result["result"], [])

    def test_reasoning_and_fences_do_not_supply_example_query(self):
        raw = '<think>示例 {"status":"ok","queries":[{"title":"错","sql":"DELETE FROM orders"}]}</think>\n```json\n' + plan("SELECT order_id FROM orders LIMIT 1") + "\n```"
        self.assertEqual(GUARD["main"](raw)["ready"], "1")
        self.assertEqual(GUARD["main"]("<think>未闭合" + plan("SELECT order_id FROM orders"))["ready"], "0")

    def test_clarification_has_no_sql(self):
        result = GUARD["main"]('{"status":"clarify","message":"需要哪个指标？","queries":[]}')
        self.assertEqual(result["ready"], "0")
        self.assertEqual(result["result"], [])
        self.assertEqual(result["message"], "需要哪个指标？")

    def test_empty_result_and_missing_plugin_output_differ(self):
        result = CAPTURE([{"result": []}], "empty", "SELECT ...", "note")
        self.assertEqual(result["result"]["row_count"], 0)
        for invalid in [[], [{"error": "connection failed"}], [{"result": "not rows"}]]:
            with self.assertRaises(ValueError):
                CAPTURE(invalid, "test", "SELECT ...", "note")

    def test_chart_points_and_number_validation(self):
        data = {"results": "表格", "ECHarts": "1", "chartType": "柱状图", "chartTitle": "品类销售额", "chartData": "100.2;200", "chartXAxis": "数码配件;家居日用"}
        self.assertEqual(CHART(json.dumps(data))["chartData"], "100.2;200")
        for changes in [{"chartXAxis": "只有一个标签"}, {"chartData": "NaN;2"}, {"chartData": "100元;200"}, {"chartType": "散点图"}, {"chartData": "-1;2", "chartType": "饼状图"}]:
            with self.assertRaises(ValueError):
                CHART(json.dumps({**data, **changes}))
        no_chart = CHART('{"results":"无记录","ECHarts":"0"}')
        self.assertEqual(no_chart["chartData"], "")

    def test_fixture_accounting_and_foreign_keys(self):
        data = json.loads((ROOT / "database" / "fixture.json").read_text(encoding="utf-8"))
        customers = {r["customer_id"] for r in data["customers"]}
        products = {r["product_id"] for r in data["products"]}
        orders = {r["order_id"]: r for r in data["orders"]}
        sums = defaultdict(Decimal)
        pairs = set()
        for item in data["order_items"]:
            self.assertIn(item["order_id"], orders)
            self.assertIn(item["product_id"], products)
            self.assertNotIn((item["order_id"], item["product_id"]), pairs)
            pairs.add((item["order_id"], item["product_id"]))
            sums[item["order_id"]] += Decimal(item["line_paid_amount"])
        for order in orders.values():
            self.assertIn(order["customer_id"], customers)
            self.assertEqual(Decimal(order["paid_amount"]), sums[order["order_id"]])
            self.assertEqual(Decimal(order["refund_amount"]), Decimal(order["paid_amount"]) if order["status"] == "refunded" else Decimal(0))
        manifest = json.loads((ROOT / "database" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["seed_sql_sha256"], hashlib.sha256((ROOT / "database" / "02_seed.sql").read_bytes()).hexdigest())

    def test_dsl_references_and_embedded_code(self):
        dsl = json.loads((ROOT / "workflow" / "电商经营分析助手.yml").read_text(encoding="utf-8"))
        graph = dsl["workflow"]["graph"]
        nodes = {node["id"]: node for node in graph["nodes"]}
        self.assertEqual(len(nodes), len(graph["nodes"]))
        for edge in graph["edges"]:
            self.assertIn(edge["source"], nodes)
            self.assertIn(edge["target"], nodes)
        for node in nodes.values():
            data = node["data"]
            if data["type"] == "code":
                compile(data["code"], "embedded", "exec")
                for var in data["variables"]:
                    selector = var["value_selector"]
                    self.assertIn(selector[0], nodes)
                    source = nodes[selector[0]]["data"]
                    if source["type"] == "code":
                        self.assertIn(selector[1], source["outputs"])
            for source_id, field in re.findall(r"\{\{#([^.#]+)\.([^#]+)#\}\}", json.dumps(data, ensure_ascii=False)):
                if source_id in {"env", "sys"}:
                    continue
                self.assertIn(source_id, nodes)
                if nodes[source_id]["data"]["type"] == "code":
                    self.assertIn(field, nodes[source_id]["data"]["outputs"])
        self.assertEqual(dsl["workflow"]["environment_variables"][0]["value"], "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
