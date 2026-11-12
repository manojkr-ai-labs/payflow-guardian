"use client";

import { FormEvent, useEffect, useState } from "react";

import { Button } from "../../../../components/button";
import { Card } from "../../../../components/card";
import { ErrorBanner } from "../../../../components/error-banner";
import {
  ApiError,
  approveRefund,
  currentUser,
  getPayment,
  getRefund,
  rejectRefund,
  type MerchantUser,
  type RefundRequest,
} from "../../../../lib/api";
import { RefundChip } from "../refund-chip";

function formatMinor(amountMinor: number): string {
  return (amountMinor / 100).toFixed(2);
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-metadata-caps font-semibold uppercase text-muted">{label}</dt>
      <dd className="mt-1 break-all text-sm text-ink">{value}</dd>
    </div>
  );
}

export function RefundReview({ refundId }: { refundId: string }) {
  const [refund, setRefund] = useState<RefundRequest | null>(null);
  const [originalAmount, setOriginalAmount] = useState<string | null>(null);
  const [user, setUser] = useState<MerchantUser | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getRefund(refundId)
      .then((result) => {
        if (cancelled) {
          return;
        }
        setRefund(result);
        getPayment(result.payment_id)
          .then((payment) => {
            if (!cancelled) {
              setOriginalAmount(`${payment.display_amount} ${payment.currency}`);
            }
          })
          .catch(() => {
            if (!cancelled) {
              setOriginalAmount("Not available");
            }
          });
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(caught instanceof ApiError ? caught : new ApiError("unknown", "The request could not be completed."));
        }
      });
    currentUser()
      .then((result) => {
        if (!cancelled) {
          setUser(result);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setUser(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [refundId]);

  async function onApprove(event: FormEvent) {
    event.preventDefault();
    if (!refund || busy) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      setRefund(await approveRefund(refund.id));
    } catch (caught: unknown) {
      const next = caught instanceof ApiError ? caught : new ApiError("unknown", "The request could not be completed.");
      setError(next);
      if (next.refund) {
        setRefund(next.refund);
      }
    } finally {
      setBusy(false);
    }
  }

  async function onReject() {
    if (!refund || busy) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      setRefund(await rejectRefund(refund.id));
    } catch (caught: unknown) {
      const next = caught instanceof ApiError ? caught : new ApiError("unknown", "The request could not be completed.");
      setError(next);
      if (next.refund) {
        setRefund(next.refund);
      }
    } finally {
      setBusy(false);
    }
  }

  const owner = user?.role === "owner";
  const waiting = refund?.status === "pending_approval";
  const preparedBy = refund && user && refund.prepared_by === user.id ? user.display_name : refund?.prepared_by;

  return (
    <div className="mx-auto w-full max-w-[760px]">
      <a href="/refunds" className="text-sm font-medium text-action focus-ring">
        Back to refunds
      </a>
      {refund === null && error === null ? (
        <p role="status" className="mt-6 text-sm text-muted">
          Loading refund
        </p>
      ) : null}
      {error ? (
        <div className="mt-6">
          <ErrorBanner code={error.code} message={error.code === "approval_stale" ? undefined : error.message} />
        </div>
      ) : null}
      {refund ? (
        <Card className="mt-6">
          <div className="flex flex-col gap-4 p-4 sm:p-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <h1 className="text-title-page text-ink">Refund draft</h1>
              <RefundChip status={refund.status} />
            </div>
            <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Payment reference" value={refund.capture_id} />
              <Field label="Original amount" value={originalAmount ?? "Loading payment"} />
              <Field label="Refund amount" value={formatMinor(refund.amount_minor)} />
              <Field label="Currency" value={refund.currency} />
              <Field label="Reason" value={refund.reason} />
              <Field label="Prepared by" value={preparedBy ?? refund.prepared_by} />
            </dl>
            {refund.paypal_refund_id ? <Field label="PayPal refund" value={refund.paypal_refund_id} /> : null}
            {refund.paypal_status ? <Field label="PayPal status" value={refund.paypal_status} /> : null}
            <p className="text-sm text-ink">Approving sends the refund to PayPal Sandbox.</p>
            {owner && waiting ? (
              <form className="flex flex-col gap-3 sm:flex-row" onSubmit={(event) => void onApprove(event)}>
                <Button variant="quiet" type="button" disabled={busy} onClick={() => void onReject()}>
                  Reject
                </Button>
                <Button type="submit" disabled={busy}>
                  Approve and send
                </Button>
              </form>
            ) : null}
            {user && !owner ? <p className="text-sm text-ink">Support cannot send this refund.</p> : null}
          </div>
        </Card>
      ) : null}
    </div>
  );
}
