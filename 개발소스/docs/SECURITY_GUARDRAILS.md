# Security Guardrails

## Secrets

Never commit:

- API keys
- Ad platform tokens
- Store API credentials
- Database credentials
- Payment credentials
- `.env` files
- Private certificates
- Refresh tokens

## Customer data

Do not log or expose:

- Customer name
- Phone number
- Full address
- Payment data
- Raw order payload
- Access token
- Email address unless strictly required and masked

## Safe logging pattern

Allowed:

```text
order_id_hash=abc123 package_id=starter-printer scanner_model=MODEL_SAFE error_code=PRINTER_OFFLINE
```

Forbidden:

```text
name=... phone=... address=... token=... raw_order_json=...
```

## External integrations

Before changing integration code, check:

- Token storage
- Token refresh handling
- Retry limit
- Rate limit
- Error handling
- Audit logging
- Webhook signature validation if webhooks are used

## AI automation permissions

Codex may:

- Read repository files
- Edit code in a branch
- Add tests
- Draft docs
- Draft PR summaries

Codex must not autonomously:

- Deploy production
- Rotate secrets
- Export customer data
- Increase ad spend
- Change pricing
- Change refund policy
- Change warranty policy
