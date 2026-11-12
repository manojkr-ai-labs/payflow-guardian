export type ErrorCode =
  | "not_found"
  | "validation_failed"
  | "approval_required"
  | "approval_stale"
  | "paypal_failed"
  | "needs_checking"
  | "forbidden"
  | "unauthorized"
  | "unknown";

export type MerchantUser = {
  id: string;
  email: string;
  display_name: string;
  role: "owner" | "support";
  merchant_id: string;
  merchant_name: string;
};

export type TestOrder = {
  code: string;
  description: string;
  amount_minor: number;
  display_amount: string;
  currency: string;
};

export type FactSheet = {
  payment_id: string;
  paypal_order_id: string | null;
  paypal_capture_id: string | null;
  paypal_status: string | null;
  local_status: string;
  confirmation: string;
  amount: string;
  currency: string;
  missing: string[];
  checked_at: string | null;
  mismatch?: boolean;
};

export type CreatedPayment = {
  id: string;
  order_id: string;
  test_order_code: string;
  description: string;
  amount_minor: number;
  display_amount: string;
  currency: string;
  status: string;
  confirmation: string;
  paypal_order_id: string | null;
  paypal_capture_id: string | null;
  paypal_status: string | null;
  approve_url: string | null;
  created_at: string;
  updated_at: string;
  last_checked_at: string | null;
  fact_sheet: FactSheet | null;
};

export type PaymentListItem = {
  id: string;
  status: string;
  confirmation: string;
  amount_minor: number;
  currency: string;
  paypal_order_id: string | null;
  paypal_capture_id: string | null;
  paypal_status: string | null;
  created_at: string;
  updated_at: string;
  test_order_code: string;
};

export type RefundRequest = {
  id: string;
  payment_id: string;
  capture_id: string;
  amount_minor: number;
  currency: string;
  reason: string;
  payload_hash: string;
  status: string;
  prepared_by: string;
  approved_by: string | null;
  approved_at: string | null;
  paypal_refund_id: string | null;
  paypal_status: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export class ApiError extends Error {
  code: ErrorCode;
  payment?: CreatedPayment;
  refund?: RefundRequest;

  constructor(code: ErrorCode, message: string, payment?: CreatedPayment, refund?: RefundRequest) {
    super(message);
    this.code = code;
    this.payment = payment;
    this.refund = refund;
  }
}

type ErrorBody = {
  error?: {
    code?: string;
    message?: string;
  };
  payment?: CreatedPayment;
  refund?: RefundRequest;
};

const ERROR_CODES = new Set<ErrorCode>([
  "not_found",
  "validation_failed",
  "approval_required",
  "approval_stale",
  "paypal_failed",
  "needs_checking",
  "forbidden",
  "unauthorized",
  "unknown",
]);

function asErrorCode(value: string | undefined): ErrorCode {
  if (value && ERROR_CODES.has(value as ErrorCode)) {
    return value as ErrorCode;
  }
  return "unknown";
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: "include",
    cache: "no-store",
    headers: {
      "content-type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ErrorBody | null;
    throw new ApiError(
      asErrorCode(body?.error?.code),
      body?.error?.message ?? "The request could not be completed.",
      body?.payment,
      body?.refund,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export async function listPayments(filters?: { q?: string; status?: string }): Promise<PaymentListItem[]> {
  const params = new URLSearchParams();
  if (filters?.q) {
    params.set("q", filters.q);
  }
  if (filters?.status) {
    params.set("status", filters.status);
  }
  const query = params.toString();
  const body = await apiRequest<{ payments: PaymentListItem[] }>(`/api/payments${query ? `?${query}` : ""}`);
  return body.payments;
}

export async function getPayment(id: string): Promise<CreatedPayment> {
  const body = await apiRequest<{ payment: CreatedPayment }>(`/api/payments/${id}`);
  return body.payment;
}

export async function investigatePayment(id: string): Promise<CreatedPayment> {
  const body = await apiRequest<{ payment: CreatedPayment }>(`/api/payments/${id}/investigate`, {
    method: "POST",
  });
  return body.payment;
}

export async function capturePayment(id: string): Promise<CreatedPayment> {
  const body = await apiRequest<{ payment: CreatedPayment }>(`/api/payments/${id}/capture`, {
    method: "POST",
  });
  return body.payment;
}

export type AssistantReply = {
  answer: string;
  next_step: string | null;
  confirmation: string | null;
  fact_sheet: FactSheet | null;
  refund_id?: string | null;
};

export async function currentUser(): Promise<MerchantUser> {
  const body = await apiRequest<{ user: MerchantUser }>("/api/auth/me");
  return body.user;
}

export type ActivityEvent = {
  action: string;
  summary: string;
  outcome: string;
  amount_minor: number | null;
  currency: string | null;
  paypal_reference: string | null;
  actor_type: string;
  created_at: string;
};

export async function listActivity(): Promise<ActivityEvent[]> {
  const body = await apiRequest<{ events: ActivityEvent[] }>("/api/activity");
  return body.events;
}

export async function listRefunds(): Promise<RefundRequest[]> {
  const body = await apiRequest<{ refunds: RefundRequest[] }>("/api/refunds");
  return body.refunds;
}

export async function getRefund(id: string): Promise<RefundRequest> {
  const body = await apiRequest<{ refund: RefundRequest }>(`/api/refunds/${id}`);
  return body.refund;
}

export async function prepareRefund(input: {
  payment_id: string;
  amount_minor: number;
  currency: string;
  reason: string;
}): Promise<RefundRequest> {
  const body = await apiRequest<{ refund: RefundRequest }>("/api/refunds", {
    method: "POST",
    body: JSON.stringify(input),
  });
  return body.refund;
}

export async function approveRefund(id: string): Promise<RefundRequest> {
  const body = await apiRequest<{ refund: RefundRequest }>(`/api/refunds/${id}/approve`, { method: "POST" });
  return body.refund;
}

export async function rejectRefund(id: string): Promise<RefundRequest> {
  const body = await apiRequest<{ refund: RefundRequest }>(`/api/refunds/${id}/reject`, { method: "POST" });
  return body.refund;
}

export async function sendAssistantMessage(message: string, conversationId: string): Promise<AssistantReply> {
  return apiRequest<AssistantReply>("/api/assistant/messages", {
    method: "POST",
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });
}
