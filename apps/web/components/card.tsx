import type { ReactNode } from "react";

import { cn } from "../lib/cn";

export function Card({
  children,
  raised = false,
  className,
}: {
  children: ReactNode;
  raised?: boolean;
  className?: string;
}) {
  return (
    <section className={cn("rounded-card border border-hairline bg-surface", raised && "shadow-raised", className)}>
      {children}
    </section>
  );
}
