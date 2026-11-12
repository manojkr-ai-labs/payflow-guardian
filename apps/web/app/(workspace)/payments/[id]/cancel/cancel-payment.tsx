"use client";

import { useEffect, useRef, useState } from "react";

import { ApiError, getPayment, type CreatedPayment } from "../../../../../lib/api";
import { PaymentOutcome, outcomeNote } from "../payment-outcome";

export function CancelPayment({ paymentId }: { paymentId: string }) {
  const [payment, setPayment] = useState<CreatedPayment | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [pending, setPending] = useState(true);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) {
      return;
    }
    started.current = true;
    getPayment(paymentId)
      .then((result) => {
        setPayment(result);
      })
      .catch((caught: unknown) => {
        const apiError = caught instanceof ApiError ? caught : new ApiError("unknown", "The payment could not be loaded.");
        setError(apiError);
      })
      .finally(() => {
        setPending(false);
      });
  }, [paymentId]);

  return (
    <PaymentOutcome
      heading="Payment cancelled"
      note={pending || !payment ? null : outcomeNote(payment, true)}
      payment={payment}
      error={error}
      pending={pending}
      showCaptureButton={false}
    />
  );
}
