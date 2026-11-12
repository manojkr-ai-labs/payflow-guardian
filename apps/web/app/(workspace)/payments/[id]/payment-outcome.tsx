"use client";

import { Button } from "../../../../components/button";
import { Card } from "../../../../components/card";
import { ErrorBanner } from "../../../../components/error-banner";
import { StatusChip } from "../../../../components/status-chip";
import type { ApiError, CreatedPayment } from "../../../../lib/api";

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-metadata-caps font-semibold uppercase text-muted">{label}</dt>
      <dd className="mt-1 break-all font-mono text-sm tabular-nums text-ink">{value}</dd>
    </div>
  );
}

export function PaymentOutcome({
  heading,
  note,
  payment,
  error,
  pending,
  showCaptureButton,
}: {
  heading: string;
  note: string | null;
  payment: CreatedPayment | null;
  error: ApiError | null;
  pending: boolean;
  showCaptureButton: boolean;
}) {
  const banner = error?.code === "paypal_failed" || (error && !payment) ? error : null;

  return (
    <div className="flex flex-col">
      <h1 className="text-title-page text-ink">{heading}</h1>
      <p className="mt-1 text-[15px] text-muted">Sandbox does not move live money.</p>

      {pending ? (
        <p role="status" className="mt-6 text-sm text-muted">
          Loading payment.
        </p>
      ) : null}

      {showCaptureButton ? (
        <div className="mt-6">
          <Button disabled={pending || payment !== null || error !== null} className="w-full md:w-auto">
            Capture payment
          </Button>
        </div>
      ) : null}

      {banner ? (
        <div className="mt-6">
          <ErrorBanner code={banner.code} message={banner.message} />
        </div>
      ) : null}

      {payment ? (
        <Card className="mt-6">
          <div className="flex flex-col gap-4 p-4 sm:p-6">
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <p className="text-title-section tabular-nums text-ink">
                {payment.display_amount} {payment.currency}
              </p>
              <StatusChip status={payment.status} confirmation={payment.confirmation} />
            </div>
            {note ? <p className="text-sm text-pending">{note}</p> : null}
            <dl className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <Field label="Amount" value={payment.display_amount} />
              <Field label="Currency" value={payment.currency} />
              <Field label="PayPal order" value={payment.paypal_order_id ?? "No PayPal order yet"} />
              <Field label="PayPal capture" value={payment.paypal_capture_id ?? "No capture id yet"} />
            </dl>
          </div>
        </Card>
      ) : null}
    </div>
  );
}

export function outcomeNote(payment: CreatedPayment | null, cancelled: boolean): string | null {
  if (cancelled) {
    return "The payment was not approved.";
  }
  if (payment && (payment.status === "needs_checking" || payment.confirmation !== "confirmed")) {
    return "This payment needs a check.";
  }
  return null;
}
