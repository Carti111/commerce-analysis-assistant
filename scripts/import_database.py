"""Interactive one-time import into the local MySQL server.

Asks for the administrator password locally; refuses existing project tables or
an existing reader account. Does not touch other schemas, and never drops data.
"""
from pathlib import Path
from urllib.parse import quote
import argparse
import getpass
import json
import os
import re
import secrets
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mysql", default=shutil.which("mysql") or r"D:\MySQL\Server\bin\mysql.exe")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3306)
    parser.add_argument("--user", default="root")
    parser.add_argument("--reader-user", default="commerce_reader")
    parser.add_argument("--dify-host", default="host.docker.internal")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,30}", args.reader_user):
        raise SystemExit("只读用户名只能包含英文字母、数字和下划线")
    if not Path(args.mysql).exists():
        raise SystemExit("找不到 mysql.exe，请用 --mysql 指定绝对路径")
    print("将创建独立数据库 commerce_ai_demo，不修改成绩库或其他业务库。")
    password = getpass.getpass(f"MySQL 管理账号 {args.user} 的密码（仅本机输入，不写入文件）：")
    base = [args.mysql, "--no-defaults", f"--host={args.host}", f"--port={args.port}", f"--user={args.user}", "--default-character-set=utf8mb4", "--batch", "--skip-column-names", "--connect-timeout=5"]

    def run(sql, reader_password=None):
        env = dict(os.environ)
        env["MYSQL_PWD"] = password if reader_password is None else reader_password
        cmd = list(base)
        if reader_password is not None:
            cmd[cmd.index(f"--user={args.user}")] = f"--user={args.reader_user}"
        result = subprocess.run(cmd, input=sql, text=True, encoding="utf-8", capture_output=True, env=env, timeout=60,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if result.returncode:
            raise RuntimeError(result.stderr.strip())
        return result.stdout.strip()

    tables = run("SELECT TABLE_NAME FROM information_schema.tables WHERE TABLE_SCHEMA='commerce_ai_demo';")
    if tables:
        raise SystemExit("commerce_ai_demo 已存在表，停止导入以保护现有数据。若此前已经完成初始化，直接继续配置 Dify 即可。")
    exists = run(f"SELECT COUNT(*) FROM mysql.user WHERE User='{args.reader_user}' AND Host='%';")
    if exists != "0":
        raise SystemExit("只读账号已存在。脚本不会重置账号，请用 --reader-user commerce_reader_v2 指定一个新名字。")
    run((ROOT / "database" / "01_schema.sql").read_text(encoding="utf-8"))
    run((ROOT / "database" / "02_seed.sql").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "database" / "manifest.json").read_text(encoding="utf-8"))
    for table, expected in manifest["counts"].items():
        if int(run(f"SELECT COUNT(*) FROM commerce_ai_demo.{table};")) != expected:
            raise RuntimeError("导入行数不符合预期，请检查数据库")
    reader_password = secrets.token_urlsafe(24)
    run(f"CREATE USER '{args.reader_user}'@'%' IDENTIFIED BY '{reader_password}';")
    for table in manifest["counts"]:
        run(f"GRANT SELECT ON commerce_ai_demo.{table} TO '{args.reader_user}'@'%';")
    run("SELECT COUNT(*) FROM commerce_ai_demo.orders;", reader_password=reader_password)
    uri = f"mysql+pymysql://{quote(args.reader_user, safe='')}:{quote(reader_password, safe='')}@{args.dify_host}:{args.port}/commerce_ai_demo?charset=utf8mb4"
    private = ROOT / ".local-db-uri.txt"
    private.write_text(uri + "\n", encoding="utf-8")
    print("初始化完成：240客户、32商品、1200订单、3043明细。")
    print(f"只读连接串已保存到 {private}。将内容填入 Dify 的 DB_URI 秘密变量；不要提交或分享此文件。")


if __name__ == "__main__":
    main()
