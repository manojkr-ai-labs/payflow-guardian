import type { ErrorCode } from "../lib/api";
import { messageFor } from "../lib/errors";
import { cn } from "../lib/cn";
import { Icon } from "./icon";

export function ErrorBanner({ code, message }: { code: ErrorCode; message?: string }) {
  const pending = code === "needs_checking";
  return (
    <div
      role="alert"
      className={cn(
        "flex items-start gap-3 rounded-card border px-4 py-3",
        pending ? "border-pending-surface bg-pending-surface text-pending" : "border-failed-surface bg-failed-surface text-failed",
      )}
    >
      <Icon name="info" size={20} />
      <p className="text-[13px] leading-5">{messageFor(code, message)}</p>
    </div>
  );
}
