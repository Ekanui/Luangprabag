"""
migrate_data.py
Run once to import your existing MySQL data into SQLite.

Usage:
    python migrate_data.py

This reads luangprabang_heritage.sql and imports:
  - heritage_categories
  - heritage_houses (including house ID 28 / Xieng Thong)
  - heritage_images
  - users (with existing bcrypt hashes — compatible with werkzeug)
  - visit_logs
"""

import sqlite3, re, os

DB_PATH  = os.environ.get('DB_PATH', 'heritage.db')
SQL_FILE = 'luangprabang_heritage.sql'

def run():
    if not os.path.exists(SQL_FILE):
        print(f"❌  {SQL_FILE} not found. Put it in the same folder as this script.")
        return

    # Init schema first
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = OFF")   # Off during import
    conn.executescript(open('schema.sql').read())

    sql = open(SQL_FILE, encoding='utf-8').read()

    # ── heritage_categories ───────────────────────────────────
    cats = re.findall(
        r"INSERT INTO `heritage_categories`.*?VALUES\s*(.*?);",
        sql, re.DOTALL
    )
    for block in cats:
        rows = re.findall(r"\(([^)]+)\)", block)
        for row in rows:
            vals = _parse_row(row)
            conn.execute(
                "INSERT OR IGNORE INTO heritage_categories (category_id, category_name_lo, category_name_en) VALUES (?,?,?)",
                vals[:3]
            )
    print(f"  ✅  Imported categories")

    # ── heritage_houses ────────────────────────────────────────
    houses = re.findall(
        r"INSERT INTO `heritage_houses`.*?VALUES\s*(.*?);",
        sql, re.DOTALL
    )
    house_cols = (
        "house_id,qr_code,house_number,house_name_lo,house_name_en,"
        "owner_name_lo,owner_name_en,construction_year,"
        "architectural_style_lo,architectural_style_en,"
        "historical_significance_lo,historical_significance_en,"
        "description_lo,description_en,image_main,status,"
        "house_type,building_material,created_at,updated_at"
    ).split(',')
    for block in houses:
        rows = _split_value_tuples(block)
        for row in rows:
            vals = _parse_row(row)
            placeholders = ','.join('?' * len(house_cols))
            conn.execute(
                f"INSERT OR IGNORE INTO heritage_houses ({','.join(house_cols)}) VALUES ({placeholders})",
                vals[:len(house_cols)]
            )
    print(f"  ✅  Imported houses")

    # ── heritage_images ────────────────────────────────────────
    imgs = re.findall(
        r"INSERT INTO `heritage_images`.*?VALUES\s*(.*?);",
        sql, re.DOTALL
    )
    for block in imgs:
        rows = _split_value_tuples(block)
        for row in rows:
            vals = _parse_row(row)
            conn.execute(
                "INSERT OR IGNORE INTO heritage_images (image_id,house_id,image_path,image_caption_lo,image_caption_en,display_order) VALUES (?,?,?,?,?,?)",
                vals[:6]
            )
    print(f"  ✅  Imported images")

    # ── users ──────────────────────────────────────────────────
    users = re.findall(
        r"INSERT INTO `users`.*?VALUES\s*(.*?);",
        sql, re.DOTALL
    )
    user_cols = "user_id,username,password,fullname_lo,fullname_en,email,role,status,created_at".split(',')
    for block in users:
        rows = _split_value_tuples(block)
        for row in rows:
            vals = _parse_row(row)
            conn.execute(
                f"INSERT OR IGNORE INTO users ({','.join(user_cols)}) VALUES ({','.join('?'*len(user_cols))})",
                vals[:len(user_cols)]
            )
    print(f"  ✅  Imported users (passwords preserved)")

    # ── visit_logs ─────────────────────────────────────────────
    logs = re.findall(
        r"INSERT INTO `visit_logs`.*?VALUES\s*(.*?);",
        sql, re.DOTALL
    )
    for block in logs:
        rows = _split_value_tuples(block)
        for row in rows:
            vals = _parse_row(row)
            conn.execute(
                "INSERT OR IGNORE INTO visit_logs (log_id,house_id,visitor_ip,visitor_device,visit_date,visit_time) VALUES (?,?,?,?,?,?)",
                vals[:6]
            )
    print(f"  ✅  Imported visit_logs")

    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()
    conn.close()
    print(f"\n🎉  Done! Database saved to: {DB_PATH}")
    print("    Run `python app.py` to start the server.")

# ── helpers ────────────────────────────────────────────────────
def _split_value_tuples(block):
    """Split a VALUES block like (1,'a','b'),(2,'c','d') into individual rows."""
    tuples, depth, current, in_str, escape = [], 0, '', False, False
    for ch in block:
        if escape:
            current += ch; escape = False; continue
        if ch == '\\' and in_str:
            current += ch; escape = True; continue
        if ch == "'" and not escape:
            in_str = not in_str; current += ch; continue
        if not in_str:
            if ch == '(': depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0:
                    tuples.append(current.strip()); current = ''; continue
        current += ch
    return tuples

def _parse_row(row):
    """Parse a single tuple row like 1,'hello','world',NULL into Python values."""
    vals, current, in_str, escape = [], '', False, False
    for ch in row:
        if escape:
            if ch == 'n': current += '\n'
            elif ch == 'r': current += '\r'
            elif ch == 't': current += '\t'
            else: current += ch
            escape = False; continue
        if ch == '\\' and in_str:
            escape = True; continue
        if ch == "'" and not in_str:
            in_str = True; continue
        if ch == "'" and in_str:
            in_str = False; continue
        if ch == ',' and not in_str:
            vals.append(_coerce(current.strip())); current = ''; continue
        current += ch
    vals.append(_coerce(current.strip()))
    return vals

def _coerce(v):
    if v.upper() == 'NULL': return None
    if re.match(r"^-?\d+$", v): return int(v)
    if re.match(r"^-?\d+\.\d+$", v): return float(v)
    return v

if __name__ == '__main__':
    run()
