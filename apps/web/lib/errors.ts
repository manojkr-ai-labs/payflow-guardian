import type { ErrorCode } from "./api";

const ERROR_COPY: Record<ErrorCode, string> = {
  not_found: "That payment or refund is not in this merchant workspace.",
  validation_failed: "Check the fields and try again.",
  approval_required: "A refund is not sent until the owner approves it.",
  approval_stale: "This request changed. Approve the current request again.",
  paypal_failed: "PayPal did not complete this request.",
  needs_checking: "PayPal has not confirmed this result. It needs a check.",
  forbidden: "Only an owner can approve a refund.",
  unauthorized: "Sign in to continue.",
  unknown: "The request could not be completed.",
};

export function messageFor(code: ErrorCode, message?: string): string {
  if (message && message.trim()) {
    return message;
  }
  return ERROR_COPY[code];
}
