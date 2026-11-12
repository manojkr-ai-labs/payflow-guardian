import { cn } from "../lib/cn";

type ChipTone = "completed" | "pending" | "failed" | "refunded";

const TONE_CLASS: Record<ChipTone, string> = {
  completed: "bg-completed-surface text-completed",
  pending: "bg-pending-surface text-pending",
  failed: "bg-failed-surface text-failed",
  refunded: "bg-refunded-surface text-refunded",
};

export function statusPresentation(status: string, confirmation?: string): { label: string; tone: ChipTone } {
  if (status === "completed" && confirmation === "confirmed") {
    return { label: "Completed", tone: "completed" };
  }
  if (status === "needs_checking" || (status === "completed" && confirmation !== "confirmed")) {
    return { label: "Needs checking", tone: "pending" };
  }
  if (status === "failed") {
    return { label: "Failed", tone: "failed" };
  }
  if (status === "refunded") {
    return { label: "Refunded", tone: "refunded" };
  }
  if (status === "partially_refunded") {
    return { label: "Partially refunded", tone: "refunded" };
  }
  if (status === "awaiting_payer" || status === "pending" || status === "created") {
    return { label: "Pending", tone: "pending" };
  }
  return { label: "Needs checking", tone: "pending" };
}

export function StatusChip({ status, confirmation }: { status: string; confirmation?: string }) {
  const presentation = statusPresentation(status, confirmation);
  return (
    <span
      className={cn(
        "inline-flex h-[22px] items-center rounded-chip px-2 text-chip-label",
        TONE_CLASS[presentation.tone],
      )}
    >
      {presentation.label}
    </span>
  );
}

export function SandboxChip() {
  return (
    <span className="inline-flex h-[22px] items-center rounded-chip bg-refunded-surface px-2 text-[11px] font-semibold uppercase tracking-wider text-refunded">
      Sandbox
    </span>
  );
}
