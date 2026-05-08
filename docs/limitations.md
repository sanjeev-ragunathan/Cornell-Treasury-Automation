# Limitations

## 1. No Direct System Integration

The system operates on manually exported Excel files from Kyriba. There is no live connection to any of Cornell's internal systems L- not KFS (Kuali Financial System), not the shared Outlook inbox that Treasury staff use for vendor correspondence, and not Cornell's secure file storage. Every run begins with a human exporting a file and uploading it through a web form. This adds a manual step and means the system cannot process payments in real-time as they arrive.

## 2. Accuracy Ceiling on Multi-Department Vendors

Some companies send payments to multiple Cornell departments. For example, a large research sponsor might fund projects in both CALS and the Vet College. The scoring engine picks the department with the strongest historical match, which defaults to the most common one. For vendors that split across departments, exact accuracy is approximately 34%. The system flags these for review, but a reviewer still has to determine the correct department manually.

## 3. Unknown Vendors Have No Historical Signal

When a company sends a payment to Cornell for the first time, there are zero historical records to match against. The scoring engine produces no matches, and the AI agent has no context beyond the raw EDI text — which often contains just a truncated company name and a dollar amount. Classification accuracy for unknown vendors is approximately 28%. These payments are correctly flagged for review, but the system cannot meaningfully help with them.

## 4. Sequential AI Calls Cannot Be Batched

The n8n AI Agent node processes one payment record at a time. With 35 payments in a typical file, this means 35 sequential OpenAI API calls, taking 2–3 minutes total. The org manages API access through n8n's credential system, so direct HTTP requests to the OpenAI API (which would allow batching multiple records per call) are not available. This is the primary bottleneck for processing speed.

## 5. Confidence Scores Are Not Calibrated

The confidence values (0.0–1.0) returned by the AI agent are the model's self-reported certainty, not calibrated against actual accuracy. A confidence of 0.8 does not mean the classification is correct 80% of the time — it means the model believes it is that confident, which is a different thing. Without a labeled test set to validate against, there is no way to know how well confidence correlates with actual accuracy.

## 6. History Data Quality Affects Everything

The scoring engine is only as good as the historical GL records it matches against. If the source Google Sheet contains errors — wrong department assignments, missing GL descriptions, duplicate entries with conflicting information — those errors propagate into the scoring and consensus computation. The Clean and Dedupe node mitigates some of this (removing numeric-only org values, stripping email addresses from edoc numbers), but it cannot fix fundamentally incorrect historical data.

## 7. EDI Data Quality Varies Significantly

Some EDI 820 records contain rich structured data — full ISA/GS/ST headers, explicit payer fields, invoice numbers, trace numbers, and RMR line items. Others contain almost nothing: just a truncated company name and a dollar amount on a single line. The system handles both, but classification accuracy drops sharply on minimal records because there are fewer signals for the scoring engine to work with.

## 8. No Formal Evaluation Framework

The system was validated through manual review of sample outputs and iterative refinement based on observed failure modes. There is no train/test split, no labeled ground truth dataset, and no automated regression testing. Accuracy numbers cited (34% for multi-department vendors, 28% for unknown vendors) are based on manual spot-checks, not systematic evaluation. A production deployment would need a proper evaluation framework.

## 9. Not Hosted on Cornell Infrastructure

The current deployment uses n8n cloud (external) and Google Sheets for data storage. Payment data — including payer names, amounts, and department assignments — flows through external services. This does not meet Cornell's data handling requirements for production financial systems. The system is a proof-of-concept that demonstrates the approach works, not a production-ready deployment.

## 10. Duplicate Handling on Re-runs

Running the workflow multiple times with the same EDI file appends new rows to the output Google Sheet rather than updating existing ones. The row_id field (based on date + amount + text hash) prevents exact duplicates, but re-running the same file after code changes or with different AI responses generates different row_ids, resulting in duplicate entries that require manual cleanup.