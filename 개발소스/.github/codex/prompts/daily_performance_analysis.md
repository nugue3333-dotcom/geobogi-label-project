# Daily Performance Analysis Prompt

Analyze daily sales, ad, support, and error data. Do not execute changes.

Input may include CSV, JSON, database export, or summarized metrics.

Calculate where possible:

- Revenue
- Gross profit
- Net profit after ad spend
- ROAS
- CAC
- Conversion rate
- Return/refund rate
- Support ticket rate
- Setup failure rate
- Printer/scanner error rate

Decision rules:

- Prefer net profit over revenue.
- Do not recommend ad budget increase if return rate, setup failure, or support rate is abnormal.
- Do not recommend selling out-of-stock packages.
- Do not recommend claims not supported in `docs/PRODUCT_PACKAGES.md`.

Output:

```md
## Daily summary

## Profitable packages

## Loss-making packages

## Ad actions proposed

## Product page actions proposed

## Software issues requiring Codex task

## Human approvals required

## Data quality problems
```
