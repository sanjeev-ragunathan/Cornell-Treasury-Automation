# Future Plans

## 1. Migration to Claude Code Skills

The project is actively being migrated from n8n to a Claude Code Skill running on Cornell's AI Gateway. This addresses several limitations simultaneously: the system runs within Cornell's approved infrastructure (solving the data security concern), eliminates the n8n cloud dependency, and significantly reduces cost - processing 282 payments costs $0.84 total through the Claude Skill implementation. The n8n prototype served as the blueprint for this migration: every scoring weight, prompt rule, fallback mechanism, and reconciliation logic in the Claude Skill traces directly back to what was developed and validated in the n8n workflow.

## 2. Feedback Loop for Continuous Improvement

When Treasury staff manually correct a department classification in the output sheet, those corrections should automatically feed back into the Mapping History source data. This creates a virtuous cycle: every manual correction makes the scoring engine smarter for future payments from the same vendor. Implementation involves adding a scheduled workflow that reads corrected rows from the output sheet (where the department was changed from the original classification) and appends them to the history source. Over time, accuracy should improve as the history dataset grows with verified classifications.

## 3. Remove the Processing Limit

The current workflow limits processing to 10 payment records per run (down from ~35 in a typical file) to manage execution time and API costs during development. For production use, this limit should be removed entirely. With the daily history cache in place, the primary bottleneck is the sequential AI calls (~5 seconds per record), putting a full 35-record batch at approximately 3 minutes - well within acceptable range for a batch processing tool.

## 4. Direct Kyriba Integration

Instead of requiring Treasury staff to manually export an Excel file from Kyriba and upload it through a web form, the system should connect directly to Kyriba's export mechanism. This could be implemented as a file watcher on a shared network drive where Kyriba deposits exports, or through Kyriba's API if available. Eliminating the manual export-and-upload step makes the system viable for daily automated processing without human initiation.

## 5. Confidence Score Calibration

Collect a labeled test set of 200+ payments with known correct departments (sourced from Treasury staff corrections and verified historical data). Compare the AI's confidence scores against actual accuracy to build a calibration curve. Use this to set meaningful thresholds: if 0.8 confidence actually corresponds to 92% accuracy, that informs whether a record needs review. Currently, thresholds (0.6 for review flagging, 0.78 for history override) are based on engineering judgment rather than empirical calibration.

## 6. Outlook Email Search Integration

Treasury staff currently search a shared Outlook inbox manually when investigating unknown payments - looking for past correspondence with the vendor that might indicate which department expected the funds. Adding an Outlook search tool to the AI agent would automate this step. The agent could query the inbox for the payer name and present relevant email threads as additional classification evidence. This is particularly valuable for the unknown vendor case (Limitation #3) where historical GL data provides no signal.

## 7. KFS Direct Integration

Replace the Google Sheets dependency for historical data with a direct connection to Cornell's Kuali Financial System (KFS). KFS is the authoritative source for GL transactions, department codes, and account mappings. A direct integration would eliminate the manual step of maintaining and updating the Mapping History Google Sheet, ensure the scoring engine always works with current data, and allow access to richer transaction metadata that may not be present in the Google Sheet export.

## 8. Automated Confidence-Based Processing

For payments that consistently classify with high confidence (0.9+) and strong evidence, implement an auto-processing path that routes them directly to the correct department without human review. This would require the confidence calibration work from Plan #5 to be completed first - auto-processing is only safe when the confidence scores have been validated against actual accuracy. Start conservatively (only auto-process 0.95+ with strong evidence and a vendor that has been correctly classified at least 5 times historically) and expand the threshold as confidence in the system grows.

## 9. Multi-Department Vendor Handling

For vendors that historically send payments to multiple Cornell departments, the current system defaults to the most common department - which is wrong roughly 66% of the time for these vendors. A better approach would be to detect multi-department vendors during scoring (when the top 5 matches span 2+ departments with no clear consensus) and present the reviewer with a ranked list of candidate departments along with the historical frequency of each. This turns a "guess and check" review into a "pick from a shortlist" review.

## 10. Automated Regression Testing

Build a test suite of 50+ labeled payment records (covering known vendors, unknown vendors, multi-department vendors, and edge cases) that can be run automatically after any code change. Compare the system's output against the expected classifications and flag any regressions. This is essential for maintaining accuracy as the scoring weights, prompt instructions, and reconciliation logic evolve over time. The test suite should be versioned alongside the code and run as part of any deployment process.

## 11. Real-Time Processing

The current system is designed for batch processing - an entire EDI file is uploaded and processed at once. A future version could process payments in real-time as they arrive in Cornell's systems, classifying each payment within seconds of receipt. This would require the Kyriba integration (Plan #4) and KFS integration (Plan #7) to be in place, along with the confidence-based auto-processing (Plan #8) for high-confidence classifications. Low-confidence payments would still queue for human review, but the turnaround time for easy cases would drop from hours to seconds.