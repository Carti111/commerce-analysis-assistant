"""Verify fixtures/reference queries in a disposable LOCAL MySQL instance.

Never connects to the user's existing server; uses --no-defaults and a fresh
workspace datadir bound to 127.0.0.1 on an ephemeral port. Requires mysql binaries.
"""
from decimal import Decimal, InvalidOperation
from pathlib import Path
import argparse
import json
import os
import secrets
import shutil
import socket
import subprocess
import time
import runpy

ROOT = Path(__file__).resolve().parents[1]


def canonical(value):
    if value is None or value == "NULL":
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return str(value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mysql-bin", default=r"D:\MySQL\Server\bin")
    args = parser.parse_args()
    mysql_bin = Path(args.mysql_bin).resolve()
    mysqld = mysql_bin / ("mysqld.exe" if os.name == "nt" else "mysqld")
    mysql = mysql_bin / ("mysql.exe" if os.name == "nt" else "mysql")
    mysqladmin = mysql_bin / ("mysqladmin.exe" if os.name == "nt" else "mysqladmin")
    if not all(p.exists() for p in [mysqld, mysql, mysqladmin]):
        raise SystemExit("未找到 MySQL 程序，请用 --mysql-bin 指定安装目录")
    temp_parent = (ROOT / "tmp").resolve()
    temp_parent.mkdir(exist_ok=True)
    # Windows' restrictive mkdtemp ACLs can exclude the sandbox token itself.
    work = (temp_parent / ("commerce_mysql_verify_" + secrets.token_hex(6))).resolve()
    work.mkdir()
    assert work.is_relative_to(temp_parent) and work.name.startswith("commerce_mysql_verify_")
    datadir = work / "data"
    datadir.mkdir()
    log = work / "mysql-error.log"
    creation = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    server = None
    report = {"scope": "temporary MySQL instance; no Dify model calls", "reference_queries": [], "permission_checks": []}
    password = secrets.token_urlsafe(24)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = [str(mysql), "--no-defaults", "--host=127.0.0.1", f"--port={port}", "--user=root", "--default-character-set=utf8mb4", "--batch", "--raw", "--connect-timeout=2"]

    def run(sql, reader=False, database=True, check=True):
        cmd = list(base)
        environment = dict(os.environ)
        environment.pop("MYSQL_PWD", None)
        if reader:
            cmd[cmd.index("--user=root")] = "--user=commerce_verify_reader"
            environment["MYSQL_PWD"] = password
        if database:
            cmd.append("commerce_ai_demo")
        result = subprocess.run(cmd, input=sql, text=True, encoding="utf-8", capture_output=True, env=environment, creationflags=creation, timeout=40)
        if check and result.returncode:
            raise RuntimeError(result.stderr.strip())
        return result

    def query(sql, reader=False):
        output = run(sql, reader=reader).stdout.splitlines()
        if not output:
            return []
        columns = output[0].split("\t")
        return [dict(zip(columns, row.split("\t"))) for row in output[1:]]

    started = time.monotonic()
    try:
        init = subprocess.run([str(mysqld), "--no-defaults", "--initialize-insecure", f"--basedir={mysql_bin.parent}", f"--datadir={datadir}", f"--log-error={log}"], creationflags=creation, capture_output=True, timeout=90)
        if init.returncode:
            raise RuntimeError(log.read_text(encoding="utf-8", errors="replace")[-5000:] if log.exists() else init.stderr.decode(errors="replace"))
        server = subprocess.Popen([str(mysqld), "--no-defaults", f"--basedir={mysql_bin.parent}", f"--datadir={datadir}", f"--port={port}", "--bind-address=127.0.0.1", "--mysqlx=OFF", "--skip-log-bin", "--performance-schema=OFF", "--innodb-buffer-pool-size=64M", f"--log-error={log}", f"--pid-file={work / 'mysql.pid'}", f"--secure-file-priv={work}"], creationflags=creation, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            if server.poll() is not None:
                raise RuntimeError(log.read_text(encoding="utf-8", errors="replace")[-5000:])
            if run("SELECT 1;", database=False, check=False).returncode == 0:
                break
            time.sleep(.5)
        else:
            raise RuntimeError("临时 MySQL 启动超时")
        report["mysql_version"] = run("SELECT VERSION();", database=False).stdout.splitlines()[-1]
        run((ROOT / "database" / "01_schema.sql").read_text(encoding="utf-8"), database=False)
        run((ROOT / "database" / "02_seed.sql").read_text(encoding="utf-8"))
        report["table_counts"] = {table: int(query(f"SELECT COUNT(*) AS count FROM {table};")[0]["count"]) for table in ["customers", "products", "orders", "order_items"]}
        run(f"CREATE USER 'commerce_verify_reader'@'localhost' IDENTIFIED BY '{password}';" + "".join(f"GRANT SELECT ON commerce_ai_demo.{table} TO 'commerce_verify_reader'@'localhost';" for table in report["table_counts"]))
        cases = json.loads((ROOT / "evaluation" / "cases.json").read_text(encoding="utf-8"))
        guard = runpy.run_path(str(ROOT / "nodes" / "sql_guard.py"))["validate_sql"]
        for case in cases:
            if "reference_sql" not in case:
                continue
            actual = query(guard(case["reference_sql"]), reader=True)
            expected = case["expected_rows"]
            if len(actual) != len(expected):
                raise AssertionError(f"{case['id']} 行数不一致：{len(actual)} != {len(expected)}")
            for left, right in zip(actual, expected):
                if {k: canonical(v) for k, v in left.items()} != {k: canonical(v) for k, v in right.items()}:
                    raise AssertionError(f"{case['id']} 结果不一致：{left} != {right}")
            report["reference_queries"].append({"id": case["id"], "passed": True, "rows": len(actual)})
        for sql, name in [
            ("DELETE FROM orders WHERE order_id=-1;", "DELETE denied"),
            ("UPDATE orders SET paid_amount=0 WHERE order_id=-1;", "UPDATE denied"),
            ("SELECT User FROM mysql.user;", "cross-database SELECT denied"),
        ]:
            result = run(sql, reader=True, check=False)
            if result.returncode == 0 or "denied" not in result.stderr.lower():
                raise AssertionError(f"只读权限校验失败：{name}")
            report["permission_checks"].append({"check": name, "passed": True})
        report.update(passed=True, elapsed_seconds=round(time.monotonic() - started, 2), end_to_end_llm_accuracy="not measured")
    except Exception as error:
        report.update(passed=False, error=str(error))
        raise
    finally:
        if server is not None and server.poll() is None:
            shutdown = subprocess.run([str(mysqladmin), "--no-defaults", "--host=127.0.0.1", f"--port={port}", "--user=root", "--connect-timeout=2", "shutdown"], creationflags=creation, capture_output=True, timeout=15)
            try:
                server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server.terminate()
                server.wait(timeout=10)
        report_path = ROOT / "evaluation" / "mysql_validation_report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        if not report.get("passed") and log.exists():
            (ROOT / "evaluation" / "mysql_validation_error.log").write_text(log.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
        # Only delete our exact newly created temp directory, within the verified workspace tmp root.
        if (server is None or server.poll() is not None) and work.is_relative_to(temp_parent) and work.name.startswith("commerce_mysql_verify_"):
            shutil.rmtree(work)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
