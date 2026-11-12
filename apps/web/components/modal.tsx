"use client";

import { useEffect, useId, useRef, type ReactNode } from "react";

export function Modal({
  title,
  children,
  onClose,
  dismissable = true,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  dismissable?: boolean;
}) {
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    dialogRef.current?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && dismissable) {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) {
        return;
      }
      const nodes = [...dialogRef.current.querySelectorAll<HTMLElement>("button, a[href], input, select, textarea")].filter(
        (node) => !node.hasAttribute("disabled"),
      );
      if (nodes.length === 0) {
        return;
      }
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && (active === first || !dialogRef.current.contains(active))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      previous?.focus();
    };
  }, [dismissable]);

  return (
    <div
      className="fixed inset-0 z-40 flex items-end justify-center bg-[var(--backdrop)] p-4 sm:items-center"
      onMouseDown={(event) => {
        if (dismissable && event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className="max-h-[calc(100vh-2rem)] w-full max-w-lg overflow-y-auto rounded-card border border-hairline bg-surface shadow-modal outline-none"
      >
        <div className="border-b border-hairline px-4 py-4 sm:px-6">
          <h2 id={titleId} className="text-title-section text-ink">
            {title}
          </h2>
        </div>
        <div className="px-4 py-4 sm:px-6 sm:py-5">{children}</div>
      </div>
    </div>
  );
}
