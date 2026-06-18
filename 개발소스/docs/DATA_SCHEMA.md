# Data Schema for Automation

## Purpose

Codex and analytics agents need stable field definitions to avoid wrong business decisions.

## product_packages

| Field | Type | Meaning |
|---|---|---|
| package_id | string | Internal package ID |
| package_name | string | Public package name |
| printer_model | string | Printer model included |
| scanner_model | string | Scanner model included |
| software_plan | string | Software feature bundle |
| label_sizes | string[] | Supported label sizes |
| barcode_types | string[] | Supported barcode types |
| cost_hardware | number | Hardware cost |
| cost_shipping | number | Shipping cost |
| cost_support_estimate | number | Expected support cost |
| sale_price | number | Current sale price |
| min_margin_rate | number | Minimum margin rate |
| active | boolean | Sales status |

## orders

| Field | Type | Meaning |
|---|---|---|
| order_id_hash | string | Hashed order ID |
| channel | string | Store channel |
| package_id | string | Sold package |
| order_date | datetime | Order date |
| quantity | number | Quantity |
| sale_amount | number | Revenue |
| fee_amount | number | Platform/payment fee |
| ad_attribution_id | string | Optional ad attribution |
| status | string | paid/shipped/canceled/returned |

## ad_daily_stats

| Field | Type | Meaning |
|---|---|---|
| date | date | Metric date |
| channel | string | Ad platform |
| campaign_id | string | Campaign |
| keyword | string | Search keyword or targeting group |
| impressions | number | Impressions |
| clicks | number | Clicks |
| spend | number | Ad spend |
| conversions | number | Orders attributed |
| revenue | number | Revenue attributed |

## support_tickets

| Field | Type | Meaning |
|---|---|---|
| ticket_id | string | Support ID |
| package_id | string | Related package |
| category | string | setup/printer/scanner/software/shipping/refund |
| severity | string | low/medium/high/blocker |
| summary | string | Safe summary without private data |
| created_at | datetime | Created time |
| resolved_at | datetime | Resolved time |

## app_error_logs

| Field | Type | Meaning |
|---|---|---|
| error_id | string | Error ID |
| app_version | string | Software version |
| package_id | string | Related package if known |
| device_type | string | printer/scanner/software |
| device_model | string | Safe model name |
| error_code | string | Safe error code |
| safe_message | string | Sanitized message |
| stack_hash | string | Hash of stack trace |
| occurred_at | datetime | Occurrence time |

## Derived metrics

```text
ROAS = attributed_revenue / ad_spend
CAC = ad_spend / orders
gross_profit = sale_amount - cost_hardware - cost_shipping - platform_fee
net_profit = gross_profit - ad_spend - support_cost_estimate
conversion_rate = orders / visits
return_rate = returned_orders / total_orders
setup_failure_rate = setup_failure_tickets / shipped_orders
```

## Privacy rule

Store only the minimum data required for business decisions. Use hashed IDs and sanitized summaries wherever possible.
