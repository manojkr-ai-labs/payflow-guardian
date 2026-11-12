# Phase prompts

Phases 1–3 are already built. Start at **4A**. Paste **one** prompt into a **new** chat. Wait until its exit command is green, then start the next chat.

Phase 10 is optional. Skip 10A and 10B if the demo path already works and go to 11.

## How to run a prompt

- One prompt per chat. Do not paste the next prompt into the same chat.
- If the agent opens `node_modules`, `.next`, `.venv`, or a Stitch HTML file, stop that chat and rerun the same prompt.
- If the exit command fails twice, stop. Do not let the agent keep trying.
- Do not run two prompts in parallel.

## Shared rules (already inside every prompt)

- Extend the current code. Do not rewrite working modules.
- Read only the files named in that prompt.
- Do not add dependencies, restyle the app, call PayPal Sandbox, or run Docker.
- Do not start the next slice.
- Tests use the in-memory SQLite fixture. Leave that fixture alone.

---

## 4A. Capture API

```
PayFlow Guardian, slice 4A only. Phases 1–3 already work. Add payment capture on the API. Do not build pages.

Read only:
- apps/api/app/modules/payments/service.py
- apps/api/app/modules/payments/models.py
- apps/api/app/api/payments.py
- apps/api/app/core/errors.py
- apps/api/app/modules/paypal/types.py
- apps/api/app/modules/paypal/fake.py
- apps/api/app/modules/activity/service.py
- apps/api/tests/test_create_payment.py (copy its login and fake-adapter fixture style only)

Do not open any other file. Do not edit the PayPal client, fake adapter, create_test_payment, catalog, or auth.

Add not_found(message) in errors.py as AppError("not_found", message, 404).

Add capture_payment(...) in payments/service.py:
- Load the payment with merchant_id from the session. Missing or other-merchant id raises not_found. Do not reveal that the row exists.
- If paypal_capture_id is stored and confirmation is confirmed, return that row and do not call capture_order.
- Otherwise call paypal.capture_order(paypal_order_id) once.
- Recognized success: store capture id, paypal_status, status completed, confirmation confirmed. Record payment.captured with activity.record in the same transaction.
- Timeout, exception, or unclear body: store needs_checking and unconfirmed, record payment.needs_checking, do not call PayPal again.
- Explicit PayPal failure: store failed and return paypal_failed.
- Ignore amount and currency from the client.

Add POST /api/payments/{id}/capture in api/payments.py. Reuse get_current_membership, get_db, and get_paypal. Return payment_payload. Add paypal_capture_id and confirmation to that payload if they are missing. Do not change the create-payment response shape for existing fields.

Add GET /api/payments/{id} that returns the same payload for the session merchant, or not_found.

Tests in apps/api/tests/test_capture.py only:
- Successful fake capture stores the capture id and confirmed.
- Second capture does not append another capture_order call.
- A queued needs_checking PayPalCall, or a capture_order that raises, stores needs_checking after one attempt.
- A random UUID returns not_found.
- A payment inserted for a second Merchant, requested by the seeded owner, returns not_found.

Exit, from apps/api:
python -m pytest tests/test_capture.py tests/test_create_payment.py -q --tb=line

If that fails, fix once. If it fails again, stop and paste the failure. Do not start 4B. Reply in under 15 lines.
```

---

## 4B. Return and cancel pages

```
PayFlow Guardian, slice 4B only. 4A is done. Add the PayPal return and cancel pages. Do not change the API.

Read only:
- apps/web/lib/api.ts
- apps/web/app/(workspace)/payments/payments-workspace.tsx
- apps/web/app/(workspace)/payments/page.tsx
- apps/web/components/status-chip.tsx
- apps/web/components/card.tsx
- apps/web/components/error-banner.tsx
- apps/web/components/button.tsx

Do not open Stitch HTML, DESIGN.md, or node_modules. Do not restyle tokens, header, or login. Do not add a dependency.

In lib/api.ts add getPayment(id) and capturePayment(id). Reuse the existing fetch helper and ApiError. Do not send amount or currency.

Add these routes under the existing workspace layout:
- apps/web/app/(workspace)/payments/[id]/return/page.tsx
- apps/web/app/(workspace)/payments/[id]/cancel/page.tsx

Return page: call capturePayment once on mount. Show amount, currency, status chip, PayPal order id, and capture id from the response. The completed chip is allowed only when confirmation is confirmed. needs_checking uses the pending chip and the label Needs checking. Disable the button while the request is in flight. Show ErrorBanner on paypal_failed.

Cancel page: call getPayment once. Say the payment was not approved. Chip follows the stored status. Do not call capture.

Use Card, StatusChip, ErrorBanner, and Button. Keep the page readable below 768px by stacking the fields. Do not build the full detail page.

Exit, from apps/web:
npx tsc --noEmit

Do not start the dev server. If tsc fails, fix once. If it fails again, stop. Do not start phase 5. Reply in under 15 lines.
```

---

## 5A. Payment list API

```
PayFlow Guardian, slice 5A only. Add the merchant payment list. Do not build the dashboard or detail page.

Read only:
- apps/api/app/api/payments.py
- apps/api/app/modules/payments/service.py
- apps/api/app/modules/payments/models.py
- apps/api/tests/test_capture.py (fixture style only)

Do not edit capture_payment, create_test_payment, or the PayPal adapter.

Add list_payments(db, merchant_id) and GET /api/payments.
Return only that merchant's rows, newest first. Each item includes id, status, confirmation, amount_minor, currency, paypal_order_id, paypal_capture_id, paypal_status, updated_at, and test_order_code.
A missing session still uses the existing auth dependency. Do not add search yet.

Test in apps/api/tests/test_list_payments.py:
- Owner and support of the seeded merchant both receive the created payment.
- A payment inserted for a second merchant is absent from the seeded owner's list.
- GET /api/payments/{id} for that foreign id returns not_found.

Exit, from apps/api:
python -m pytest tests/test_list_payments.py tests/test_capture.py tests/test_create_payment.py -q --tb=line

One fix if it fails, then stop. Do not start 5B. Reply in under 15 lines.
```

---

## 5B. Payments table and detail

```
PayFlow Guardian, slice 5B only. 5A is done. Fill the payments table and the payment detail page from the API. Do not change the API.

Read only:
- apps/web/lib/api.ts
- apps/web/app/(workspace)/payments/payments-workspace.tsx
- apps/web/app/(workspace)/payments/new-test-order-modal.tsx
- apps/web/components/card.tsx
- apps/web/components/status-chip.tsx
- apps/web/components/empty-state.tsx
- apps/web/components/error-banner.tsx
- apps/web/components/button.tsx

Do not open Stitch files. Do not change login, header, or globals.css. Keep the New test order modal working, including its catalog amount and Idempotency-Key behavior.

Payments page:
- Load GET /api/payments.
- Show created time, catalog code, amount, currency, StatusChip, and PayPal reference.
- Empty list uses EmptyState plus the existing New test order action.
- Loading keeps the page chrome and shows a short "Loading payments" line.
- Errors use ErrorBanner.
- Below 768px, each payment is a stacked card with the same fields.

Add apps/web/app/(workspace)/payments/[id]/page.tsx:
- Title is the stored display amount and currency.
- Definition list: status, PayPal order id, capture id, amount, currency, updated time.
- StatusChip from server status and confirmation. Completed only when status is completed and confirmation is confirmed.
- needs_checking uses pending colors and the label Needs checking.
- Prepare refund is a disabled button with the caption that it opens after PayPal marks the payment completed.
- Ask the assistant links to /assistant?payment={id}.
- Back link goes to /payments.

Do not add search, filter chips, or a refresh button.

Exit, from apps/web:
npx tsc --noEmit

Do not start the dev server. One fix, then stop. Do not start 5C. Reply in under 15 lines.
```

---

## 5C. Dashboard counts

```
PayFlow Guardian, slice 5C only. Show live dashboard counts from stored payments. Refunds stay at zero.

Read only:
- apps/web/app/(workspace)/page.tsx
- apps/web/lib/api.ts
- apps/web/components/card.tsx
- apps/web/components/status-chip.tsx
- apps/web/components/empty-state.tsx

Do not edit the API. Do not invent sample totals. Zero is 0 or $0.00.

Derive these from GET /api/payments for the signed-in merchant:
- Open payments: count of rows that are not completed, failed, refunded, or partially_refunded.
- Awaiting customer: awaiting_payer.
- Refunds to review: 0.
- Confirmed today: completed and confirmation confirmed, updated today in UTC. Show the sum of those amounts as $0.00 when none.

Waiting on you: rows with needs_checking. Each row links to /payments/{id} and shows amount, StatusChip, PayPal reference, and updated time. If none, say no test payment is waiting.

Latest from PayPal: keep the card and show one line, "No PayPal events yet."

Use the existing Card and StatusChip. Do not add a new color or font.

Exit, from apps/web:
npx tsc --noEmit

Do not start the dev server. One fix, then stop. Do not start phase 6. Reply in under 15 lines.
```

---

## 6A. Search and investigate API

```
PayFlow Guardian, slice 6A only. Add search and a PayPal refresh. Do not build the assistant.

Read only:
- apps/api/app/api/payments.py
- apps/api/app/modules/payments/service.py
- apps/api/app/modules/payments/models.py
- apps/api/app/modules/paypal/types.py
- apps/api/app/modules/paypal/status.py
- apps/api/app/modules/activity/service.py
- apps/api/alembic/versions/0002_orders_payments.py (copy the revision header style only)
- apps/api/tests/test_list_payments.py (fixture style only)

Do not edit the PayPal HTTP client. FakePayPalAdapter.get_order_or_capture already exists. Use it.

Add alembic revision 0003_payment_fact_sheet, down_revision 0002_orders_payments. Add nullable payments.fact_sheet as Text. Add the same column on the Payment model. Tests create tables from the models, so the model change is what the tests use.

Extend GET /api/payments with optional query params q and status.
- q matches internal id, paypal_order_id, or paypal_capture_id for this merchant only.
- status matches the stored status. Pending means awaiting_payer or pending. Refunded means refunded or partially_refunded.
- No match returns an empty list, not an error.

Add investigate_payment(db, merchant_id, user_id, payment_id, paypal):
- Merchant scope or not_found.
- Call paypal.get_order_or_capture once.
- On success, update last_checked_at, paypal_status, and confirmation from the mapper in status.py. An unrecognized PayPal status becomes needs_checking and unconfirmed.
- Save this fact sheet JSON on the payment: payment_id, paypal_order_id, paypal_capture_id, paypal_status, local_status, confirmation, amount as a decimal string, currency, missing as an array, checked_at.
- Record payment.investigated.
- If the call raises or the body is unclear, keep the previous confirmation, set missing to the fields that were not refreshed, record that the refresh did not complete, and do not invent a new confirmed status.

Add POST /api/payments/{id}/investigate. Include fact_sheet on the detail payload.

Tests in apps/api/tests/test_investigate.py:
- Search by capture id returns only this merchant's payment.
- A successful read updates last_checked_at and fact_sheet.
- A failed read leaves a prior confirmed status unchanged.
- An unrecognized paypal_status becomes needs_checking.

Exit, from apps/api:
python -m pytest tests/test_investigate.py tests/test_list_payments.py tests/test_capture.py -q --tb=line

One fix, then stop. Do not start 6B. Reply in under 15 lines.
```

---

## 6B. Search and refresh UI

```
PayFlow Guardian, slice 6B only. 6A is done. Bind search, filter chips, and refresh. Do not change the API.

Read only:
- apps/web/app/(workspace)/payments/payments-workspace.tsx
- apps/web/app/(workspace)/payments/[id]/page.tsx
- apps/web/lib/api.ts
- apps/web/components/button.tsx
- apps/web/components/text-field.tsx
- apps/web/components/status-chip.tsx
- apps/web/components/error-banner.tsx

Do not open Stitch HTML. Do not change the New test order flow.

Payments toolbar:
- A 40px search field, placeholder "PayPal reference". Submit sends q to GET /api/payments.
- Chips: All, Completed, Pending, Needs checking, Failed, Refunded. The active chip uses a #0070E0 outline. They send the status filter from 6A. All clears it.

Detail page:
- Secondary button "Refresh from PayPal" calls POST /api/payments/{id}/investigate.
- "What PayPal returned" renders the fact sheet, including missing fields.
- A failed refresh keeps the previous chip and says the check did not complete.
- The note stays visible while confirmation is unconfirmed.
- The chip still comes from the server confirmation field.

Disable the refresh button until the response returns. Do not add an assistant.

Exit, from apps/web:
npx tsc --noEmit

Do not start the dev server. One fix, then stop. Do not start phase 7. Reply in under 15 lines.
```

---

## 7A. Assistant API

```
PayFlow Guardian, slice 7A only. Add the assistant API with a fake model. Do not build the page. Do not call a real model.

Read only:
- apps/api/app/api/router.py
- apps/api/app/api/deps.py
- apps/api/app/modules/assistant/__init__.py
- apps/api/app/modules/payments/service.py (call existing functions, do not rewrite them)
- apps/api/app/modules/activity/models.py (for a message table style only if you need column types)
- apps/api/app/core/config.py
- apps/api/alembic/versions/0002_orders_payments.py (revision header style only)

Do not edit the PayPal client. The assistant must not import httpx or modules.paypal.

Add alembic 0004_assistant_messages, down_revision 0003_payment_fact_sheet. Table assistant_messages: id, merchant_id, user_id, conversation_id, role, content, tool_name nullable, created_at. No provider payload column.

New files:
- apps/api/app/modules/assistant/tools.py
- apps/api/app/modules/assistant/service.py
- apps/api/app/api/assistant.py

Tools, and no others:
- find_payment
- list_recent_payments
- create_test_order (calls create_test_payment, catalog amount only)
- complete_approved_payment (calls capture_payment)
- investigate_payment
- prepare_refund_request (return the text "available in the next phase" and do not write a refund)
- check_operation_status

Validate arguments before running a tool. Unknown tool name is rejected and not executed. Payment ids resolve inside the session merchant. A foreign id is not_found.

Loop at most 3 tool calls, then require a final answer. The model is a function argument, defaulting to a fake that returns a final answer. Tests pass their own fake model.

The server picks next_step from stored status, not from model text:
- awaiting_payer -> approve_on_paypal
- needs_checking or unconfirmed -> refresh_payment
- completed and confirmed -> prepare_refund
- failed -> show_failure

POST /api/assistant/messages body {message, conversation_id}. Response: answer, next_step, confirmation, fact_sheet. confirmation in the response is the stored value. Persist user message, tool name, and final answer only.

Register the router in api/router.py.

Tests in apps/api/tests/test_assistant.py:
- Unknown tool is rejected.
- A fact sheet with confirmation unconfirmed stays unconfirmed in the response.
- create_test_order through the assistant stores 2500 USD for DEMO-25.
- The tool map has exactly the seven names above and no approve or send name.
- A foreign payment id is reported as not found.
- Support and owner can both call the route.

Exit, from apps/api:
python -m pytest tests/test_assistant.py tests/test_create_payment.py tests/test_capture.py -q --tb=line

One fix, then stop. Do not start 7B. Reply in under 15 lines.
```

---

## 7B. Assistant page

```
PayFlow Guardian, slice 7B only. 7A is done. Build /assistant from the API. Do not change the API or the tool list.

Read only:
- apps/web/app/(workspace)/assistant/page.tsx
- apps/web/lib/api.ts
- apps/web/components/card.tsx
- apps/web/components/button.tsx
- apps/web/components/text-field.tsx
- apps/web/components/status-chip.tsx
- apps/web/components/error-banner.tsx

Do not open Stitch HTML. Do not add a dependency.

Replace the empty assistant page with a client view:
- Thread column max 720px and a context rail max 360px. Below 768px the rail stacks under the thread.
- Composer: 40px field and a primary Send button. Disable Send until the response returns.
- Show the merchant message, the answer, and whether a PayPal read was used (next_step refresh_payment or a fact_sheet checked_at).
- Rail shows fact sheet amount, currency, PayPal reference, time, and StatusChip. The chip reads confirmation from the API. Do not let the answer text change the chip.
- Rail includes this sentence: The assistant cannot approve or send a refund.
- One suggested link only, from next_step: open /payments/{id}, or /refunds/{id} only if the API later sends a refund id. No approve button in the thread.
- If the request fails, say the explanation could not be completed. Keep the last fact sheet on the rail.

Read payment from the query string ?payment= and send it only as part of the merchant message text, not as a hidden amount.

Exit, from apps/web:
npx tsc --noEmit

Do not start the dev server. One fix, then stop. Do not start phase 8. Reply in under 15 lines.
```

---

## 8A. Prepare a refund

```
PayFlow Guardian, slice 8A only. Prepare a refund. Do not call PayPal refund. Do not add approve.

Read only:
- apps/api/app/modules/payments/models.py
- apps/api/app/modules/payments/service.py (read capture fields, do not rewrite capture)
- apps/api/app/modules/assistant/tools.py
- apps/api/app/api/router.py
- apps/api/app/core/errors.py
- apps/api/app/modules/activity/service.py
- apps/api/alembic/versions/0002_orders_payments.py (revision header style only)
- apps/api/tests/test_assistant.py (fixture style only)

Add approval_required(message) as AppError("approval_required", message, 409) if it is missing.

Add alembic 0005_refund_requests, down_revision 0004_assistant_messages. Table refund_requests:
id, merchant_id, payment_id, capture_id, amount_minor, currency, reason, payload_hash, status, prepared_by, approved_by nullable, approved_at nullable, approved_hash nullable, paypal_refund_id nullable, paypal_status nullable, created_at, updated_at.
Unique paypal_refund_id when present. One open request per capture means status in pending_approval or needs_checking.

prepare_refund:
- Merchant owns the payment, or not_found.
- Payment is completed and confirmation confirmed, with a capture id. Otherwise validation_failed.
- Amount greater than zero and no greater than the captured amount. Currency must match. Reason required.
- Insert pending_approval. payload_hash covers payment id, capture id, amount, currency, and reason.
- Do not call refund_capture. A second prepare for the same open capture returns that request.
- Record refund.prepared.

POST /api/refunds accepts payment_id, amount_minor, currency, reason. The server still checks them against the stored payment. GET /api/refunds/{id} is merchant scoped.

Replace the prepare_refund_request stub so it calls prepare_refund. Leave every other tool unchanged.

Tests in apps/api/tests/test_prepare_refund.py:
- Prepare records zero refund_capture calls on the fake adapter.
- Second prepare returns the same id.
- Foreign payment id returns not_found.
- Amount above the capture returns validation_failed and writes nothing.

Exit, from apps/api:
python -m pytest tests/test_prepare_refund.py tests/test_assistant.py -q --tb=line

One fix, then stop. Do not start 8B. Reply in under 15 lines.
```

---

## 8B. Approve and reject

```
PayFlow Guardian, slice 8B only. 8A is done. Owner approve is the only path that calls refund_capture.

Read only:
- apps/api/app/modules/refunds/ (the prepare module from 8A)
- apps/api/app/api/refunds.py if it exists, otherwise the router file you added in 8A
- apps/api/app/modules/auth/service.py (require_owner already exists)
- apps/api/app/modules/paypal/fake.py (queue refund_capture, do not rewrite it)
- apps/api/app/modules/paypal/types.py
- apps/api/app/core/errors.py
- apps/api/tests/test_prepare_refund.py

Do not add a separate send route. Do not give the assistant an approve tool.

Add approval_stale(message) as AppError("approval_stale", message, 409).

POST /api/refunds/{id}/approve, owner only:
- Lock the row with with_for_update. Recompute payload_hash. Mismatch returns approval_stale and does not call PayPal.
- Support receives forbidden and zero refund calls.
- pending_approval is required. Already completed returns the stored refund and does not call PayPal again.
- Then call paypal.refund_capture(capture_id, amount_minor, currency, request_id=refund id).
- Success stores paypal_refund_id, paypal_status, completed, and refund.completed.
- Explicit failure stores failed and refund.failed.
- Timeout or unclear body stores needs_checking, keeps the same refund id, and does not create another refund.
- Record refund.approved before the PayPal result event.

POST /api/refunds/{id}/reject, owner only: status rejected, record refund.rejected, zero PayPal calls.
Changing amount, currency, reason, or payment before submit clears approved_by, approved_at, and approved_hash and returns the row to pending_approval. There is no edit route in this slice unless prepare already replaced those fields. If there is no edit function, do not add a general editor. Add only the hash check used by approve.

Tests in apps/api/tests/test_approve_refund.py:
- Owner approve performs one refund_capture. Second approve performs none.
- Hash mismatch returns approval_stale and zero refund calls.
- Support approve returns forbidden and zero refund calls.
- A queued unclear refund result stores needs_checking and does not call refund again.
- A foreign refund id returns not_found.
- Reject performs zero refund calls.

Exit, from apps/api:
python -m pytest tests/test_approve_refund.py tests/test_prepare_refund.py tests/test_assistant.py -q --tb=line

One fix, then stop. Do not start 8C. Reply in under 15 lines.
```

---

## 8C. Refund screens

```
PayFlow Guardian, slice 8C only. 8B is done. Build the refund list and review page. Do not change approve rules.

Read only:
- apps/web/app/(workspace)/refunds/page.tsx
- apps/web/app/(workspace)/payments/[id]/page.tsx
- apps/web/lib/api.ts
- apps/web/components/card.tsx
- apps/web/components/button.tsx
- apps/web/components/status-chip.tsx
- apps/web/components/error-banner.tsx
- apps/web/components/empty-state.tsx
- apps/api/app/api/refunds.py (response fields only)

Do not open Stitch HTML. Do not add an approve control on /assistant.

Enable Prepare refund on the payment detail page only when status is completed and confirmation is confirmed. It posts the stored amount and currency, plus a reason field, to POST /api/refunds, then links to /refunds/{id}. The client must not invent a different amount.

/refunds lists requests from GET /api/refunds. If that list route is missing, stop and say so. Do not invent a second list shape. Each row links to /refunds/{id}. Empty state says no refund is waiting.

/refunds/[id]:
- Title Refund draft.
- Chip Not sent while pending_approval. After approve, chip comes from the response status.
- Show payment reference, original amount, refund amount, currency, reason, and who prepared it.
- Note: Approving sends the refund to PayPal Sandbox.
- Owner sees Reject (quiet) and Approve and send (primary). Support sees the payload and the sentence "Support cannot send this refund." and does not see the buttons.
- approval_stale uses ErrorBanner and says to approve the current request again.
- Disable the buttons until the response returns.
- Show paypal_refund_id and paypal_status from the response. Do not show a refund id that the API did not return.

Exit, from apps/web:
npx tsc --noEmit

Do not start the dev server. One fix, then stop. Do not start phase 9. Reply in under 15 lines.
```

---

## 9A. Activity feed

```
PayFlow Guardian, slice 9A only. Show activity the earlier slices already record. Do not add webhooks.

Read only:
- apps/api/app/modules/activity/service.py
- apps/api/app/modules/activity/models.py
- apps/api/app/api/router.py
- apps/web/app/(workspace)/page.tsx
- apps/web/app/(workspace)/payments/[id]/page.tsx
- apps/web/lib/api.ts
- apps/web/components/card.tsx

Do not change payment, refund, or assistant write logic in this slice. If a write path is missing an activity.record call, stop and name the path. Do not patch it here.

Add GET /api/activity for the session merchant, newest first, limit 50. Fields: action, summary, outcome, amount_minor, currency, paypal_reference, actor_type, created_at. No tokens, secrets, or card data.

Dashboard "Latest from PayPal" renders those events: time, one-line summary, PayPal reference. Replace the empty line from 5C.
Waiting on you also lists refunds in pending_approval when GET /api/refunds returns them, linking to /refunds/{id}. Keep the needs_checking payment rows.

Payment detail Activity: a simple list, time plus one sentence. The newest row uses color #0070E0 for its marker. Do not add a chart.

Test in apps/api/tests/test_activity_feed.py:
- Events from another merchant are absent.
- A created payment produces a payment.created row for this merchant.
- The payload has no field named authorization, client_secret, api_key, password, or access_token.

Exit, from apps/api, then apps/web:
python -m pytest tests/test_activity_feed.py tests/test_activity.py -q --tb=line
npx tsc --noEmit

One fix, then stop. Do not start 9B. Reply in under 15 lines.
```

---

## 9B. Safety test sweep

```
PayFlow Guardian, slice 9B only. Add the missing safety tests. Do not add features. Do not add webhooks.

Read only:
- apps/api/tests/ (test file names and the assertions, not a rewrite)
- the service function you need if a test shows a real hole

Allowed product edits: a bug that makes one of the checks below fail. Do not refactor passing code.

These checks must already pass or get one new test each. Put new tests in apps/api/tests/test_safety_sweep.py. Reuse fixtures from the existing test files. Do not duplicate a test that already exists. Say which existing test covers a check.

- Create DEMO-25 stores 2500 USD.
- Capture stores confirmed only from a successful fake capture.
- Unconfirmed assistant response stays unconfirmed.
- Prepare performs zero refund_capture calls.
- Stale approval performs zero refund_capture calls.
- A second merchant gets not_found.
- Second capture and second approve add zero extra PayPal calls.
- Timeout or unclear PayPal result stores needs_checking.
- Log filter test still exists in test_log_filter.py. Do not weaken it.

Exit, from apps/api:
python -m pytest tests -q --tb=line

If the full suite fails, fix once only if the failure is in the new sweep or a one-line assertion bug. If a failure needs a redesign, stop and report it. Do not start phase 10. Reply in under 15 lines.
```

---

## 10A. Webhooks (optional)

```
PayFlow Guardian, optional slice 10A. Skip this whole prompt if you are short on time. Phase 11 does not need it.

Add PayPal webhook intake. Do not change capture or approve.

Read only:
- apps/api/app/api/router.py
- apps/api/app/modules/paypal/status.py
- apps/api/app/modules/activity/service.py
- apps/api/app/core/config.py
- apps/api/alembic/versions/0002_orders_payments.py (revision header style only)

Do not verify a signature by calling the network in tests. Put verification in a function the test can stub. An unverified payload changes nothing.

Add alembic 0006_paypal_events, down_revision 0005_refund_requests. Table paypal_events with a unique paypal_event_id.

POST /api/webhooks/paypal is public. Require PAYPAL_WEBHOOK_ID in settings when the route is called for real. A duplicate paypal_event_id updates nothing. A verified event uses map_paypal_status and records activity. It must not create a second capture or refund.

Test in apps/api/tests/test_webhooks.py:
- Same paypal_event_id twice causes one state change.
- Unverified body leaves the payment unchanged.

Exit, from apps/api:
python -m pytest tests/test_webhooks.py tests/test_capture.py tests/test_approve_refund.py -q --tb=line

One fix, then stop. Do not start 10B unless this exit is green. Reply in under 15 lines.
```

---

## 10B. Saved versus PayPal (optional)

```
PayFlow Guardian, optional slice 10B. Do this only after 9B is green. Do not add webhooks here.

Read only:
- apps/api/app/modules/payments/service.py (the investigate_payment function)
- apps/web/app/(workspace)/payments/[id]/page.tsx
- apps/api/tests/test_investigate.py

Extend investigate_payment. Compare stored capture id, amount, currency, and status with the fresh PayPal read. On a mismatch, set needs_checking, keep confirmation unconfirmed, and record payment.mismatch. Do not call refund or capture.

Detail note bar, only when the fact sheet says mismatch: The saved payment and the latest PayPal data differ and need a check. Chip stays Needs checking.

Add one test: a queued PayPal amount that differs from the stored amount sets needs_checking and does not change the stored amount.

Exit, from apps/api, then apps/web:
python -m pytest tests/test_investigate.py -q --tb=line
npx tsc --noEmit

One fix, then stop. Reply in under 15 lines.
```

---

## 11. README and submission

```
PayFlow Guardian, slice 11 only. Write the README from the code that exists. Do not add features.

Read only:
- README.md if it exists
- .env.example
- docs/implementation-plan.md sections "Phase 11" and "Definition of done"
- apps/api/app/api/router.py
- apps/api/tests/test_safety_sweep.py (names of checks only)

Do not open node_modules or .venv. Do not put real secrets, passwords, or employer details in the README. Seeded demo passwords may be described as the values already in .env.example or the seed module. Do not copy live keys.

README must include:
- What the product does, who it is for, and these safety rules: PayPal confirms a payment, the owner is the only refund send path, unclear PayPal results stay needs_checking.
- Sandbox only. Say what is not included.
- Setup with Docker Compose, .env.example, and the seeded owner and support users.
- The demo steps that the finished routes actually support. Omit any phase 10 feature that has no route.
- How to see that an unapproved refund is blocked and that support cannot approve.

Do not claim a YouTube video exists unless a URL is already in the repo. Leave a single placeholder line: "Demo video: add the public YouTube URL."

Search the repo, excluding node_modules, .next, .venv, and .git, for PAYPAL_CLIENT_SECRET values that are not empty placeholders. If you find a live secret, stop and report the path. Do not print the secret.

Do not change application code. Exit when the README covers the list above. Reply in under 15 lines.
```
