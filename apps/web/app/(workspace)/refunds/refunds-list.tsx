"use client";

import { useEffect, useState } from "react";

import { Card } from "../../../components/card";
import { EmptyState } from "../../../components/empty-state";
import { ErrorBanner } from "../../../components/error-banner";
import { ApiError, listRefunds, type RefundRequest } from "../../../lib/api";
import { RefundChip } from "./refund-chip";

function formatMinor(amountMinor: number): string {
  return (amountMinor / 100).toFixed(2);
}

export function RefundsList() {
  const [refunds, setRefunds] = useState<RefundRequest[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    let cancelled = false;
    listRefunds()
      .then((rows) => {
        if (!cancelled) {
          setRefunds(rows);
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(caught instanceof ApiError ? caught : new ApiError("unknown", "The request could not be completed."));
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <h1 className="text-title-page text-ink">Refunds</h1>
      <p className="mt-1 text-[15px] text-muted">A refund is not sent until the owner approves it.</p>
      {error ? (
        <div className="mt-6">
          <ErrorBanner code={error.code} message={error.message} />
        </div>
      ) : null}
      <Card className="mt-6">
        {refunds === null && error === null ? (
          <p role="status" className="px-4 py-6 text-sm text-muted">
            Loading refunds
          </p>
        ) : null}
        {refunds && refunds.length === 0 ? (
          <EmptyState title="No refund is waiting." description="A prepared refund will show its payment reference, amount, currency, and reason here." />
        ) : null}
        {refunds && refunds.length > 0 ? (
          <>
            <div className="hidden md:block">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-hairline text-metadata-caps font-semibold uppercase text-muted">
                    <th className="px-4 py-3 font-semibold">Payment reference</th>
                    <th className="px-4 py-3 text-right font-semibold">Amount</th>
                    <th className="px-4 py-3 font-semibold">Currency</th>
                    <th className="px-4 py-3 font-semibold">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {refunds.map((refund) => (
                    <tr key={refund.id} className="border-b border-hairline last:border-b-0">
                      <td className="px-4 py-3 text-sm text-ink">
                        <a href={`/refunds/${refund.id}`} className="break-all text-action focus-ring">
                          {refund.capture_id}
                        </a>
                      </td>
                      <td className="px-4 py-3 text-right text-sm tabular-nums text-ink">{formatMinor(refund.amount_minor)}</td>
                      <td className="px-4 py-3 text-sm text-ink">{refund.currency}</td>
                      <td className="px-4 py-3">
                        <RefundChip status={refund.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex flex-col divide-y divide-hairline md:hidden">
              {refunds.map((refund) => (
                <a key={refund.id} href={`/refunds/${refund.id}`} className="grid grid-cols-1 gap-2 p-4 focus-ring">
                  <div className="flex items-start justify-between gap-3">
                    <p className="break-all text-sm font-medium text-ink">{refund.capture_id}</p>
                    <RefundChip status={refund.status} />
                  </div>
                  <p className="text-sm tabular-nums text-ink">
                    {formatMinor(refund.amount_minor)} {refund.currency}
                  </p>
                </a>
              ))}
            </div>
          </>
        ) : null}
      </Card>
    </>
  );
}
