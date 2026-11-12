"use client";

import { FormEvent, useEffect, useId, useRef, useState } from "react";

import { Button } from "../../../components/button";
import { ErrorBanner } from "../../../components/error-banner";
import { Modal } from "../../../components/modal";
import { PayPalPayLink } from "../../../components/paypal-pay-link";
import { ApiError, apiRequest, type CreatedPayment, type TestOrder } from "../../../lib/api";

export function NewTestOrderModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (payment: CreatedPayment, error: ApiError | null) => void;
}) {
  const descriptionId = useId();
  const [orders, setOrders] = useState<TestOrder[] | null>(null);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [selected, setSelected] = useState("");
  const [fieldError, setFieldError] = useState("");
  const [formError, setFormError] = useState<ApiError | null>(null);
  const [pending, setPending] = useState(false);
  const [created, setCreated] = useState<CreatedPayment | null>(null);
  const keyForCode = useRef<{ code: string; key: string } | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiRequest<{ test_orders: TestOrder[] }>("/api/catalog/test-orders")
      .then((body) => {
        if (cancelled) {
          return;
        }
        setOrders(body.test_orders);
        setSelected(body.test_orders[0]?.code ?? "");
      })
      .catch((caught: unknown) => {
        if (cancelled) {
          return;
        }
        setLoadError(caught instanceof ApiError ? caught : new ApiError("unknown", "Test orders could not be loaded."));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) {
      setFieldError("Select a test order.");
      return;
    }
    setFieldError("");
    setFormError(null);
    if (!keyForCode.current || keyForCode.current.code !== selected) {
      keyForCode.current = { code: selected, key: crypto.randomUUID() };
    }
    const idempotencyKey = keyForCode.current.key;
    setPending(true);
    try {
      const body = await apiRequest<{ payment: CreatedPayment }>("/api/payments", {
        method: "POST",
        body: JSON.stringify({ test_order_code: selected }),
        headers: { "Idempotency-Key": idempotencyKey },
      });
      keyForCode.current = null;
      setCreated(body.payment);
      setPending(false);
      onCreated(body.payment, null);
    } catch (caught) {
      const error = caught instanceof ApiError ? caught : new ApiError("unknown", "The test order could not be created.");
      if (caught instanceof ApiError) {
        keyForCode.current = null;
      }
      if (error.payment) {
        if (error.payment.approve_url) {
          setCreated(error.payment);
          setPending(false);
        }
        onCreated(error.payment, error);
        return;
      }
      setFormError(error);
      setPending(false);
    }
  }

  if (created) {
    return (
      <Modal title="Test order created" onClose={onClose}>
        <p className="text-sm font-medium text-ink">
          {created.test_order_code}
          <span className="font-normal text-muted"> · {created.description}</span>
        </p>
        <p className="mt-2 text-title-section tabular-nums text-ink">
          {created.display_amount} {created.currency}
        </p>
        <PayPalPayLink approveUrl={created.approve_url} paypalOrderId={created.paypal_order_id} />
        <div className="mt-5 flex justify-end">
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
        </div>
      </Modal>
    );
  }

  return (
    <Modal title="New test order" onClose={onClose} dismissable={!pending}>
      <form onSubmit={onSubmit} noValidate>
        <fieldset disabled={pending || orders === null}>
          <legend className="text-sm font-medium text-ink">Test orders</legend>
          <p id={descriptionId} className="mt-1 text-sm leading-5 text-muted">
            These are test orders. Sandbox does not move live money.
          </p>
          {loadError ? (
            <div className="mt-4">
              <ErrorBanner code={loadError.code} message={loadError.message} />
            </div>
          ) : null}
          {orders === null && !loadError ? (
            <p role="status" className="mt-4 text-sm text-muted">
              Loading test orders.
            </p>
          ) : null}
          {orders ? (
            <div className="mt-4 space-y-2" role="radiogroup" aria-describedby={descriptionId}>
              {orders.map((order) => {
                const id = `test-order-${order.code}`;
                const checked = selected === order.code;
                return (
                  <label
                    key={order.code}
                    htmlFor={id}
                    className={`flex cursor-pointer items-start gap-3 rounded-card border px-3 py-3 ${
                      checked ? "border-action" : "border-hairline"
                    }`}
                  >
                    <input
                      id={id}
                      type="radio"
                      name="test_order_code"
                      value={order.code}
                      checked={checked}
                      onChange={() => {
                        setSelected(order.code);
                        setFieldError("");
                      }}
                      className="mt-1 h-[18px] w-[18px] accent-action"
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-medium text-ink">{order.code}</span>
                      <span className="mt-0.5 block text-sm text-muted">{order.description}</span>
                    </span>
                    <span className="tabular-nums text-sm font-medium text-ink">
                      {order.display_amount} {order.currency}
                    </span>
                  </label>
                );
              })}
            </div>
          ) : null}
          {fieldError ? <p className="mt-2 text-xs text-failed">{fieldError}</p> : null}
        </fieldset>
        {formError ? (
          <div className="mt-4">
            <ErrorBanner code={formError.code} message={formError.message} />
          </div>
        ) : null}
        <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="secondary" onClick={onClose} disabled={pending}>
            Cancel
          </Button>
          <Button type="submit" disabled={pending || !orders || orders.length === 0} className="sm:min-w-40">
            Create test order
          </Button>
        </div>
      </form>
    </Modal>
  );
}
