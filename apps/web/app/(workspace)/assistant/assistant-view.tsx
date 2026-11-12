"use client";

import { FormEvent, useState } from "react";
import { useSearchParams } from "next/navigation";

import { Button } from "../../../components/button";
import { Card } from "../../../components/card";
import { StatusChip } from "../../../components/status-chip";
import { TextField } from "../../../components/text-field";
import { sendAssistantMessage, type AssistantReply, type FactSheet } from "../../../lib/api";

type Turn = {
  id: string;
  message: string;
  answer: string | null;
  paypalRead: boolean;
  failed: boolean;
};

function paypalReference(sheet: FactSheet): string {
  return sheet.paypal_capture_id ?? sheet.paypal_order_id ?? "No PayPal reference yet";
}

function formatWhen(value: string | null | undefined): string {
  if (!value) {
    return "No successful check yet";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" });
}

function usedPayPalRead(reply: AssistantReply): boolean {
  return reply.next_step === "refresh_payment" || Boolean(reply.fact_sheet?.checked_at);
}

function suggestedLink(
  nextStep: string | null,
  sheet: FactSheet | null,
  refundId: string | null,
): { href: string; label: string } | null {
  if (!nextStep) {
    return null;
  }
  if (refundId) {
    return { href: `/refunds/${refundId}`, label: "Open refund" };
  }
  if (!sheet?.payment_id) {
    return null;
  }
  return { href: `/payments/${sheet.payment_id}`, label: "Open payment" };
}

function messageText(draft: string, paymentId: string | null): string {
  const text = draft.trim();
  if (!paymentId || text.includes(paymentId)) {
    return text;
  }
  return `${text}\nPayment ${paymentId}`;
}

export function AssistantView() {
  const searchParams = useSearchParams();
  const paymentId = searchParams.get("payment");
  const [conversationId] = useState(() => crypto.randomUUID());
  const [draft, setDraft] = useState(paymentId ? `Check payment ${paymentId}` : "");
  const [sending, setSending] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [sheet, setSheet] = useState<FactSheet | null>(null);
  const [confirmation, setConfirmation] = useState<string | null>(null);
  const [nextStep, setNextStep] = useState<string | null>(null);
  const [refundId, setRefundId] = useState<string | null>(null);

  const link = suggestedLink(nextStep, sheet, refundId);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = messageText(draft, paymentId);
    if (!message || sending) {
      return;
    }
    const id = crypto.randomUUID();
    setSending(true);
    setDraft("");
    setTurns((current) => [...current, { id, message, answer: null, paypalRead: false, failed: false }]);
    try {
      const reply = await sendAssistantMessage(message, conversationId);
      setTurns((current) =>
        current.map((turn) =>
          turn.id === id ? { ...turn, answer: reply.answer, paypalRead: usedPayPalRead(reply) } : turn,
        ),
      );
      setSheet(reply.fact_sheet);
      setConfirmation(reply.confirmation);
      setNextStep(reply.next_step);
      setRefundId(reply.refund_id ?? null);
    } catch {
      setTurns((current) =>
        current.map((turn) =>
          turn.id === id
            ? { ...turn, answer: "The explanation could not be completed.", failed: true }
            : turn,
        ),
      );
    } finally {
      setSending(false);
    }
  }

  return (
    <>
      <h1 className="text-title-page text-ink">Assistant</h1>
      <p className="mt-1 text-[15px] text-muted">Answers use PayPal’s response. If PayPal did not confirm it, the assistant says so.</p>
      <div className="mt-6 flex flex-col gap-6 md:flex-row md:items-start">
        <div className="w-full max-w-[720px] flex-1">
          <Card>
            <div className="flex flex-col gap-4 p-4 sm:p-6">
              {turns.length === 0 ? (
                <p className="text-sm text-muted">Send a message about a test payment.</p>
              ) : (
                <ol className="flex flex-col gap-4">
                  {turns.map((turn) => (
                    <li key={turn.id} className="flex flex-col gap-2">
                      <p className="text-sm text-ink">{turn.message}</p>
                      {turn.answer ? (
                        <p className={turn.failed ? "text-sm text-failed" : "text-sm text-ink"}>{turn.answer}</p>
                      ) : (
                        <p className="text-sm text-muted">Waiting for the answer</p>
                      )}
                      {turn.answer && !turn.failed ? (
                        <p className="text-xs text-muted">
                          {turn.paypalRead ? "A PayPal read was used." : "This answer did not use a PayPal read."}
                        </p>
                      ) : null}
                    </li>
                  ))}
                </ol>
              )}
              <form className="flex items-end gap-3" onSubmit={(event) => void onSubmit(event)}>
                <div className="min-w-0 flex-1">
                  <TextField
                    id="assistant-message"
                    label="Message"
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    disabled={sending}
                    autoComplete="off"
                  />
                </div>
                <Button type="submit" disabled={sending || draft.trim().length === 0}>
                  Send
                </Button>
              </form>
            </div>
          </Card>
        </div>
        <aside className="w-full max-w-[360px]">
          <Card>
            <div className="flex flex-col gap-4 p-4 sm:p-6">
              <h2 className="text-title-section text-ink">Payment</h2>
              {sheet ? (
                <>
                  <StatusChip status={sheet.local_status} confirmation={confirmation ?? sheet.confirmation} />
                  <dl className="grid grid-cols-1 gap-4">
                    <div>
                      <dt className="text-metadata-caps font-semibold uppercase text-muted">Amount</dt>
                      <dd className="mt-1 text-sm tabular-nums text-ink">{sheet.amount}</dd>
                    </div>
                    <div>
                      <dt className="text-metadata-caps font-semibold uppercase text-muted">Currency</dt>
                      <dd className="mt-1 text-sm text-ink">{sheet.currency}</dd>
                    </div>
                    <div>
                      <dt className="text-metadata-caps font-semibold uppercase text-muted">PayPal reference</dt>
                      <dd className="mt-1 break-all text-sm text-ink">{paypalReference(sheet)}</dd>
                    </div>
                    <div>
                      <dt className="text-metadata-caps font-semibold uppercase text-muted">Time</dt>
                      <dd className="mt-1 text-sm text-ink">{formatWhen(sheet.checked_at)}</dd>
                    </div>
                  </dl>
                </>
              ) : (
                <p className="text-sm text-muted">No payment is in context yet.</p>
              )}
              {link ? (
                <a href={link.href} className="text-sm font-medium text-action focus-ring">
                  {link.label}
                </a>
              ) : null}
              <p className="text-sm text-ink">The assistant cannot approve or send a refund.</p>
            </div>
          </Card>
        </aside>
      </div>
    </>
  );
}
