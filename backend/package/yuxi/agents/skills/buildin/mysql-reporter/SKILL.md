---
name: mysql reporter
slug: mysql-reporter
description: "Generate MySQL query reports and generate visual charts. Use this skill when users need to query the MySQL database and display the results in the form of reports, including: counting sales data, analyzing user behavior, generating business reports, querying business indicators, etc."
---

# MySQL reporting skills

According to the user's instructions, access the MySQL database through terminal scripts and combine it with chart drawing tools to build SQL query reports.

## Operation process

1. Understand user instructions and clarify report needs and goals
2. Enter the skills directory through terminal: `cd /home/gem/skills/mysql-reporter`
3. Use `uv run scripts/list_tables.py` to view available tables; if the script prompts that MySQL configuration is missing, reply to the user according to "Handling missing environment variables"
4. If necessary, use `uv run scripts/describe_table.py --table table name` to view the table structure
5. Generate correct and efficient read-only SQL, execute the query and obtain the results through `uv run scripts/query.py --sql "SQL statement" --timeout 60`
6. Use Charts MCP to generate charts
7. Embed the chart into the report in markdown image format

## Handling missing environment variables

The script only reads environment variables in the Agent sandbox, not backend `.env` or Docker Compose variables. Required variables include:

- `MYSQL_HOST`
- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `MYSQL_DATABASE`

Optional variables include:

- `MYSQL_PORT`: default `3306`
- `MYSQL_DATABASE_DESCRIPTION`: database business description, used to assist in understanding the meaning of tables and indicators

If `MySQL configuration missing required key` appears when executing a script, do not continue to guess connection information or make up reports. Users should be clearly told that they need to configure the missing `MYSQL_*` variables in the "Sandbox Environment Variables" in personal settings; after saving, they will only take effect for new sandboxes, and they need to re-initiate the task or create a new session before executing.

## Key constraints

- The generated SQL queries must be correct and efficient to avoid full table scans
- MySQL operations must be executed through the CLI script under `scripts/` in this skill. Do not call the platform's built-in MySQL tools.
- Do not output the values ​​of sensitive environment variables such as `MYSQL_PASSWORD` in reports or error descriptions. Only indicate which variable names are missing.
- The results returned by the chart generation tool will not be rendered by default and must be embedded in the final report in the format of `![Description](Picture URL)`
- Only return conclusions related to the report, do not return the original SQL query statement

## Allowed tools

- terminal: execute `scripts/list_tables.py`, `scripts/describe_table.py`, `scripts/query.py`
- Charts MCP: generate visual charts
- Web search tool: add background information if necessary
