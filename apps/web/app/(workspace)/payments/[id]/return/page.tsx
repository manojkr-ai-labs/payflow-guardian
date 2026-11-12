import { ReturnCapture } from "./return-capture";

export default async function PaymentReturnPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ReturnCapture paymentId={id} />;
}
