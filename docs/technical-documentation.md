# Architecture and Technical Documentation

## System Overview

The EDI Payment Classifier is an n8n workflow that automates the classification of unidentified incoming payments at Cornell University Treasury. It combines a deterministic multi-signal scoring engine with LLM-based classification to route EDI 820 payments to the correct Cornell department.

## Data Flow

```
EDI 820 Excel → Parse → Limit → Merge ← History Cache (pre-cleaned)
                                   ↓
                          Score History Matches
                                   ↓
                         Format Agent Prompt
                                   ↓
                        AI Agent (GPT-4o) ──→ Merge2
                                               ↓
                                    Reconcile AI + History
                                               ↓
                                         Google Sheet
```

A parallel daily workflow refreshes the history cache:

```
Schedule Trigger (6 AM) → Read History Sheet (101k rows)
                            → Clean & Dedupe (→ 8,700 rows)
                              → Write to Cache Sheet
```

## Components

### 1. Parse EDI to Payment Records

**Input:** 1,539 flat Excel rows from the EDI 820 file
**Output:** ~35 structured payment blocks

The EDI file is a flat table where each payment spans multiple rows. A new payment block starts whenever the `Date` column is non-empty. This node groups consecutive rows into payment blocks, then flattens each block into a single `record_text` string for downstream processing.

Excel serial date numbers are converted to `YYYY-MM-DD` strings using a manual algorithm (no `datetime` import - n8n's Python sandbox restricts it in some versions).

### 2. Clean and Dedupe History

**Input:** 101,170 raw GL transaction records from Google Sheets
**Output:** ~8,702 cleaned, deduplicated records

Processing steps:
- Parse dates in multiple formats (`M/D/YYYY`, `YYYY-MM-DD`, `M-D-YYYY`)
- Calculate `net_amount` as `credit - debit`
- Strip email addresses from `edoc_nbr` fields
- Remove numeric-only `specific_org` values
- Build a pattern key from `(gl_description, org, acct, object)` for deduplication
- Keep up to 3 recent records (within 365 days) per pattern key
- Keep 1 older record per pattern key if not already represented in recent records
- Sort by date descending
- Assign sequential `row_id` for cache storage

### 3. Score History Matches

**Input:** 10 EDI payment records + 8,702 history rows (merged via append)
**Output:** 10 records, each enriched with top 5 history matches and consensus department

This is the core ranking engine. It uses a two-pass scoring approach:

**Pass 1 - Cheap pre-filter (`cheap_candidate_score`):**
Runs a lightweight score on all 8,702 history rows per payment record. Eliminates candidates with amount differences > $100 (returns -1). Keeps top 80 candidates for full scoring.

**Pass 2 - Full scoring (`full_score_history_match`):**
Scores each candidate on 5 signals:

| Signal | Max Points | Method |
|---|---|---|
| Payer name | +30 | Company name normalization, substring matching, token similarity (Dice coefficient) |
| Amount | +25 | Tiered: exact (<$0.01) = 25, near (<$5) = 14, loose (<$25) = 8, wide (<$100) = 3 |
| Reference ID | +24 | Extract invoice/trace numbers from EDI, match against edoc_nbr, edoc_description, and leading numeric IDs in GL description |
| Keyword overlap | +16 | Meaningful word intersection (4+ chars, stop words removed) between EDI text and GL description |
| Generic penalty | -8 | Penalizes history rows with generic descriptions ("incoming ACH", "deposits to depts") |

**Safeguards:**
- Amount-only matches are rejected (must have at least one non-amount signal)
- Generic history rows require a minimum score of 34
- Minimum qualifying score: 22

**Consensus computation:**
Top 5 matches are deduplicated and a weighted consensus is computed. Matches scoring 45+ get weight 3, 34+ get weight 2, others get weight 1. The department with the highest weighted count becomes the consensus org.

### 4. Format Agent Prompt

**Input:** 10 scored records with history matches
**Output:** 10 records with a `formatted_prompt` field containing clean, readable context

Transforms the raw match data into a structured prompt:
```
CURRENT PAYMENT
Date: 2025-10-24
Amount: $2992.0
Payment Details:
[flattened EDI text]

HISTORICAL MATCHES
Match 1 (score: 47, reasons: payer_substring_match, exact_amount):
  Org: NIFA
  GL Description: WIRE SAIC GEMINI
  Amount: $2992.0

History consensus: NIFA (5 weighted matches support this)
```

### 5. AI Agent (GPT-4o)

**Model:** openai.gpt-4o
**Mode:** 1 call per payment record

**System prompt** instructs the model to:
- Identify the payer (company name, not "Cornell University")
- Only assign a department with explicit evidence
- Not treat payee or payer team names as Cornell departments
- Return structured JSON with `likely_payer`, `likely_department`, `confidence`, `reasoning`, `next_action`

The AI acts as a second opinion - the scoring engine handles most classification, and the AI confirms, overrides, or handles edge cases the deterministic system can't.

### 6. Reconcile AI + History

**Input:** 10 records combining Format Agent Prompt output and AI Agent output
**Output:** 10 final classified records

Reconciliation logic:
1. Parse AI JSON output (handles markdown fences, malformed JSON)
2. Normalize payer name (strip generic suffixes, filter bad values)
3. Sanitize department (filter "Cornell University", "Accounts Payable", numeric-only values)
4. **Payer fallback:** If AI returned no payer, extract from raw EDI text (explicit `Payer | Value:` field, then first Description line)
5. **History department override:** If AI returned no department but history consensus is strong (≥3 weighted matches, or ≥2 with top score ≥34, or top score ≥45), use history consensus
6. **Confidence null-out:** If no department was assigned, confidence is set to null
7. **Evidence strength scoring:** strong (department in text, or high history consensus), medium (moderate history, or "cornell" in text), weak (everything else)
8. **Review flagging:** `needs_review = true` if no department, weak evidence, low confidence (<0.6), or parse error

## External Services

| Service | Purpose | Auth |
|---|---|---|
| Google Sheets | History source, cache, and output | OAuth2 |
| OpenAI API | GPT-4o for AI classification | API key (managed by n8n org) |

## Design Decisions

**Why deterministic scoring before LLM?** The scoring engine catches most cases without AI, reducing cost and improving reliability. The LLM adds value on ambiguous cases but would hallucinate departments without the structured history context.

**Why a daily history cache?** The source history sheet has 101k+ rows. Clean & Dedupe takes significant processing time. Since history updates daily, caching the cleaned result avoids reprocessing on every form submission.

**Why not batch AI calls?** The n8n AI Agent node processes one item at a time by design. The org controls API access through n8n, so direct HTTP requests to OpenAI aren't available.

**Why manual date conversion?** n8n's Python sandbox intermittently blocks `from datetime import datetime`. The manual Excel-serial-to-date algorithm avoids this dependency.
