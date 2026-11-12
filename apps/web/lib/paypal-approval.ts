const PAYPAL_HOSTS = new Set(["www.paypal.com", "www.sandbox.paypal.com", "paypal.com", "sandbox.paypal.com"]);

export function paypalApprovalHref(approveUrl: string | null, paypalOrderId: string | null): string | null {
  if (!approveUrl) {
    return null;
  }
  let url: URL;
  try {
    url = new URL(approveUrl);
  } catch {
    return null;
  }
  if (url.protocol !== "https:" && url.protocol !== "http:") {
    return null;
  }
  const orderId = paypalOrderId?.trim() ?? "";
  if (PAYPAL_HOSTS.has(url.hostname) && /^[A-Za-z0-9]+$/.test(orderId)) {
    return `https://${url.hostname}/checkoutnow?token=${encodeURIComponent(orderId)}`;
  }
  return url.toString();
}
