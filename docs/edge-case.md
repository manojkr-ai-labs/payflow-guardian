# PayFlow Guardian Edge Cases

This document lists the edge cases PayFlow Guardian must handle. It follows [architecture.md](./architecture.md) and [implementation-plan.md](./implementation-plan.md).

Each case names the situation, the required outcome, and the phase that implements it. Automated tests use the fake PayPal adapter. Sandbox is only for the checks the implementation plan marks as manual.

Confirmed status comes only from a recognized PayPal response that includes a PayPal order or capture id. Anything unclear is `needs_checking` and `unconfirmed`. The merchant-facing badge is the server `confirmation` field.

## Error codes

| Code | Use |
| --- | --- |
| `not_found` | The payment or refund does not exist for this merchant. A foreign id uses the same code as a missing id. |
| `validation_failed` | The catalog code, amount, currency, reason, or idempotency key is unacceptable. |
| `approval_required` | A refund send was attempted without a current owner approval. |
| `approval_stale` | The refund payload changed and must be approved again. |
| `paypal_failed` | PayPal explicitly failed the call. |
| `needs_checking` | The PayPal result is missing, timed out, or unrecognized. |
| `forbidden` | The signed-in role cannot approve or reject a refund. |

## 1. Configuration and session

Implemented in phase 1.

| Case | Required outcome |
| --- | --- |
| `DATABASE_URL`, `SESSION_SECRET`, `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_API_BASE`, or `WEB_ORIGIN` is missing | The API refuses to start and names the missing setting. |
| `PAYPAL_WEBHOOK_ID` is empty before phase 10 | Startup succeeds. The webhook route is absent. |
| `AI_API_KEY` is empty before phase 7 | Startup succeeds. The assistant route is absent until phase 7. |
| `AI_API_KEY` is empty in phase 7 | Assistant calls fail with an honest unavailable message. Payment pages still show stored PayPal facts. |
| Request has no session, an expired session, or a logged-out cookie | Protected routes reject the request. Login stays public. The optional webhook is the only other route without a session, and only in phase 10. |
| Session belongs to a user who is not a member of the payment's merchant | Payment and refund reads return `not_found`. |
| Support user calls an owner-only approve or reject route | `forbidden`. No refund row is approved and PayPal is not called. |
| Owner and support both view the same merchant's payment | Both receive the stored payment. |
| Log line contains `authorization`, `client_secret`, `api_key`, `password`, or `access_token` | The log filter removes those values. PayPal ids and HTTP status may remain. |
| Web build or `.env.example` is inspected | No real PayPal secret, AI key, database URL, or session secret is present. |

## 2. PayPal adapter

Implemented in phase 2. Capture, read, and refund callers arrive in later phases. The mapping rules apply as soon as those callers exist.

| Case | Required outcome |
| --- | --- |
| Token request succeeds | The access token stays in process memory. It is not written to Postgres or logs. |
| PayPal returns 401 for a call | The adapter refreshes the token once and retries that call once. |
| Token refresh also fails | The payment operation returns `paypal_failed` when PayPal explicitly rejects the credentials, or `needs_checking` when the result is unclear. The secret is not included in the message. |
| PayPal status is `COMPLETED`, `PENDING`, `FAILED`, refunded, or partially refunded | Map to `completed`, `pending`, `failed`, `refunded`, or `partially_refunded` with `confirmation = confirmed` when the PayPal id is present. |
| PayPal status is payer action required or the order is created and waiting | Map to `awaiting_payer` and `confirmed` only when the PayPal order id is present. The payment is not treated as captured. |
| PayPal status string is unknown, the body is partial, or the HTTP status is 5xx | `needs_checking` and `unconfirmed`. Do not guess a completed or failed payment. |
| The network call times out after PayPal may have accepted a capture or refund | `needs_checking` and `unconfirmed`. Do not automatically send a second capture or refund. |
| Another module tries to call PayPal with its own HTTP client | That path does not exist. Only `modules/paypal` accepts PayPal traffic. |

## 3. Create a test order

Implemented in phase 3.

| Case | Required outcome |
| --- | --- |
| Merchant selects `DEMO-25` or `DEMO-49` | The stored amount and currency are the catalog values: 2500 USD or 4900 USD. The PayPal order uses those values. |
| Body includes a different amount or currency | Those fields are ignored. The catalog values are stored and sent. |
| Catalog code is missing or unknown | `validation_failed`. No order row and no PayPal call. |
| `Idempotency-Key` header is missing | `validation_failed`. No order row and no PayPal call. |
| Same merchant, same idempotency key, and same catalog code are sent again | The original payment is returned. PayPal create runs once. |
| Same idempotency key is reused with a different catalog code | The request is rejected. The original payment stays unchanged. |
| Two merchants use the same idempotency key and catalog code | Each merchant gets their own payment. The key is scoped by `merchant_id`. |
| Two identical creates arrive together | One PayPal order is created. The other request returns that same payment. |
| PayPal explicitly says the order was not created | Store `failed` when a local row was opened, return `paypal_failed`, and show PayPal's message. |
| Create times out or the body has no PayPal order id | Store `needs_checking` and `unconfirmed`. A repeat of the same idempotency key returns that row and does not open a second PayPal order. |
| Create returns an order id and an unrecognized status | Store the PayPal order id, `needs_checking`, and `unconfirmed`. |
| PayPal response amount or currency differs from the catalog value | Keep the catalog amount and currency. Set `needs_checking`. Do not replace the stored amount with a client value. |

## 4. Approval and capture

Implemented in phase 4.

| Case | Required outcome |
| --- | --- |
| Customer approves on PayPal and the merchant returns to the app | Capture runs. A recognized completed response stores `paypal_capture_id`, `completed`, and `confirmation = confirmed`. |
| Capture is clicked twice, or the return page loads twice | The first confirmed capture is stored. The second call returns that row and does not call PayPal. |
| Two capture requests arrive together | The row lock lets one call PayPal. The other waits and then returns the stored result. |
| PayPal capture times out, or the body is unrecognized | Store `needs_checking` and `unconfirmed`. Record `payment.needs_checking`. Do not capture again automatically. |
| A later capture call finds `needs_checking` | Return the stored row. Do not send another capture. The merchant refreshes the payment from PayPal in phase 6. |
| PayPal explicitly fails the capture with a failure status | Store `failed` and return `paypal_failed`. |
| PayPal still reports payer action required | Keep `awaiting_payer`. Tell the merchant the customer has not approved the payment. Do not mark it failed or completed. |
| Customer cancels and PayPal reports the order void | Store `failed`. The UI says the payment was not approved. |
| Customer cancels and PayPal has no cancel event | Leave `awaiting_payer`. The UI says the payment was not approved. |
| Return URL payment id belongs to another merchant, or the id does not exist | `not_found`. No capture call. |
| Capture is requested before a PayPal order id exists | `needs_checking` is returned from the stored row. PayPal capture is not called. |
| Local save fails after PayPal may have captured | The row is left `needs_checking` rather than dropped. A later read reconciles it from PayPal. |

## 5. List and detail

Implemented in phase 5.

| Case | Required outcome |
| --- | --- |
| Merchant has no payments | The dashboard explains that no test payments exist yet. |
| Payment is `needs_checking` | The screen says the payment needs a check and shows `last_checked_at` when a successful check exists. |
| Detail is opened for a stored completed payment | Amount, currency, status, confirmation, and PayPal ids match the stored row that was mapped from PayPal. |
| Detail id is unknown or belongs to another merchant | `not_found`. The response does not reveal whether the id exists elsewhere. |
| Support opens a payment for their merchant | The same detail as the owner, without an approve action. |

## 6. Search and investigation

Implemented in phase 6.

| Case | Required outcome |
| --- | --- |
| Search by internal id, PayPal order id, PayPal capture id, or status | Results are limited to the session merchant. |
| Search matches nothing, including another merchant's PayPal id | Empty list for search. Direct detail still returns `not_found`. |
| Investigate receives a full recognized PayPal body | The fact sheet copies PayPal ids, PayPal status, amount, currency, confirmation, and `checked_at`. `missing` is empty. `last_checked_at` updates. |
| PayPal body omits a field | That field name is listed in `missing`. The explanation does not fill it in. |
| First investigate cannot reach PayPal and no earlier confirmation exists | Stored confirmation stays `unconfirmed`. The fact sheet has `paypal_status = null` and lists the fields that could not be refreshed. Activity records the failed refresh. |
| A later refresh cannot reach PayPal after a prior confirmed read | The stored `confirmation` stays as it was. Previously confirmed values remain labeled with the last successful `checked_at`. The new fact sheet says this refresh did not complete. The assistant does not describe the payment as newly completed. |
| PayPal returns an unrecognized status during refresh | Set `needs_checking` and `unconfirmed`. |
| Investigate is asked for a foreign or missing payment | `not_found`, including when the assistant calls `investigate_payment`. |

The failed-refresh rule is the one in the architecture failure table and phase 6: a prior confirmation is kept. The fact sheet for the failed attempt still says the latest check did not complete.

## 7. Assistant

Implemented in phase 7. Refund preparation inside the assistant is live in phase 8.

| Case | Required outcome |
| --- | --- |
| Merchant asks to find, list, create, capture, investigate, or check status | The assistant may call only `find_payment`, `list_recent_payments`, `create_test_order`, `complete_approved_payment`, `investigate_payment`, `prepare_refund_request`, and `check_operation_status`. |
| The model requests any other tool, including approve, reject, send, SQL, shell, or arbitrary HTTP | The server rejects the tool call. PayPal is not contacted by that call. |
| The model returns more than three tool calls | The loop stops. The reply uses the facts already collected. |
| Tool arguments name a payment outside the merchant | The tool result is not found. The reply says it was not found. |
| Tool arguments are the wrong shape | The tool is not run. The merchant sees a validation message. |
| `create_test_order` is given an amount in the model arguments | The catalog amount and currency are used. |
| `complete_approved_payment` runs when the payer has not approved | The payment stays `awaiting_payer` when that is PayPal's status. The reply tells the merchant the customer still needs to approve. |
| `investigate_payment` returns `confirmation = unconfirmed` | The API badge stays unconfirmed. Prose from the model cannot change it. |
| The fact sheet has entries in `missing` | The reply states that those facts are unknown. |
| The model is unavailable or times out | The transcript says the explanation could not be completed and still shows the latest stored payment facts and badge. |
| The server next-step table matches `needs_checking` | The recommended step is to refresh the payment before taking action. |
| The payment is `completed` and there is no open refund | The recommended step is to offer refund preparation. |
| A refund is `pending_approval` | The recommended step opens the approval screen. The chat transcript has no approve control. |
| A refund is `completed` | The recommended step shows the PayPal refund reference. |
| The payment or refund is `failed` | The recommended step shows PayPal's failure and does not start another money movement. |
| A raw provider payload would be stored | Only the user message, tool names, and final answer are stored. |

## 8. Refund preparation

Implemented in phase 8.

| Case | Required outcome |
| --- | --- |
| Prepare on a confirmed `completed` capture with a positive amount in the capture currency, not above the captured amount | Insert `pending_approval` with payment reference, amount, currency, and reason. `paypal_refund_id` is empty. PayPal refund is not called. |
| Prepare is requested again while that request is open | Return the open request. Do not insert a second one. |
| Amount is zero, negative, or greater than the captured amount | `validation_failed`. No request row and no PayPal refund call. |
| Currency differs from the captured payment | `validation_failed`. No PayPal refund call. |
| Reason is blank | `validation_failed`. The approval screen always has a reason to review. |
| Payment is `awaiting_payer`, `pending`, `failed`, `needs_checking`, or `unconfirmed` | Refuse preparation. No PayPal refund call. |
| Payment is already `refunded` or the only request is `completed` | Return the completed refund result. Do not create another PayPal refund. |
| Payment is `partially_refunded` | Keep that status as PayPal reported it. Do not automatically prepare or send another refund. |
| The previous request is `rejected` or `failed` | A new prepare may create a new `pending_approval` request. |
| Prepare is called by the assistant or by `POST /api/refunds` | Both use the same service and the same checks. |
| Payment or refund id is foreign or missing | `not_found`. |

## 9. Refund approval, rejection, and send

Implemented in phase 8.

| Case | Required outcome |
| --- | --- |
| Owner approves a current `pending_approval` request | Lock the row, recompute `payload_hash`, read the capture from PayPal, then call `refund_capture` with `PayPal-Request-Id` set to the refund id. |
| Support, or any non-owner, calls approve or reject | `forbidden`. No state change and no PayPal call. |
| Approve is called on a request that is still `pending_approval` through any path other than the owner approve route | No such path exists. `prepare_refund_request` cannot send. |
| Amount, currency, reason, or target payment changes before a confirmed submit | Clear `approved_by`, `approved_at`, and `approved_hash`. Status returns to `pending_approval`. The next approve without a fresh match returns `approval_stale` and does not call PayPal. |
| Owner approves after the stored hash no longer matches the capture, amount, or currency | `approval_stale`. The request stays `pending_approval`. PayPal refund is not called. |
| Someone edits a request in `submitting`, `completed`, or `needs_checking` | The edit is refused. Those states cannot be turned into a second PayPal call. |
| Two owners approve at the same time | The row lock allows one transition from `pending_approval` to `submitting`. The other caller receives the stored result. |
| Approve is repeated after `completed` | Return the stored PayPal refund id and status. PayPal is not called again. |
| PayPal explicitly fails the refund | Store `failed`, return `paypal_failed`, and show PayPal's message. |
| PayPal refund times out or the body is unclear | Store `needs_checking` on that same refund id. Do not create another refund request and do not send again automatically. |
| A later status check runs for a `needs_checking` refund | Read status with the same `PayPal-Request-Id`. Keep `needs_checking` until PayPal returns a recognized result. |
| PayPal recheck on approve shows the capture is no longer refundable | Do not call refund. Leave the request unsent and show that the payment needs a check. |
| Owner rejects `pending_approval` | Store `rejected`. PayPal is not called. A later prepare may start a new request. |
| Reject or approve is called on another merchant's refund | `not_found`. |
| The UI still shows an old approve button after the payload changed | The API returns `approval_stale` or `forbidden` from the current row and role. The button label is not the authority. |

## 10. Activity

Implemented from phase 1 as a writer, and shown to the merchant in phase 9.

| Case | Required outcome |
| --- | --- |
| Create, capture, investigate, prepare, approve, reject, or a PayPal result succeeds or becomes unclear | An activity event is written in the same transaction as the local state change. |
| The merchant opens activity | Events are only those for the session merchant and include amount, currency, PayPal reference, actor, and outcome when those exist. |
| An event is written for a secret-bearing value | The row keeps ids, amounts, currency, and PayPal references. It has no access token, client secret, API key, card number, or security code. |
| There are no events yet | The activity list is empty and the dashboard says there is nothing to review. |
| A payment is `needs_checking` or a refund is `pending_approval` | The dashboard includes it in the actions that need attention. |
| Support opens activity | Support sees the merchant's events and cannot approve from that list. |

## 11. Optional phase

These cases apply only after phase 9. If phase 10 is not built, the product does not expose a webhook, and the demo does not depend on one.

| Case | Required outcome |
| --- | --- |
| Webhook signature is missing or invalid | The body is ignored. No payment or refund changes. |
| `PAYPAL_WEBHOOK_ID` is empty | The webhook cannot verify events, so it does not apply them. |
| The same `paypal_event_id` is delivered twice | The first verified event updates state once. The duplicate changes nothing. |
| Verified event refers to an unknown PayPal id | No local row is created from the event. |
| Verified event has a known status | The same status mapper as the pull path updates the payment or refund, then activity is appended. |
| Timeline is requested for a foreign payment | `not_found`. |
| Saved capture id, amount, currency, or status differs from a fresh PayPal read | Set `needs_checking` and record `payment.mismatch`. |
| Fresh PayPal read matches the stored payment | Do not record a mismatch. Refresh `last_checked_at`. |

## 12. Cases the product must leave alone

These are boundaries from the problem statement, not gaps to fill.

| Case | Required outcome |
| --- | --- |
| A caller asks for a live PayPal charge | The app talks only to the configured Sandbox base URL. |
| The model or browser asks to skip owner approval | The request stays `pending_approval` until the owner approve route passes. |
| A card number or security code is submitted | No column stores it. The payment flow never collects it. |
| The assistant is asked to guarantee fraud prevention or recovery | The reply stays inside the PayPal fact sheet and the server next step. |
| A fixture did not come from PayPal Sandbox | The UI labels it as a test example. Activity for a real Sandbox call includes the PayPal reference. |

## 13. Exit mapping

The phase 9 test pass covers the required edges. Phase 10 adds the last two rows only if that phase is built.

| Exit check | Edge cases that prove it |
| --- | --- |
| Catalog amount wins | Client amount ignored. Model amount ignored. |
| One create, one capture, one refund | Repeated idempotency key, repeated capture, repeated approve, concurrent approve. |
| Confirmed means PayPal said so | Unknown status, partial body, and model prose cannot set the badge. |
| Unclear stays unclear | Create timeout, capture timeout, refund timeout, and failed refresh. |
| Refund is human gated | Prepare performs zero refund calls. Support receives `forbidden`. Edited payload returns `approval_stale`. |
| Isolation | Foreign payment and refund ids return `not_found`. |
| Secrets stay server-side | Log filter and web bundle checks. |
| Webhook is safe | Invalid signature ignored. Duplicate `paypal_event_id` applied once. |
| Comparison is honest | Mismatch sets `needs_checking` and `payment.mismatch`. |
