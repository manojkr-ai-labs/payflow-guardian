import { RefundReview } from "./refund-review";

export default async function RefundPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <RefundReview refundId={id} />;
}
