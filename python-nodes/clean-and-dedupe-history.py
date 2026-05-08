# NOTE: This code runs inside n8n's Python Code node where top-level
# return statements are valid. Pylance warnings about "return outside
# function" can be safely ignored.

import re

output = []
MAX_RECENT_PER_KEY = 3

def parse_date(value):
    if value in [None, "", "undefined"]:
        return None
    text = str(value).strip()
    # try M/D/YYYY
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", text)
    if m:
        return (int(m.group(3)), int(m.group(1)), int(m.group(2)))
    # try YYYY-MM-DD
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", text)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    # try M-D-YYYY
    m = re.match(r"^(\d{1,2})-(\d{1,2})-(\d{4})$", text)
    if m:
        return (int(m.group(3)), int(m.group(1)), int(m.group(2)))
    return None

def date_to_string(d):
    if d is None:
        return None
    y, m, day = d
    return f"{y:04d}-{m:02d}-{day:02d}"

def date_to_days(d):
    """Convert (y, m, d) to a rough day number for comparison."""
    if d is None:
        return 0
    y, m, day = d
    return y * 365 + m * 30 + day

def to_float(value):
    if value in [None, "", "undefined"]:
        return 0.0
    try:
        return float(str(value).replace(",", "").strip())
    except Exception:
        return 0.0

def normalize_text(value):
    if value in [None, "", "undefined"]:
        return ""
    text = str(value).lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def build_pattern_key(row):
    gl_desc = normalize_text(row.get("GL Transaction Description"))
    org = normalize_text(row.get("Specific Org"))
    acct = normalize_text(row.get("Acct And Name"))
    obj = normalize_text(row.get("Object Cd And Name"))
    return " | ".join([gl_desc, org, acct, obj])

rows = []

for item in _items:
    raw = item["json"]
    post_date = parse_date(raw.get("Post Date"))
    if post_date is None:
        continue

    debit = to_float(raw.get("Debit Amount"))
    credit = to_float(raw.get("Credit Amount"))
    net_amount = credit - debit

    def safe_str(v):
        if v is None:
            return ""
        return str(v).strip()

    row = {
        "post_date": date_to_string(post_date),
        "gl_transaction_description": safe_str(raw.get("GL Transaction Description")),
        "specific_org": safe_str(raw.get("Specific Org")),
        "acct_and_name": safe_str(raw.get("Acct And Name")),
        "object_cd_and_name": safe_str(raw.get("Object Cd And Name")),
        "edoc_nbr": safe_str(raw.get("EDOC Nbr")),
        "edoc_description": safe_str(raw.get("EDoc Description")),
        "debit_amount": debit,
        "credit_amount": credit,
        "net_amount": net_amount,
        "_date_days": date_to_days(post_date),
        "_pattern_key": build_pattern_key(raw),
    }
    if "@" in row["edoc_nbr"]:
        row["edoc_nbr"] = ""
    if row["specific_org"].isdigit():
        row["specific_org"] = ""
    rows.append(row)

if not rows:
    return []

max_days = max(r["_date_days"] for r in rows)
cutoff_days = max_days - 365

recent_rows = []
older_rows = []

for row in rows:
    if row["_date_days"] >= cutoff_days:
        recent_rows.append(row)
    else:
        older_rows.append(row)

recent_rows.sort(key=lambda r: r["_date_days"], reverse=True)
older_rows.sort(key=lambda r: r["_date_days"], reverse=True)

recent_key_counts = {}
filtered_recent_rows = []
recent_keys = set()

for row in recent_rows:
    key = row["_pattern_key"]
    if not key:
        continue
    count = recent_key_counts.get(key, 0)
    if count < MAX_RECENT_PER_KEY:
        filtered_recent_rows.append(row)
        recent_key_counts[key] = count + 1
        recent_keys.add(key)

older_unique_rows = []
seen_old_keys = set()

for row in older_rows:
    key = row["_pattern_key"]
    if not key:
        continue
    if key not in recent_keys and key not in seen_old_keys:
        older_unique_rows.append(row)
        seen_old_keys.add(key)

filtered_rows = filtered_recent_rows + older_unique_rows
filtered_rows.sort(key=lambda r: r["_date_days"], reverse=True)

for row in filtered_rows:
    clean = dict(row)
    clean.pop("_date_days", None)
    clean.pop("_pattern_key", None)
    clean["row_id"] = str(len(output))
    output.append({"json": clean})

return output