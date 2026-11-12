import { PaymentDetail } from "./payment-detail";

export default async function PaymentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <PaymentDetail paymentId={id} />;
}
