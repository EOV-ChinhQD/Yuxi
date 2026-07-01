# /// script
# dependencies = [
#   "pymysql>=1.1.0",
# ]
# ///

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Any

import pymysql
from pymysql import MySQLError
from pymysql.cursors import DictCursor


class MySQLConnectionError(Exception):
    """MySQL Connection abnormality"""


def load_mysql_config() -> dict[str, Any]:
    config: dict[str, Any] = {
        "host": os.getenv("MYSQL_HOST"),
        "user": os.getenv("MYSQL_USER"),
        "password": os.getenv("MYSQL_PASSWORD"),
        "database": os.getenv("MYSQL_DATABASE"),
        "port": int(os.getenv("MYSQL_PORT") or "3306"),
        "charset": "utf8mb4",
        "description": os.getenv("MYSQL_DATABASE_DESCRIPTION") or "CSDL MySQL mặc định",
    }

    required_keys = ["host", "user", "password", "database"]
    for key in required_keys:
        if not config[key]:
            raise MySQLConnectionError(
                f"MySQL configuration missing required key: {key}, please check your environment variables."
            )

    return config


def create_connection(config: dict[str, Any]) -> pymysql.Connection:
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return pymysql.connect(
                host=config["host"],
                user=config["user"],
                password=config["password"],
                database=config["database"],
                port=config["port"],
                charset=config.get("charset", "utf8mb4"),
                cursorclass=DictCursor,
                connect_timeout=10,
                read_timeout=60,
                write_timeout=30,
                autocommit=True,
            )
        except MySQLError as exc:
            if attempt < max_retries - 1:
                time.sleep(2**attempt)
                continue
            raise ConnectionError(f"MySQL connection failed: {exc}") from exc

    raise ConnectionError("MySQL connection failed")


def list_tables() -> str:
    config = load_mysql_config()
    connection = create_connection(config)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()

        if not tables:
            return "Không tìm thấy bất kỳ bảng nào trong cơ sở dữ liệu"

        table_names = []
        for table in tables:
            table_name = list(table.values())[0]
            table_names.append(table_name)

        all_table_names = "\n".join(table_names)
        result = f"Các bảng trong cơ sở dữ liệu:\n{all_table_names}"
        if db_note := config.get("description"):
            result = f"Mô tả cơ sở dữ liệu: {db_note}\n\n" + result
        return result
    finally:
        connection.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Liệt kê tất cả các bảng trong cơ sở dữ liệu MySQL hiện tại")
    return parser.parse_args()


def main() -> int:
    parse_args()
    try:
        print(list_tables())
        return 0
    except Exception as exc:
        print(f"Lấy tên bảng thất bại: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
