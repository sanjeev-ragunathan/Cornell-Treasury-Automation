# NOTE: This code runs inside n8n's Python Code node where top-level
# return statements are valid. Pylance warnings about "return outside
# function" can be safely ignored.

def excel_date_to_string(value):
    if value in [None, ""]:
        return None
    if isinstance(value, (int, float)):
        n = int(value)
        y = 1900
        m = 1
        d = n - 2
        dim = [31,28,31,30,31,30,31,31,30,31,30,31]
        while True:
            leap = (y % 4 == 0 and y % 100 != 0) or (y % 400 == 0)
            dim[1] = 29 if leap else 28
            if d <= dim[m - 1]:
                break
            d -= dim[m - 1]
            m += 1
            if m > 12:
                m = 1
                y += 1
        return f"{y:04d}-{m:02d}-{d:02d}"
    return str(value).split(" ")[0]

def format_row(row):
    parts = []
    for key, value in row.items():
        if value not in [None, "", "undefined"]:
            if key == "Date":
                value = excel_date_to_string(value)
            parts.append(f"{key}: {value}")
    return " | ".join(parts)

grouped = []
current_group = None

for item in _items:
    row = item["json"]
    date_value = row.get("Date")
    amount_value = row.get("Amount")
    if date_value not in [None, ""]:
        current_group = {
            "record_date": date_value,
            "record_amount": amount_value,
            "rows": []
        }
        grouped.append(current_group)
    if current_group is not None:
        current_group["rows"].append(row)

output = []
for group in grouped:
    formatted_rows = "\n".join(format_row(row) for row in group["rows"])
    output.append({
        "json": {
            "record_date": excel_date_to_string(group["record_date"]),
            "record_amount": group.get("record_amount"),
            "record_text": formatted_rows
        }
    })

return output