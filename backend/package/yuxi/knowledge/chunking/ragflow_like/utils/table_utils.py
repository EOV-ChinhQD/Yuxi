from __future__ import annotations

from bs4 import BeautifulSoup


def html_table_to_markdown(html: str) -> str:
    """
    Specific implementation of converting HTML tables to Markdown format
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        return ""

    rows = table.find_all("tr")
    if not rows:
        return ""

    grid = []

    for r_idx, row in enumerate(rows):
        while len(grid) <= r_idx:
            grid.append([])

        cells = row.find_all(["td", "th"])
        c_idx = 0

        for cell in cells:
            while c_idx < len(grid[r_idx]) and grid[r_idx][c_idx] is not None:
                c_idx += 1

            text = cell.get_text(strip=True)
            text = text.replace("\n", " ")

            rowspan = int(cell.get("rowspan", 1))
            colspan = int(cell.get("colspan", 1))

            for r in range(rowspan):
                target_r = r_idx + r
                while len(grid) <= target_r:
                    grid.append([])

                for c in range(colspan):
                    target_c = c_idx + c
                    while len(grid[target_r]) <= target_c:
                        grid[target_r].append(None)

                    grid[target_r][target_c] = text

            c_idx += colspan

    if not grid:
        return ""

    markdown_lines = []
    max_cols = max(len(r) for r in grid)
    for r in grid:
        while len(r) < max_cols:
            r.append("")

    header = grid[0]
    header = [h if h is not None else "" for h in header]
    markdown_lines.append("| " + " | ".join(header) + " |")
    markdown_lines.append("|" + "|".join([" --- " for _ in range(max_cols)]) + "|")

    for row in grid[1:]:
        row_clean = [cell if cell is not None else "" for cell in row]
        line = "| " + " | ".join(row_clean) + " |"
        markdown_lines.append(line)

    return "\n".join(markdown_lines)


def html_table_to_key_value(html: str) -> list[str]:
    """
    Convert the HTMLsheet into a key-value pair Formatof column surface, in order to deal with the overly long sheetof cut pointquestion.

    Processing logic:
    1. **mesh reconstruction**: Since HTML tables may contain `rowspan` and `colspan` (merged cells),
       The function first builds a oneindivual complete oftwo-dimensional grid (grid).
    2. **Cell expansion**: Traverse HTML rows and columns, and when encountering a merged cell, fill its content with all affected coordinate points in the arrival grid.
       This ensures that the originally merged of area has a corresponding of value for each individual point in the logical grid.
    3. **Key-value pair conversion**：
       - Think of the first row of the grid as the header (Key).
       - Starting from the second row, correspond each row to the table header to generate "key:value" form ofcharacter string.

    For example：
    - Input: HTML table, including three columns: name, age, and gender.
    - Output:['Name: Zhang San; Age: 25; Gender: Male', 'Name: Li Si; Age: 30; Gender: Female']
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        return []

    rows = table.find_all("tr")
    if not rows:
        return []

    grid = []

    for r_idx, row in enumerate(rows):
        while len(grid) <= r_idx:
            grid.append([])

        cells = row.find_all(["td", "th"])
        c_idx = 0

        for cell in cells:
            while c_idx < len(grid[r_idx]) and grid[r_idx][c_idx] is not None:
                c_idx += 1

            text = cell.get_text(strip=True)
            rowspan = int(cell.get("rowspan", 1))
            colspan = int(cell.get("colspan", 1))

            for r in range(rowspan):
                target_r = r_idx + r
                while len(grid) <= target_r:
                    grid.append([])

                for c in range(colspan):
                    target_c = c_idx + c
                    while len(grid[target_r]) <= target_c:
                        grid[target_r].append(None)
                    grid[target_r][target_c] = text
            c_idx += colspan

    if not grid:
        return []

    headers = grid[0]
    headers = [h if h is not None else "" for h in headers]

    kv_lines = []
    for row_values in grid[1:]:
        min_len = min(len(headers), len(row_values))
        row_parts = []
        for i in range(min_len):
            key = headers[i]
            val = row_values[i] if row_values[i] is not None else ""
            if key:
                row_parts.append(f"{key}：{val}")
        if row_parts:
            kv_lines.append("；".join(row_parts) + "；")

    return kv_lines
