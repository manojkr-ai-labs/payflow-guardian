"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

import { Button } from "../../../components/button";
import { Card } from "../../../components/card";
import { EmptyState } from "../../../components/empty-state";
import { ErrorBanner } from "../../../components/error-banner";
import { Icon } from "../../../components/icon";
import { PayPalPayLink } from "../../../components/paypal-pay-link";
import { StatusChip } from "../../../components/status-chip";
import { ApiError, listPayments, type CreatedPayment, type PaymentListItem } from "../../../lib/api";
import { NewTestOrderModal } from "./new-test-order-modal";

const FILTERS = [
  { label: "All", status: "" },
  { label: "Completed", status: "completed" },
  { label: "Pending", status: "pending" },
  { label: "Needs checking", status: "needs_checking" },
  { label: "Failed", status: "failed" },
  { label: "Refunded", status: "refunded" },
];

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

function paypalReference(payment: PaymentListItem): string {
  return payment.paypal_capture_id ?? payment.paypal_order_id ?? "No PayPal reference yet";
}

function PaymentFields({ payment }: { payment: PaymentListItem }) {
  return (
    <>
      <div>
        <p className="text-metadata-caps font-semibold uppercase text-muted">Created</p>
        <p className="mt-1 text-sm tabular-nums text-ink">{formatWhen(payment.created_at)}</p>
      </div>
      <div>
        <p className="text-metadata-caps font-semibold uppercase text-muted">Catalog</p>
        <p className="mt-1 text-sm text-ink">{payment.test_order_code}</p>
      </div>
      <div>
        <p className="text-metadata-caps font-semibold uppercase text-muted">Amount</p>
        <p className="mt-1 text-sm tabular-nums text-ink">
          {formatMinor(payment.amount_minor)} {payment.currency}
        </p>
      </div>
      <div>
        <p className="text-metadata-caps font-semibold uppercase text-muted">PayPal reference</p>
        <p className="mt-1 break-all font-mono text-sm tabular-nums text-ink">{paypalReference(payment)}</p>
      </div>
    </>
  );
}

export function PaymentsWorkspace() {
  const [open, setOpen] = useState(false);
  const [payment, setPayment] = useState<CreatedPayment | null>(null);
  const [resultError, setResultError] = useState<ApiError | null>(null);
  const [payments, setPayments] = useState<PaymentListItem[] | null>(null);
  const [listError, setListError] = useState<ApiError | null>(null);
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const filtered = query.length > 0 || status.length > 0;

  const loadPayments = useCallback(() => {
    return listPayments({ q: query, status })
      .then((rows) => {
        setPayments(rows);
        setListError(null);
      })
      .catch((caught: unknown) => {
        setListError(caught instanceof ApiError ? caught : new ApiError("unknown", "Payments could not be loaded."));
      });
  }, [query, status]);

  function onSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setQuery(draft.trim());
  }

  useEffect(() => {
    void loadPayments();
  }, [loadPayments]);

  return (
    <>
      <div className="flex flex-col">
        <h1 className="text-title-page text-ink">Payments</h1>
        <p className="mt-1 text-[15px] text-muted">Orders created in this workspace and completed through PayPal Sandbox.</p>
      </div>

      <div className="mt-6 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="order-2 flex flex-col gap-3 md:flex-row md:items-center lg:order-1">
          <form className="relative w-full md:w-80" onSubmit={onSearch}>
            <label htmlFor="payment-search" className="sr-only">
              Search by PayPal reference
            </label>
            <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-muted">
              <Icon name="search" size={16} />
            </span>
            <input
              id="payment-search"
              type="search"
              value={draft}
              placeholder="PayPal reference"
              autoComplete="off"
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  setQuery(draft.trim());
                }
              }}
              className="h-10 w-full rounded-control border border-hairline bg-surface pl-9 pr-3.5 text-sm text-ink placeholder:text-muted focus:border-action focus-ring"
            />
          </form>
          <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Payment status">
            {FILTERS.map((filter) => {
              const active = status === filter.status;
              return (
                <button
                  key={filter.label}
                  type="button"
                  aria-pressed={active}
                  onClick={() => setStatus(filter.status)}
                  className={`inline-flex h-10 items-center rounded-control border bg-surface px-3 text-xs font-medium focus-ring ${
                    active ? "border-[#0070E0] text-ink" : "border-hairline text-muted"
                  }`}
                >
                  {filter.label}
                </button>
              );
            })}
          </div>
        </div>
        <div className="order-1 lg:order-2">
          <Button className="w-full gap-1.5 md:w-auto" onClick={() => setOpen(true)}>
            <Icon name="add" size={16} />
            <span>New test order</span>
          </Button>
        </div>
      </div>

      {resultError ? (
        <div className="mt-6">
          <ErrorBanner code={resultError.code} message={resultError.message} />
        </div>
      ) : null}

      {payment ? (
        <Card className="mt-6">
          <div className="flex flex-col gap-4 p-4 sm:p-6 md:flex-row md:items-start md:justify-between">
            <div className="min-w-0">
              <p className="text-metadata-caps font-semibold uppercase text-muted">Test order</p>
              <p className="mt-2 text-sm font-medium text-ink">
                {payment.test_order_code}
                <span className="font-normal text-muted"> · {payment.description}</span>
              </p>
              <p className="mt-2 text-title-section tabular-nums text-ink">
                {payment.display_amount} {payment.currency}
              </p>
              <p className="mt-4 text-metadata-caps font-semibold uppercase text-muted">PayPal reference</p>
              <p className="mt-1 break-all font-mono text-sm tabular-nums text-ink">
                {payment.paypal_order_id ?? "No PayPal reference yet"}
              </p>
              <PayPalPayLink approveUrl={payment.approve_url} paypalOrderId={payment.paypal_order_id} />
            </div>
            <StatusChip status={payment.status} confirmation={payment.confirmation} />
          </div>
        </Card>
      ) : null}

      {listError ? (
        <div className="mt-6">
          <ErrorBanner code={listError.code} message={listError.message} />
        </div>
      ) : null}

      <Card className="mt-6">
        {payments === null && !listError ? (
          <p role="status" className="px-4 py-6 text-sm text-muted">
            Loading payments
          </p>
        ) : null}
        {payments && payments.length === 0 && filtered ? (
          <p role="status" className="px-4 py-6 text-sm text-muted">
            No payments match this search.
          </p>
        ) : null}
        {payments && payments.length === 0 && !filtered ? (
          <EmptyState
            title="No payments yet"
            description="Create a test order to send a catalog amount to PayPal Sandbox."
            action={
              <Button className="gap-1.5" onClick={() => setOpen(true)}>
                <Icon name="add" size={16} />
                <span>New test order</span>
              </Button>
            }
          />
        ) : null}
        {payments && payments.length > 0 ? (
          <>
            <div className="hidden md:block">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-hairline text-metadata-caps font-semibold uppercase text-muted">
                    <th className="px-4 py-3 font-semibold">Created</th>
                    <th className="px-4 py-3 font-semibold">Catalog</th>
                    <th className="px-4 py-3 text-right font-semibold">Amount</th>
                    <th className="px-4 py-3 font-semibold">Currency</th>
                    <th className="px-4 py-3 font-semibold">Status</th>
                    <th className="px-4 py-3 font-semibold">PayPal reference</th>
                  </tr>
                </thead>
                <tbody>
                  {payments.map((row) => (
                    <tr key={row.id} className="border-b border-hairline last:border-b-0">
                      <td className="px-4 py-3 text-sm tabular-nums text-ink">{formatWhen(row.created_at)}</td>
                      <td className="px-4 py-3 text-sm text-ink">
                        <a href={`/payments/${row.id}`} className="text-action focus-ring">
                          {row.test_order_code}
                        </a>
                      </td>
                      <td className="px-4 py-3 text-right text-sm tabular-nums text-ink">{formatMinor(row.amount_minor)}</td>
                      <td className="px-4 py-3 text-sm text-ink">{row.currency}</td>
                      <td className="px-4 py-3">
                        <StatusChip status={row.status} confirmation={row.confirmation} />
                      </td>
                      <td className="px-4 py-3 break-all font-mono text-sm tabular-nums text-ink">{paypalReference(row)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex flex-col divide-y divide-hairline md:hidden">
              {payments.map((row) => (
                <a key={row.id} href={`/payments/${row.id}`} className="grid grid-cols-1 gap-3 p-4 focus-ring">
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-sm font-medium text-ink">{row.test_order_code}</p>
                    <StatusChip status={row.status} confirmation={row.confirmation} />
                  </div>
                  <PaymentFields payment={row} />
                </a>
              ))}
            </div>
          </>
        ) : null}
      </Card>

      {open ? (
        <NewTestOrderModal
          onClose={() => setOpen(false)}
          onCreated={(created, error) => {
            setPayment(created);
            setResultError(error);
            if (!created.approve_url) {
              setOpen(false);
            }
            void loadPayments();
          }}
        />
      ) : null}
    </>
  );
}
