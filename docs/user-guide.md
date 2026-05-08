# User Guide - EDI Payment Classifier

This guide is for Cornell Treasury staff who will use the tool to classify incoming payments.

## What This Tool Does

When you receive an EDI 820 Excel file from Kyriba, this tool automatically figures out which Cornell department each payment should go to. It gives you a Google Sheet with its best guesses, confidence levels, and flags the ones it's unsure about so you only need to manually review those.

## How to Use It

### Step 1: Export the EDI file from Kyriba
Export the EDI 820 report as an Excel (.xlsx) file, same as you normally would.

### Step 2: Upload the file
Open the n8n form page (your team lead will provide the URL). Click "Upload XLSX" and select the file. Click Submit.

### Step 3: Wait for processing
The system will process the file. This typically takes 1-3 minutes depending on how many payments are in the file. You don't need to keep the page open.

### Step 4: Review results in Google Sheets
Open the "EDI Payment Classifications" Google Sheet. Each row is one payment with the following columns:

| Column | What It Means |
|---|---|
| Date | Payment date |
| Amount | Payment amount |
| Payer | Who sent the money (company name) |
| Department | Which Cornell department should receive it |
| Confidence | How sure the system is (0.0 to 1.0) |
| Evidence Strength | strong, medium, or weak |
| Needs Review | TRUE if the system wants you to check this one |
| Review Reason | Why it was flagged (no_department, weak_evidence, low_confidence, parse_error) |
| Reasoning | The system's explanation for its classification |
| Next Action | Suggested next step |

### Step 5: Handle flagged records
Filter the sheet on **Needs Review = TRUE**. These are the payments the system couldn't confidently classify. For each one:
- Check the **Payer** and **Reasoning** columns for context
- Use your judgment and any additional information to assign the correct department
- Update the **Department** column manually

Unflagged records (Needs Review = FALSE) have been classified with reasonable confidence and can be processed normally, though spot-checking is always recommended.

## What the Confidence Scores Mean

- **0.9+** - Very confident, explicit evidence found
- **0.7-0.9** - Confident, strong historical match or clear payer identification
- **0.5-0.7** - Educated guess, some evidence but not conclusive
- **Below 0.5** - Low confidence, likely flagged for review
- **Blank** - No department was assigned, so confidence doesn't apply

## What the Evidence Strength Means

- **strong** - Department name appears in the payment text, or there are 3+ strong historical matches pointing to the same department
- **medium** - Moderate historical support, or Cornell-related text found
- **weak** - Minimal evidence, classification is a best guess

## Limitations

- **New vendors:** If a company has never sent a payment to Cornell before, there's no historical data to match against. These will almost always be flagged for review.
- **Multi-department vendors:** Some companies send payments to multiple Cornell departments. The system picks the most common historical match, which may not always be correct.
- **The system doesn't replace your judgment.** It accelerates the easy cases and flags the hard ones. Always verify before processing payments.

## When Something Goes Wrong

- **No results appear in the sheet:** The workflow may have errored. Contact your n8n admin to check the execution logs.
- **All records show "Needs Review":** The history cache may be empty. Check that the daily cache refresh ran successfully.
- **Wrong department assigned:** This can happen, especially for vendors that send to multiple departments. Correct it in the sheet and the correction will help future classifications.
- **"parse_error" in Review Reason:** The AI returned an unexpected format. The payment still needs manual classification.

## Getting Help

Contact repo owner or n8n admin for technical issues. For questions about how to classify specific payments, follow existing Treasury procedures.
