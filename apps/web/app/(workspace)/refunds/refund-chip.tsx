import { StatusChip } from "../../../components/status-chip";

export function RefundChip({ status }: { status: string }) {
  if (status === "pending_approval") {
    return (
      <span className="inline-flex h-[22px] items-center rounded-chip bg-pending-surface px-2 text-chip-label text-pending">
        Not sent
      </span>
    );
  }
  if (status === "rejected") {
    return (
      <span className="inline-flex h-[22px] items-center rounded-chip bg-failed-surface px-2 text-chip-label text-failed">
        Rejected
      </span>
    );
  }
  if (status === "completed") {
    return <StatusChip status="completed" confirmation="confirmed" />;
  }
  return <StatusChip status={status} />;
}
