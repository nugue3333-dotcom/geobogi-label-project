---
name: daily-ops-analysis
description: Use when analyzing daily sales, ad spend, orders, product-package performance, support tickets, return rate, setup failures, or software error logs.
---

# Daily Operations Analysis Skill

## Goal

Find profitable actions and operational risks from sales, ad, support, and error data.

## Rules

- Optimize for net profit, not revenue.
- Do not recommend ad budget increases when stock is low, support load is high, return rate is high, or setup failures are increasing.
- Do not recommend unsupported product claims.
- Separate software fixes from marketing fixes.
- Flag data quality problems clearly.

## Metrics

Calculate when data exists:

```text
ROAS = revenue / ad_spend
CAC = ad_spend / orders
net_profit = revenue - hardware_cost - shipping_cost - platform_fee - ad_spend - support_cost
conversion_rate = orders / visits
return_rate = returned_orders / total_orders
setup_failure_rate = setup_failure_tickets / shipped_orders
```

## Output

```md
## Daily operations result

### What worked

### What lost money

### Risks

### Proposed software tasks

### Proposed marketing tasks

### Actions requiring approval

### Missing data
```
