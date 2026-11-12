import { paypalApprovalHref } from "../lib/paypal-approval";

export function PayPalPayLink({
  approveUrl,
  paypalOrderId,
}: {
  approveUrl: string | null;
  paypalOrderId: string | null;
}) {
  const href = paypalApprovalHref(approveUrl, paypalOrderId);
  if (!href) {
    return null;
  }
  const logoutHref = href.includes("sandbox.paypal.com")
    ? "https://www.sandbox.paypal.com/signout"
    : "https://www.paypal.com/signout";
  return (
    <div className="mt-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <a
          href={logoutHref}
          target="_blank"
          rel="noreferrer"
          className="inline-flex h-10 items-center justify-center rounded-control border border-hairline bg-surface px-4 text-sm font-medium text-ink hover:border-ink focus-ring"
        >
          Log out of PayPal
        </a>
        <a
          href={href}
          target="_blank"
          rel="noreferrer"
          className="inline-flex h-10 items-center justify-center rounded-control bg-action px-4 text-sm font-medium text-white hover:bg-action-hover focus-ring"
        >
          Pay with PayPal
        </a>
      </div>
      <p className="mt-2 max-w-xl text-sm leading-5 text-muted">
        Log out of PayPal, then pay with a Sandbox personal account whose country is United States.
        PayPal hides Pay and shows “this seller doesn’t accept payments in your currency” when the buyer
        account is in India. Create that United States buyer under Sandbox accounts at developer.paypal.com.
      </p>
    </div>
  );
}
