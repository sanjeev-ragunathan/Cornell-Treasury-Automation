# NOTE: This code runs inside n8n's Python Code node where top-level
# return statements are valid. Pylance warnings about "return outside
# function" can be safely ignored.

import json
import re

output = []

BAD_DEPARTMENTS = {
    "cornell university",
    "cornell universi",
    "accounts payable",
    "ap",
    "payee",
    "payer",
    "cornell",
    "university",
    "null",
    "none"
}

GENERIC_PAYER_BAD_VALUES = {
    "",
    "payer",
    "payee",
    "cornell university",
    "cornell universi",
    "null",
    "none",
    "unknown"
}

def clean_null_string(value):
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned == "":
            return None
        if cleaned.lower() in {"null", "none", "undefined", "n/a", "na"}:
            return None
        return cleaned
    return value

def normalize_text(value):
    if value is None:
        return ""
    value = str(value).lower().strip()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value

def normalize_payer_name(value):
    value = clean_null_string(value)
    if not value or not isinstance(value, str):
        return value

    cleaned = re.sub(r"\s+", " ", value).strip()

    # generic cleanup only
    cleaned = re.sub(r"\bllc\b", "LLC", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\binc\b", "Inc", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bcorp\b", "Corp", cleaned, flags=re.IGNORECASE)

    if cleaned.lower() in GENERIC_PAYER_BAD_VALUES:
        return None

    return cleaned

def extract_payer_from_record_text(record_text):
    text = str(record_text or "")

    # 1. strongest: explicit payer field
    m = re.search(r"Payer\s*\|\s*Value:\s*(.+)", text, re.IGNORECASE)
    if m:
        payer = m.group(1).strip()
        payer = re.sub(r"\s+\|\s*Value:.*$", "", payer).strip()
        if payer and payer.lower() not in GENERIC_PAYER_BAD_VALUES:
            return normalize_payer_name(payer)

    # 2. fallback: first description line
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("Description:"):
            candidate = line.split("Description:", 1)[-1].strip()

            # remove long trailing IDs
            candidate = re.sub(r"\s+\d{6,}$", "", candidate).strip()

            # skip obvious metadata / malformed description lines
            bad_starts = [
                "***",
                "invalid edi",
                "authorization",
                "security",
                "interchange",
                "functional",
                "transaction",
                "payment amount",
                "credit debit",
                "payment method",
                "payment format",
                "invoice amount",
                "invoice date",
                "payee",
            ]
            cand_norm = candidate.lower()
            if any(cand_norm.startswith(x) for x in bad_starts):
                continue

            if candidate and candidate.lower() not in GENERIC_PAYER_BAD_VALUES:
                return normalize_payer_name(candidate)

    return None

def evidence_strength(record_text, reasoning, likely_department, history_matches, history_consensus_count):
    if not likely_department:
        return None

    rt = (record_text or "").lower()
    rsn = (reasoning or "").lower()
    dept = likely_department.lower()

    if dept in rt or dept in rsn:
        return "strong"

    if "@cornell.edu" in rt:
        return "strong"

    if history_matches:
        top_score = history_matches[0].get("match_score", 0)
        if history_consensus_count >= 3 or top_score >= 45:
            return "strong"
        if history_consensus_count >= 2 or top_score >= 34:
            return "medium"

    if "cornell" in rt:
        return "medium"

    return "weak"

def should_use_history_department(ai_department, history_org, history_matches, history_consensus_count):
    if ai_department:
        return False

    if not history_org:
        return False

    if not history_matches:
        return False

    top_score = history_matches[0].get("match_score", 0)

    if history_consensus_count >= 3:
        return True

    if history_consensus_count >= 2 and top_score >= 34:
        return True

    if top_score >= 45:
        return True

    return False

def sanitize_department(value):
    value = clean_null_string(value)
    if not value or not isinstance(value, str):
        return None

    dept_clean = value.strip()
    dept_norm = dept_clean.lower()

    if dept_norm in BAD_DEPARTMENTS:
        return None

    if dept_norm.isdigit():
        return None

    return dept_clean

def normalize_history_matches(matches):
    if not isinstance(matches, list):
        return []

    normalized = []
    for m in matches:
        if not isinstance(m, dict):
            continue

        try:
            score = int(float(m.get("match_score", 0)))
        except Exception:
            score = 0

        normalized.append({
            "match_score": score,
            "match_reasons": m.get("match_reasons", []),
            "post_date": m.get("post_date"),
            "specific_org": m.get("specific_org"),
            "acct_and_name": m.get("acct_and_name"),
            "object_cd_and_name": m.get("object_cd_and_name"),
            "gl_transaction_description": m.get("gl_transaction_description"),
            "edoc_nbr": m.get("edoc_nbr"),
            "edoc_description": m.get("edoc_description"),
            "net_amount": m.get("net_amount"),
        })

    return normalized

for item in _items:
    data = item["json"]

    record_date = data.get("record_date")
    record_amount = data.get("record_amount")
    record_text = data.get("record_text")

    if not record_date and not record_amount and not record_text:
        continue

    raw = data.get("output", "")
    if raw is None:
        raw = ""

    raw = str(raw).replace("```json", "").replace("```", "").strip()

    try:
        parsed = json.loads(raw) if raw else {}
    except Exception:
        parsed = {
            "likely_payer": None,
            "likely_department": None,
            "confidence": None,
            "reasoning": None,
            "next_action": None,
            "parse_error": "Could not parse AI output as JSON",
            "raw_output": raw
        }

    likely_payer_ai = normalize_payer_name(parsed.get("likely_payer"))
    likely_department_ai = sanitize_department(parsed.get("likely_department"))
    confidence = parsed.get("confidence")
    reasoning = clean_null_string(parsed.get("reasoning"))
    next_action = clean_null_string(parsed.get("next_action"))

    try:
        confidence = float(confidence) if confidence is not None else None
    except Exception:
        confidence = None

    history_matches = normalize_history_matches(data.get("history_matches", []))
    history_consensus_org = sanitize_department(data.get("history_consensus_org"))
    history_consensus_count = data.get("history_consensus_count", 0)

    try:
        history_consensus_count = int(history_consensus_count)
    except Exception:
        history_consensus_count = 0

    # payer fallback from current record text
    likely_payer = likely_payer_ai
    used_record_text_for_payer = False

    if not likely_payer:
        fallback_payer = extract_payer_from_record_text(record_text)
        if fallback_payer:
            likely_payer = fallback_payer
            used_record_text_for_payer = True

            if confidence is None or confidence < 0.65:
                confidence = 0.65

            if reasoning:
                reasoning = reasoning + " The payer was recovered directly from the record text."
            else:
                reasoning = "The payer was recovered directly from the record text."

    likely_department = likely_department_ai
    used_history_for_department = False

    if should_use_history_department(
        likely_department_ai,
        history_consensus_org,
        history_matches,
        history_consensus_count
    ):
        likely_department = history_consensus_org
        used_history_for_department = True

        if confidence is None:
            confidence = 0.78
        else:
            confidence = max(confidence, 0.78)

        if reasoning:
            reasoning = reasoning + " Historical matching also supports this Cornell organization."
        else:
            reasoning = "Historical matching supports this Cornell organization."

    # no department = no confidence
    if not likely_department:
        confidence = None
    
    department_evidence_strength = evidence_strength(
        record_text,
        reasoning,
        likely_department,
        history_matches,
        history_consensus_count
    )

    normalized = {
        "row_id": f"{record_date}_{record_amount}_{hash(str(record_text)[:50]) % 100000}",
        "record_date": record_date,
        "record_amount": record_amount,
        "record_text": record_text,
        "likely_payer": likely_payer,
        "likely_department": likely_department,
        "confidence": confidence,
        "reasoning": reasoning,
        "next_action": next_action,
        "department_evidence_strength": department_evidence_strength,
        "used_record_text_for_payer": used_record_text_for_payer,
        "used_history_for_department": used_history_for_department,
        "history_match_count": len(history_matches),
        "top_history_matches": history_matches[:3],
        "history_consensus_org": history_consensus_org,
        "history_consensus_count": history_consensus_count,
    }

    if "parse_error" in parsed:
        normalized["parse_error"] = parsed["parse_error"]
        normalized["raw_output"] = parsed.get("raw_output")

    # flag for manual review
    needs_review = (
        not likely_department
        or department_evidence_strength in ["weak", None]
        or (confidence is not None and confidence < 0.6)
        or "parse_error" in parsed
    )
    normalized["needs_review"] = needs_review
    normalized["review_reason"] = (
        "parse_error" if "parse_error" in parsed
        else "no_department" if not likely_department
        else "weak_evidence" if department_evidence_strength in ["weak", None]
        else "low_confidence" if (confidence is not None and confidence < 0.6)
        else None
    )

    output.append({"json": normalized})

return output