# NOTE: This code runs inside n8n's Python Code node where top-level
# return statements are valid. Pylance warnings about "return outside
# function" can be safely ignored.

import re

output = []

MAX_MATCHES = 5
MIN_SCORE = 22
MAX_CANDIDATES_PER_RECORD = 80
MIN_HISTORY_CONFIDENCE_FOR_CONSENSUS = 2

GENERIC_GL_PATTERNS = [
    "incoming ach",
    "incoming wire",
    "incoming wires",
    "deposits to depts",
    "deposits to departments",
    "ur to depts",
    "ur batch",
    "cash receipt",
    "lockbox",
]

GENERIC_COMPANY_WORDS = {
    "llc", "inc", "corp", "corporation", "company", "co", "ltd", "limited",
    "group", "services", "service", "systems", "system", "solutions",
    "solution", "holdings", "holding", "international", "global", "north",
    "america", "usa", "us", "ap", "the"
}

STOP_WORDS = {
    "date", "amount", "description", "value", "payment", "payments",
    "invoice", "number", "current", "transaction", "trace", "originating",
    "company", "identifier", "code", "payee", "payer", "wire", "ach",
    "incoming", "deposits", "dept", "depts", "reference", "effective",
    "control", "header", "trailer", "group", "interchange", "bank",
    "university", "cornell", "advice", "order", "remittance", "open",
    "item", "seller", "buyer", "date", "paid", "credit", "debit"
}

def to_float(value):
    try:
        if value in [None, "", "undefined"]:
            return None
        return float(str(value).replace(",", "").strip())
    except Exception:
        return None

def normalize_text(value):
    if value is None:
        return ""
    value = str(value).lower().strip()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value

def normalize_id(value):
    if value is None:
        return ""
    value = str(value).strip().lower()
    value = re.sub(r"[^a-z0-9]", "", value)
    return value

def normalize_company_text(value):
    text = normalize_text(value)
    words = [w for w in text.split() if w not in GENERIC_COMPANY_WORDS]
    return " ".join(words)

def get_keywords(text):
    words = normalize_text(text).split()
    return set(
        w for w in words
        if len(w) >= 4 and not w.isdigit() and w not in STOP_WORDS
    )

def get_company_tokens(value):
    words = normalize_company_text(value).split()
    return set(w for w in words if len(w) >= 4 and not w.isdigit())

def word_overlap_score(text1, text2):
    words1 = get_keywords(text1)
    words2 = get_keywords(text2)
    if not words1 or not words2:
        return 0
    return len(words1.intersection(words2))

def company_similarity(a, b):
    a_tokens = get_company_tokens(a)
    b_tokens = get_company_tokens(b)

    if not a_tokens or not b_tokens:
        return 0.0

    overlap = len(a_tokens.intersection(b_tokens))
    if overlap == 0:
        return 0.0

    return (2.0 * overlap) / (len(a_tokens) + len(b_tokens))

def is_generic_history_row(hist):
    text = " ".join([
        str(hist.get("gl_transaction_description", "") or ""),
        str(hist.get("edoc_description", "") or "")
    ])
    text = normalize_text(text)
    return any(pat in text for pat in GENERIC_GL_PATTERNS)

def extract_payer_hint(record_text):
    """
    Extract likely payer from current EDI text.
    Preference:
    1. explicit 'Payer | Value: ...'
    2. first Description line
    """
    text = str(record_text or "")

    payer_match = re.search(r"Payer\s*\|\s*Value:\s*(.+)", text, re.IGNORECASE)
    if payer_match:
        payer = payer_match.group(1).strip()
        payer = re.sub(r"\s+\|\s*Value:.*$", "", payer).strip()
        if payer:
            return payer

    for line in text.splitlines():
        if line.strip().startswith("Description:"):
            candidate = line.split("Description:", 1)[-1].strip()
            candidate = re.sub(r"\s+\d{6,}$", "", candidate).strip()
            if candidate and len(candidate) >= 4:
                return candidate

    return ""

def extract_candidate_reference_ids(record_text):
    text = str(record_text or "")
    ids = set()

    patterns = [
        r"Seller's Invoice Number\s*\|\s*Value:\s*([A-Za-z0-9\-]+)",
        r"Invoice Date\s*\|\s*Value:\s*([A-Za-z0-9\-]+)",
        r"Transaction Reference Number\s*\|\s*Value:\s*([A-Za-z0-9\-]+)",
        r"Current Transaction Trace Numbers\s*\|\s*Value:\s*([A-Za-z0-9\-]+)",
        r"Payment Number[:\s]+([A-Za-z0-9\-]+)",
        r"INVOICE\s+([A-Za-z0-9\-]+)",
    ]

    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            val = normalize_id(m.group(1))
            if len(val) >= 4:
                ids.add(val)

    return ids

def history_text_blob(hist):
    return " ".join([
        str(hist.get("gl_transaction_description", "") or ""),
        str(hist.get("edoc_description", "") or ""),
        str(hist.get("specific_org", "") or ""),
        str(hist.get("acct_and_name", "") or ""),
        str(hist.get("object_cd_and_name", "") or ""),
    ])

def payer_match_score(record, hist):
    payer_hint = extract_payer_hint(record.get("record_text", ""))
    if not payer_hint:
        return 0, []

    hist_blob = history_text_blob(hist)
    hist_desc = str(hist.get("gl_transaction_description", "") or "")
    hist_edoc_desc = str(hist.get("edoc_description", "") or "")

    score = 0
    reasons = []

    sim_blob = company_similarity(payer_hint, hist_blob)
    sim_desc = company_similarity(payer_hint, hist_desc)
    sim_edoc = company_similarity(payer_hint, hist_edoc_desc)
    best_sim = max(sim_blob, sim_desc, sim_edoc)

    payer_norm = normalize_company_text(payer_hint)
    hist_blob_norm = normalize_company_text(hist_blob)

    if payer_norm and hist_blob_norm:
        if payer_norm in hist_blob_norm or hist_blob_norm in payer_norm:
            score += 30
            reasons.append("payer_substring_match")
            return score, reasons

    if best_sim >= 0.95:
        score += 30
        reasons.append("payer_text_match")
    elif best_sim >= 0.75:
        score += 22
        reasons.append("payer_strong_similarity")
    elif best_sim >= 0.50:
        score += 12
        reasons.append("payer_partial_similarity")

    return score, reasons

def reference_id_match_score(record, hist):
    record_ids = extract_candidate_reference_ids(record.get("record_text", ""))
    hist_values = [
        hist.get("edoc_nbr"),
        hist.get("edoc_description"),
        hist.get("gl_transaction_description"),
    ]
    hist_ids = set()
    for v in hist_values:
        norm = normalize_id(v)
        if norm and len(norm) >= 4:
            hist_ids.add(norm)

    # extract leading numeric ID from GL description (e.g. "104141 HOWARD HUGHES ME")
    gl_desc = str(hist.get("gl_transaction_description", "") or "")
    leading_id_match = re.match(r"^(\d{4,})\s", gl_desc.strip())
    if leading_id_match:
        hist_ids.add(normalize_id(leading_id_match.group(1)))

    for rid in record_ids:
        for hid in hist_ids:
            if rid == hid:
                return 24, ["reference_id_exact_match"]
            if rid in hid or hid in rid:
                return 14, ["reference_id_partial_match"]
    return 0, []

def cheap_candidate_score(record, hist):
    score = 0

    record_amount = to_float(record.get("record_amount"))
    hist_amount = to_float(hist.get("net_amount"))

    if record_amount is not None and hist_amount is not None:
        diff = abs(record_amount - hist_amount)
        if diff < 0.01:
            score += 20
        elif diff <= 5:
            score += 12
        elif diff <= 25:
            score += 8
        elif diff <= 100:
            score += 3
        else:
            return -1

    payer_score, _ = payer_match_score(record, hist)
    score += payer_score

    record_text = record.get("record_text", "")
    hist_text = history_text_blob(hist)
    overlap = word_overlap_score(record_text, hist_text)
    score += overlap * 3

    ref_score, _ = reference_id_match_score(record, hist)
    score += ref_score

    if is_generic_history_row(hist):
        score -= 6

    return score

def full_score_history_match(record, hist):
    score = 0
    reasons = []

    record_amount = to_float(record.get("record_amount"))
    hist_amount = to_float(hist.get("net_amount"))
    record_text = record.get("record_text", "")

    hist_desc = hist.get("gl_transaction_description", "") or ""
    hist_org = hist.get("specific_org", "") or ""
    hist_acct = hist.get("acct_and_name", "") or ""
    hist_obj = hist.get("object_cd_and_name", "") or ""
    hist_edoc_desc = hist.get("edoc_description", "") or ""

    # 1. Amount similarity
    if record_amount is not None and hist_amount is not None:
        diff = abs(record_amount - hist_amount)
        if diff < 0.01:
            score += 25
            reasons.append("exact_amount")
        elif diff <= 5:
            score += 14
            reasons.append("near_amount")
        elif diff <= 25:
            score += 8
            reasons.append("loose_amount")
        elif diff <= 100:
            score += 3
            reasons.append("wide_amount")

    # 2. Dynamic payer similarity
    payer_score, payer_reasons = payer_match_score(record, hist)
    score += payer_score
    reasons.extend(payer_reasons)

    # 3. Reference / invoice / trace overlap
    ref_score, ref_reasons = reference_id_match_score(record, hist)
    score += ref_score
    reasons.extend(ref_reasons)

    # 4. Keyword overlap with GL description
    overlap = word_overlap_score(record_text, hist_desc)
    if overlap >= 3:
        score += 16
        reasons.append("strong_keyword_overlap")
    elif overlap == 2:
        score += 10
        reasons.append("medium_keyword_overlap")
    elif overlap == 1:
        score += 3
        reasons.append("light_keyword_overlap")

    # 5. Weak overlap with edoc description
    edoc_overlap = word_overlap_score(record_text, hist_edoc_desc)
    if edoc_overlap >= 2:
        score += 4
        reasons.append("edoc_desc_overlap")

    # 6. Org/acct/object text appearing directly in record
    record_norm = normalize_text(record_text)

    for label, value, pts in [
        ("org_text_match", hist_org, 6),
        ("acct_text_match", hist_acct, 4),
        ("object_text_match", hist_obj, 2),
    ]:
        value_norm = normalize_text(value)
        if value_norm and len(value_norm) >= 5 and value_norm in record_norm:
            score += pts
            reasons.append(label)

    # 7. Penalize generic history rows
    if is_generic_history_row(hist):
        score -= 8
        reasons.append("generic_history_penalty")

    # 8. Reject amount-only matches
    non_amount_reasons = [
        r for r in reasons
        if r not in {
            "exact_amount", "near_amount", "loose_amount", "wide_amount",
            "generic_history_penalty"
        }
    ]

    if not non_amount_reasons:
        return 0, []

    # 9. Require stronger threshold when history row is generic
    if is_generic_history_row(hist) and score < 34:
        return 0, []

    return score, reasons

def dedupe_matches(matches):
    seen = set()
    deduped = []

    for m in matches:
        key = (
            m.get("specific_org"),
            m.get("acct_and_name"),
            m.get("object_cd_and_name"),
            m.get("gl_transaction_description"),
            m.get("net_amount"),
        )
        if key not in seen:
            seen.add(key)
            deduped.append(m)

    return deduped

def summarize_history(matches):
    if not matches:
        return {
            "history_consensus_org": None,
            "history_consensus_count": 0
        }

    counts = {}
    for m in matches:
        org = m.get("specific_org")
        score = m.get("match_score", 0)

        if not org:
            continue

        # weight stronger matches more heavily
        weight = 1
        if score >= 45:
            weight = 3
        elif score >= 34:
            weight = 2

        counts[org] = counts.get(org, 0) + weight

    if not counts:
        return {
            "history_consensus_org": None,
            "history_consensus_count": 0
        }

    best_org = max(counts, key=counts.get)
    return {
        "history_consensus_org": best_org,
        "history_consensus_count": counts[best_org]
    }

current_records = []
history_rows = []

for item in _items:
    data = item.get("json", {})

    if "record_text" in data and "record_amount" in data:
        current_records.append(data)
    elif "gl_transaction_description" in data and "specific_org" in data:
        history_rows.append(data)

for record in current_records:
    record_date = record.get("record_date")
    record_amount = record.get("record_amount")
    record_text = record.get("record_text")

    if not record_date and not record_amount and not record_text:
        continue

    candidate_rows = []

    for hist in history_rows:
        pre_score = cheap_candidate_score(record, hist)
        if pre_score >= 0:
            candidate_rows.append((pre_score, hist))

    candidate_rows.sort(key=lambda x: x[0], reverse=True)
    candidate_rows = candidate_rows[:MAX_CANDIDATES_PER_RECORD]

    matches = []

    for _, hist in candidate_rows:
        score, reasons = full_score_history_match(record, hist)

        if score >= MIN_SCORE:
            matches.append({
                "match_score": score,
                "match_reasons": reasons,
                "post_date": hist.get("post_date"),
                "specific_org": hist.get("specific_org"),
                "acct_and_name": hist.get("acct_and_name"),
                "object_cd_and_name": hist.get("object_cd_and_name"),
                "gl_transaction_description": hist.get("gl_transaction_description"),
                "edoc_nbr": hist.get("edoc_nbr"),
                "edoc_description": hist.get("edoc_description"),
                "net_amount": hist.get("net_amount"),
            })

    matches = sorted(matches, key=lambda x: x["match_score"], reverse=True)
    matches = dedupe_matches(matches)
    matches = matches[:MAX_MATCHES]

    history_summary = summarize_history(matches)

    output.append({
        "json": {
            "record_date": record_date,
            "record_amount": record_amount,
            "record_text": record_text,
            "history_matches": matches,
            "history_consensus_org": history_summary["history_consensus_org"],
            "history_consensus_count": history_summary["history_consensus_count"],
        }
    })

return output
