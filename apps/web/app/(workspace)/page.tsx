"use client";

import { useEffect, useState } from "react";

import { Card } from "../../components/card";
import { ErrorBanner } from "../../components/error-banner";
import { StatusChip } from "../../components/status-chip";
import { ApiError, listActivity, listPayments, listRefunds, type ActivityEvent, type PaymentListItem, type RefundRequest } from "../../lib/api";

const CLOSED = new Set(["completed", "failed", "refunded", "partially_refunded"]);

function formatMinor(amountMinor: number): string {
  return (amountMinor / 100).toFixed(2);
}

function formatWhen(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function isTodayUtc(value: string): boolean {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return false;
  }
  const now = new Date();
  return (
    parsed.getUTCFullYear() === now.getUTCFullYear() &&
    parsed.getUTCMonth() === now.getUTCMonth() &&
    parsed.getUTCDate() === now.getUTCDate()
  );
}

function paypalReference(payment: PaymentListItem): string {
  return payment.paypal_capture_id ?? payment.paypal_order_id ?? "No PayPal reference yet";
}

function CountStrip({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <div className="p-4">
        <p className="text-metadata-caps font-semibold uppercase text-muted">{label}</p>
        <p className="mt-2 text-title-section tabular-nums text-ink">{value}</p>
      </div>
    </Card>
  );
}

export default function DashboardPage() {
  const [payments, setPayments] = useState<PaymentListItem[] | null>(null);
  const [refunds, setRefunds] = useState<RefundRequest[] | null>(null);
  const [events, setEvents] = useState<ActivityEvent[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    let cancelled = false;
    listPayments()
      .then((rows) => {
        if (!cancelled) {
          setPayments(rows);
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(caught instanceof ApiError ? caught : new ApiError("unknown", "Payments could not be loaded."));
        }
      });
    listRefunds()
      .then((rows) => {
        if (!cancelled) {
          setRefunds(rows);
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(caught instanceof ApiError ? caught : new ApiError("unknown", "Refunds could not be loaded."));
        }
      });
    listActivity()
      .then((rows) => {
        if (!cancelled) {
          setEvents(rows);
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(caught instanceof ApiError ? caught : new ApiError("unknown", "Activity could not be loaded."));
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const rows = payments ?? [];
  const openPayments = rows.filter((payment) => !CLOSED.has(payment.status)).length;
  const awaitingCustomer = rows.filter((payment) => payment.status === "awaiting_payer").length;
  const confirmedMinor = rows
    .filter((payment) => payment.status === "completed" && payment.confirmation === "confirmed" && isTodayUtc(payment.updated_at))
    .reduce((sum, payment) => sum + payment.amount_minor, 0);
  const waiting = rows.filter((payment) => payment.status === "needs_checking");
  const refundsToReview = (refunds ?? []).filter((refund) => refund.status === "pending_approval");

  return (
    <>
      <h1 className="text-title-page text-ink">Dashboard</h1>
      <p className="mt-1 text-[15px] text-muted">PayPal’s response is the source of a confirmed result.</p>

      {payments === null && error === null ? (
        <p role="status" className="mt-6 text-sm text-muted">
          Loading payments
        </p>
      ) : null}
      {error ? (
        <div className="mt-6">
          <ErrorBanner code={error.code} message={error.message} />
        </div>
      ) : null}

      {payments && refunds ? (
        <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-4">
          <CountStrip label="Open payments" value={String(openPayments)} />
          <CountStrip label="Awaiting customer" value={String(awaitingCustomer)} />
          <CountStrip label="Refunds to review" value={String(refundsToReview.length)} />
          <CountStrip label="Confirmed today" value={`$${formatMinor(confirmedMinor)}`} />
        </div>
      ) : null}

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <Card>
          <div className="p-4 sm:p-6">
            <h2 className="text-title-section text-ink">Waiting on you</h2>
            {payments === null || refunds === null ? null : waiting.length === 0 && refundsToReview.length === 0 ? (
              <p role="status" className="mt-4 text-sm text-muted">
                No test payment is waiting.
              </p>
            ) : (
              <div className="mt-4 flex flex-col divide-y divide-hairline">
                {waiting.map((payment) => (
                  <a key={payment.id} href={`/payments/${payment.id}`} className="grid grid-cols-1 gap-2 py-3 focus-ring">
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-sm tabular-nums text-ink">
                        {formatMinor(payment.amount_minor)} {payment.currency}
                      </p>
                      <StatusChip status={payment.status} confirmation={payment.confirmation} />
                    </div>
                    <p className="break-all font-mono text-sm tabular-nums text-muted">{paypalReference(payment)}</p>
                    <p className="text-sm tabular-nums text-muted">{formatWhen(payment.updated_at)}</p>
                  </a>
                ))}
                {refundsToReview.map((refund) => (
                  <a key={refund.id} href={`/refunds/${refund.id}`} className="grid grid-cols-1 gap-2 py-3 focus-ring">
                    <p className="text-sm tabular-nums text-ink">
                      {formatMinor(refund.amount_minor)} {refund.currency}
                    </p>
                    <p className="break-all font-mono text-sm tabular-nums text-muted">{refund.capture_id}</p>
                    <p className="text-sm text-muted">Refund waiting for approval</p>
                  </a>
                ))}
              </div>
            )}
          </div>
        </Card>
        <Card>
          <div className="p-4 sm:p-6">
            <h2 className="text-title-section text-ink">Latest from PayPal</h2>
            {events === null ? null : events.length === 0 ? (
              <p className="mt-4 text-sm text-muted">No PayPal events yet.</p>
            ) : (
              <ul className="mt-4 flex flex-col gap-3">
                {events.map((event) => (
                  <li key={`${event.created_at}-${event.action}-${event.summary}`} className="text-sm text-ink">
                    <p className="text-muted">{formatWhen(event.created_at)}</p>
                    <p>{event.summary}</p>
                    <p className="break-all font-mono tabular-nums text-muted">{event.paypal_reference ?? "No PayPal reference yet"}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Card>
      </div>
    </>
  );
}
