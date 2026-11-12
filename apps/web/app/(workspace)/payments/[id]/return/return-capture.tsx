"use client";

import { useEffect, useRef, useState } from "react";

import { ApiError, capturePayment, type CreatedPayment } from "../../../../../lib/api";
import { PaymentOutcome, outcomeNote } from "../payment-outcome";

export function ReturnCapture({ paymentId }: { paymentId: string }) {
  const [payment, setPayment] = useState<CreatedPayment | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [pending, setPending] = useState(true);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) {
      return;
    }
    started.current = true;
    capturePayment(paymentId)
      .then((result) => {
        setPayment(result);
      })
      .catch((caught: unknown) => {
        const apiError = caught instanceof ApiError ? caught : new ApiError("unknown", "The payment could not be captured.");
        setError(apiError);
        if (apiError.payment) {
          setPayment(apiError.payment);
        }
      })
      .finally(() => {
        setPending(false);
      });
  }, [paymentId]);

  return (
    <PaymentOutcome
      heading="Payment return"
      note={pending ? null : outcomeNote(payment, false)}
      payment={payment}
      error={error}
      pending={pending}
      showCaptureButton
    />
  );
}
