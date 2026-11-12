"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "../../../../components/button";
import { Card } from "../../../../components/card";
import { ErrorBanner } from "../../../../components/error-banner";
import { PayPalPayLink } from "../../../../components/paypal-pay-link";
import { StatusChip } from "../../../../components/status-chip";
import { TextField } from "../../../../components/text-field";
import {
  ApiError,
  getPayment,
  investigatePayment,
  listActivity,
  prepareRefund,
  type ActivityEvent,
  type CreatedPayment,
  type FactSheet,
} from "../../../../lib/api";

function formatWhen(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-metadata-caps font-semibold uppercase text-muted">{label}</dt>
      <dd className="mt-1 break-all text-sm tabular-nums text-ink">{value}</dd>
    </div>
  );
}

function FactSheetList({ sheet }: { sheet: FactSheet }) {
  return (
    <dl className="grid grid-cols-1 gap-4 md:grid-cols-2">
      <Field label="PayPal status" value={sheet.paypal_status ?? "Not returned"} />
      <Field label="Local status" value={sheet.local_status} />
      <Field label="Confirmation" value={sheet.confirmation} />
      <Field label="Amount" value={`${sheet.amount} ${sheet.currency}`} />
      <Field label="PayPal order" value={sheet.paypal_order_id ?? "No PayPal order yet"} />
      <Field label="PayPal capture" value={sheet.paypal_capture_id ?? "No capture id yet"} />
      <Field label="Checked" value={sheet.checked_at ? formatWhen(sheet.checked_at) : "No successful check yet"} />
      <Field label="Missing" value={sheet.missing.length > 0 ? sheet.missing.join(", ") : "None"} />
    </dl>
  );
}

function ActivityList({ events }: { events: ActivityEvent[] }) {
  if (events.length === 0) {
    return <p className="mt-4 text-sm text-muted">No activity yet.</p>;
  }
  return (
    <ol className="mt-4 flex flex-col gap-3">
      {events.map((event, index) => (
        <li key={`${event.created_at}-${event.action}-${event.summary}`} className="flex gap-3">
          <span
            className="mt-1.5 h-2 w-2 shrink-0 rounded-full"
            style={{ backgroundColor: index === 0 ? "#0070E0" : "#c5ced6" }}
          />
          <div>
            <p className="text-sm text-muted">{formatWhen(event.created_at)}</p>
            <p className="text-sm text-ink">{event.summary}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}

export function PaymentDetail({ paymentId }: { paymentId: string }) {
  const [payment, setPayment] = useState<CreatedPayment | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshNote, setRefreshNote] = useState<string | null>(null);
  const [activity, setActivity] = useState<ActivityEvent[] | null>(null);
  const [reason, setReason] = useState("");
  const [preparing, setPreparing] = useState(false);
  const [prepareError, setPrepareError] = useState<ApiError | null>(null);
  const router = useRouter();

  async function onRefresh() {
    if (!payment) {
      return;
    }
    setRefreshing(true);
    setRefreshNote(null);
    try {
      const next = await investigatePayment(payment.id);
      setPayment(next);
      if (next.fact_sheet && next.fact_sheet.missing.length > 0) {
        setRefreshNote("The check did not complete.");
      }
    } catch {
      setRefreshNote("The check did not complete.");
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    getPayment(paymentId)
      .then((result) => {
        if (!cancelled) {
          setPayment(result);
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(caught instanceof ApiError ? caught : new ApiError("unknown", "The payment could not be loaded."));
        }
      });
    listActivity()
      .then((events) => {
        if (!cancelled) {
          setActivity(events);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setActivity([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [paymentId]);

  return (
    <div className="flex flex-col">
      <a href="/payments" className="text-sm font-medium text-action focus-ring">
        Back to payments
      </a>
      {payment === null && error === null ? (
        <p role="status" className="mt-6 text-sm text-muted">
          Loading payment
        </p>
      ) : null}
      {error ? (
        <div className="mt-6">
          <ErrorBanner code={error.code} message={error.message} />
        </div>
      ) : null}
      {payment ? (
        <Card className="mt-6">
          <div className="flex flex-col gap-4 p-4 sm:p-6">
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <h1 className="text-title-page tabular-nums text-ink">
                {payment.display_amount} {payment.currency}
              </h1>
              <StatusChip status={payment.status} confirmation={payment.confirmation} />
            </div>
            {payment.fact_sheet?.mismatch ? (
              <p className="text-sm text-pending">The saved payment and the latest PayPal data differ and need a check.</p>
            ) : null}
            {payment.confirmation !== "confirmed" ? (
              <p className="text-sm text-pending">This payment needs a check.</p>
            ) : null}
            {refreshNote ? <p className="text-sm text-pending">{refreshNote}</p> : null}
            {payment.paypal_capture_id === null && (payment.status === "awaiting_payer" || payment.status === "created") ? (
              <PayPalPayLink approveUrl={payment.approve_url} paypalOrderId={payment.paypal_order_id} />
            ) : null}
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <Button variant="secondary" className="w-full md:w-auto" disabled={refreshing} onClick={() => void onRefresh()}>
                Refresh from PayPal
              </Button>
            </div>
            <div>
              <h2 className="text-title-section text-ink">What PayPal returned</h2>
              <div className="mt-4">
                {payment.fact_sheet ? (
                  <FactSheetList sheet={payment.fact_sheet} />
                ) : (
                  <p className="text-sm text-muted">No PayPal read yet.</p>
                )}
              </div>
            </div>
            <dl className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <Field label="Status" value={payment.status} />
              <Field label="PayPal order" value={payment.paypal_order_id ?? "No PayPal order yet"} />
              <Field label="PayPal capture" value={payment.paypal_capture_id ?? "No capture id yet"} />
              <Field label="Amount" value={payment.display_amount} />
              <Field label="Currency" value={payment.currency} />
              <Field label="Updated" value={formatWhen(payment.updated_at)} />
            </dl>
            <div>
              <h2 className="text-title-section text-ink">Activity</h2>
              {activity === null ? (
                <p className="mt-4 text-sm text-muted">Loading activity</p>
              ) : (
                <ActivityList
                  events={activity.filter(
                    (event) =>
                      event.paypal_reference !== null &&
                      (event.paypal_reference === payment.paypal_order_id || event.paypal_reference === payment.paypal_capture_id),
                  )}
                />
              )}
            </div>
            <div>
              {payment.status === "completed" && payment.confirmation === "confirmed" ? (
                <form
                  className="flex flex-col gap-3"
                  onSubmit={(event) => {
                    event.preventDefault();
                    if (preparing || reason.trim().length === 0) {
                      return;
                    }
                    setPreparing(true);
                    setPrepareError(null);
                    prepareRefund({
                      payment_id: payment.id,
                      amount_minor: payment.amount_minor,
                      currency: payment.currency,
                      reason: reason.trim(),
                    })
                      .then((refund) => {
                        router.push(`/refunds/${refund.id}`);
                      })
                      .catch((caught: unknown) => {
                        setPrepareError(
                          caught instanceof ApiError ? caught : new ApiError("unknown", "The request could not be completed."),
                        );
                        setPreparing(false);
                      });
                  }}
                >
                  <p className="text-sm tabular-nums text-ink">
                    Refund amount {payment.display_amount} {payment.currency}
                  </p>
                  <TextField
                    id="refund-reason"
                    label="Reason"
                    value={reason}
                    onChange={(event) => setReason(event.target.value)}
                    disabled={preparing}
                    autoComplete="off"
                  />
                  {prepareError ? <ErrorBanner code={prepareError.code} message={prepareError.message} /> : null}
                  <Button type="submit" className="w-full md:w-auto" disabled={preparing || reason.trim().length === 0}>
                    Prepare refund
                  </Button>
                </form>
              ) : (
                <>
                  <Button disabled className="w-full md:w-auto">
                    Prepare refund
                  </Button>
                  <p className="mt-2 text-sm text-muted">Available after PayPal marks the payment completed.</p>
                </>
              )}
            </div>
            <a href={`/assistant?payment=${payment.id}`} className="text-sm font-medium text-action focus-ring">
              Ask the assistant
            </a>
          </div>
        </Card>
      ) : null}
    </div>
  );
}
