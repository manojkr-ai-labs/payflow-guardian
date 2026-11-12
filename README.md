# PayFlow Guardian

PayFlow Guardian is a Sandbox workspace for a merchant owner and a support teammate. The owner creates a catalog test order, lets the buyer approve it in PayPal Sandbox, then reviews the saved payment, the assistant’s explanation, and any refund before money is sent.

The merchant screens follow the PayFlow Guardian design system. Sample rows in the design files are fixtures. The running demo uses PayPal Sandbox data.

## Safety rules

- PayPal confirms a payment. A status becomes confirmed only from a recognized PayPal response.
- The owner is the only refund send path. Preparing a refund does not call PayPal. Support can read a draft and cannot approve it.
- Unclear PayPal results stay `needs_checking` and unconfirmed. A timeout or an unrecognized status does not count as confirmed.

The assistant can look up a payment, explain the stored fact sheet, and prepare a refund. It cannot approve or send one. The badge on screen comes from the stored payment, not from the assistant’s text.

## Sandbox only

This project talks to PayPal Sandbox. It does not take live payments.

Not included:

- Live PayPal charges or a production PayPal app
- A refund path that skips owner approval
- Card data storage
- An accounting or banking ledger
- Fraud-prevention claims
- An assistant tool that runs SQL, a shell, or arbitrary HTTP

`POST /api/webhooks/paypal` is present. Signature verification does not call PayPal and does not accept a delivery, including when `PAYPAL_WEBHOOK_ID` is empty. An unverified body does not change a payment.

Refreshing a payment compares the saved capture id, amount, currency, and status with the latest PayPal read. A mismatch sets `needs_checking`, leaves the stored amount unchanged, and shows: "The saved payment and the latest PayPal data differ and need a check."

## Setup

Requirements: Docker Compose.

The API container runs migrations, then starts. On startup it seeds PayFlow Demo Shop when that merchant is missing.

```bash
docker compose up --build
```

Open http://localhost:3000. The API is on port 8000. Compose starts Postgres and sets `DATABASE_URL` and `WEB_ORIGIN` for the API service. The web container does not receive PayPal or session secrets.

Copy `.env.example` only as a name list. For a real Sandbox story, set these beside `docker-compose.yml`:

- `SESSION_SECRET`
- `PAYPAL_CLIENT_ID`
- `PAYPAL_CLIENT_SECRET`
- `PAYPAL_API_BASE` as `https://api-m.sandbox.paypal.com`

`PAYPAL_WEBHOOK_ID`, `AI_BASE_URL`, `AI_API_KEY`, and `AI_MODEL` may stay empty. Empty AI settings keep the built-in assistant answer and do not call a model network.

If those PayPal variables are missing, Compose uses the placeholders in `docker-compose.yml`. The app boots. A Sandbox approve, capture, or refund does not complete until the placeholders are replaced with Sandbox credentials. An empty `PAYPAL_CLIENT_SECRET=` in a `.env` file overrides the placeholder, so omit a line instead of leaving it blank.

Seeded sign-in, merchant PayFlow Demo Shop:

| Role    | Email                |
| ------- | -------------------- |
| Owner   | owner@payflow.test   |
| Support | support@payflow.test |

Passwords are the demo values in `apps/api/app/modules/auth/seed.py`.

Catalog amounts are fixed. `DEMO-25` is 25.00 USD. `DEMO-49` is 49.00 USD. The browser cannot choose another amount.

## Demo

Use Sandbox credentials for steps 2 through 8. Label any other row a test example.

1. Sign in as the owner.
2. Open Payments, choose Create test order, and create `DEMO-25`.
3. Approve that order as the Sandbox buyer. The return page captures it once. If you land on the payment first, use Capture payment.
4. The payment shows the PayPal capture id. The chip is Completed only when the status is completed and PayPal confirmed it.
5. Open Ask the assistant on that payment. Ask it to investigate. The fact sheet and chip stay on the server value.
6. On a completed, confirmed payment, enter a reason and choose Prepare refund. PayPal is not called yet.
7. On the refund draft, check the capture reference, original amount, refund amount, currency, and reason. The owner chooses Approve and send.
8. The draft shows the PayPal refund result. A failed or unclear result stays on that same draft and does not add a PayPal refund id.
9. Dashboard, Latest from PayPal, and the payment Activity list show the capture, the investigation, the approval, and the result.
10. Prepare a second refund and do not approve it. It stays Not sent, with no PayPal refund id. Sign out, sign in as support, and open that draft. The payload is visible, the page says "Support cannot send this refund.", and Approve and send is absent.

Reject is available to the owner only while a draft is still waiting. Reject does not call PayPal.

## Checks already in the API tests

There is no separate safety-sweep file. These tests cover the same rules:

- `test_demo_25_persists_catalog_amount_when_client_sends_another_amount`
- `test_successful_capture_stores_capture_id_and_confirmed`
- `test_unconfirmed_fact_sheet_stays_unconfirmed`
- `test_prepare_does_not_call_refund`
- `test_hash_mismatch_does_not_call_paypal`
- `test_other_merchant_payment_returns_not_found`
- `test_second_capture_does_not_call_paypal_again`
- `test_owner_approve_calls_refund_once`
- `test_capture_timeout_stores_needs_checking_after_one_attempt`
- `test_unclear_capture_stores_needs_checking_after_one_attempt`
- `test_log_filter_removes_bearer_token_and_client_secret`

Licensed under the MIT License. See `LICENSE`.

Demo video: add the public YouTube URL.
