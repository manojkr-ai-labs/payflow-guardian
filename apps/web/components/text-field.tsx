import type { InputHTMLAttributes } from "react";

import { cn } from "../lib/cn";

type TextFieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  error?: string;
};

export function TextField({ id, label, error, className, ...props }: TextFieldProps) {
  const errorId = error ? `${id}-error` : undefined;

  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-ink">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={errorId}
        className={cn(
          "h-10 w-full rounded-control border bg-surface px-3.5 text-sm text-ink placeholder:text-muted focus:border-action focus-ring",
          error ? "border-failed" : "border-hairline",
          className,
        )}
        {...props}
      />
      {error ? (
        <p id={errorId} className="mt-1.5 text-xs text-failed">
          {error}
        </p>
      ) : null}
    </div>
  );
}
