# Evaluation record

Recorded 12 Nov 2026. Git commit `8fadaee92fc91ded5e61c01374dde1172fed58c8`. The running API also had the uncommitted assistant planner from this working tree (`apps/api/app/modules/assistant/model.py` and the assistant route and service changes). PayPal Sandbox credentials were the local `.env` values. No secret is written here.

## Sandbox journey

| Field | Value |
| --- | --- |
| Suite | Sandbox journey |
| Eval | `EV-DEMO-01` |
| Result | pass |
| Failed ids | none |

The owner signed in as `owner@payflow.test` and created `DEMO-25`. PayPal stored the order as 25.00 USD. A Sandbox buyer approved that order on PayPal and returned to the app. The return page captured it once.

| Step | What was checked | Result |
| --- | --- | --- |
| 1 | Owner creates `DEMO-25` and PayPal receives 25.00 USD | Payment `b6053008-4f3d-4860-93bc-b8d51a612201`, order `1PR32201LL3551506`, stored amount 2500 USD. PayPal order read was 25.00 USD. |
| 2 | Sandbox buyer approves on PayPal | Checkout returned to the app with a payer id. |
| 3 | App shows `confirmation = confirmed` and a PayPal capture id | Chip Completed. Confirmation `confirmed`. Capture `57B499451D290335P`. PayPal status `COMPLETED`. |
| 4 | Assistant investigation returns a fact sheet from that PayPal payment | Answer named 25.00 USD and capture `57B499451D290335P`. The page said a PayPal read was used. |
| 5 | On-screen badge matches `confirmation` beside the answer | Badge Completed, which is the chip for `completed` and `confirmed`. The answer said PayPal confirmed the payment as completed. |
| 6 | Prepare creates `pending_approval` and does not create a PayPal refund id | Refund `06d5bb3e-fb21-4e9c-b44f-06d851710f25` was `pending_approval`. `paypal_refund_id` was empty. Chip Not sent. |
| 7 | Approval screen shows the payment reference, amount, currency, and reason | Capture `57B499451D290335P`, 25.00 USD, and the reason were on the draft. |
| 8 | Owner approve shows the PayPal refund result | PayPal refund `8G8751151Y513444S`, PayPal status `COMPLETED`, chip Completed. |
| 9 | Activity contains the capture, investigation, approval, and refund result | `payment.captured`, `payment.investigated`, `refund.approved`, and `refund.completed` are in `GET /api/activity`. The dashboard showed the refund result. The payment Activity list showed the capture, the PayPal refresh, and the approval. |
| 10 | A second refund stays `pending_approval` with no PayPal refund id, and support cannot approve it | Refund `fc0b01ee-e1d2-4d0d-b0b2-52044177b0bb` stayed `pending_approval` with an empty PayPal refund id. Support `POST /api/refunds/{id}/approve` returned `forbidden`. The support screen said "Support cannot send this refund." and did not show Approve and send. |
