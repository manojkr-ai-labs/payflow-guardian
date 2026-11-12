import { CancelPayment } from "./cancel-payment";

export default async function PaymentCancelPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <CancelPayment paymentId={id} />;
}
