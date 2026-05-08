# NOTE: This code runs inside n8n's Python Code node where top-level
# return statements are valid. Pylance warnings about "return outside
# function" can be safely ignored.

import json

output = []

for item in _items:
    data = item["json"]

    record_date = data.get("record_date", "unknown")
    record_amount = data.get("record_amount", "unknown")
    record_text = data.get("record_text", "")
    history_matches = data.get("history_matches", [])
    consensus_org = data.get("history_consensus_org")
    consensus_count = data.get("history_consensus_count", 0)

    # format history matches into readable text
    if history_matches:
        match_lines = []
        for i, m in enumerate(history_matches, 1):
            score = m.get("match_score", 0)
            org = m.get("specific_org", "unknown")
            gl_desc = m.get("gl_transaction_description", "")
            acct = m.get("acct_and_name", "")
            obj = m.get("object_cd_and_name", "")
            amount = m.get("net_amount", "")
            reasons = ", ".join(m.get("match_reasons", []))
            edoc = m.get("edoc_description", "")

            line = f"Match {i} (score: {score}, reasons: {reasons}):"
            line += f"\n  Org: {org}"
            line += f"\n  GL Description: {gl_desc}" if gl_desc else ""
            line += f"\n  Account: {acct}" if acct else ""
            line += f"\n  Object: {obj}" if obj else ""
            line += f"\n  EDoc: {edoc}" if edoc else ""
            line += f"\n  Amount: ${amount}" if amount else ""
            match_lines.append(line)

        history_section = "\n\n".join(match_lines)

        if consensus_org:
            history_section += f"\n\nHistory consensus: {consensus_org} ({consensus_count} weighted matches support this)"
        else:
            history_section += "\n\nNo clear consensus across history matches."
    else:
        history_section = "No historical matches found for this payment."

    prompt = f"""CURRENT PAYMENT
Date: {record_date}
Amount: ${record_amount}
Payment Details:
{record_text}

HISTORICAL MATCHES
{history_section}"""

    # pass through all original fields plus the formatted prompt
    out = dict(data)
    out["formatted_prompt"] = prompt
    output.append({"json": out})

return output