import type { ReactNode } from "react";

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div role="status" className="px-4 py-10 text-center sm:px-8">
      <h2 className="text-title-section text-ink">{title}</h2>
      <p className="mx-auto mt-2 max-w-lg text-sm leading-5 text-muted">{description}</p>
      {action ? <div className="mt-4 flex justify-center">{action}</div> : null}
    </div>
  );
}
