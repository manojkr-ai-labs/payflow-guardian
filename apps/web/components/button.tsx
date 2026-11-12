import type { ButtonHTMLAttributes } from "react";

import { cn } from "../lib/cn";

type ButtonVariant = "primary" | "secondary" | "quiet" | "destructive";

const VARIANTS: Record<ButtonVariant, string> = {
  primary: "bg-action text-white hover:bg-action-hover disabled:bg-disabled disabled:text-disabled-text",
  secondary:
    "border border-hairline bg-surface text-ink hover:border-ink hover:bg-canvas disabled:border-transparent disabled:bg-disabled disabled:text-disabled-text",
  quiet: "bg-transparent text-action hover:text-action-hover disabled:text-disabled-text",
  destructive: "bg-failed-surface text-failed hover:bg-failed-hover disabled:bg-disabled disabled:text-disabled-text",
};

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
};

export function Button({ variant = "primary", className, type = "button", ...props }: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        "inline-flex h-10 items-center justify-center rounded-control px-4 text-sm font-medium transition-colors focus-ring disabled:cursor-not-allowed",
        VARIANTS[variant],
        className,
      )}
      {...props}
    />
  );
}
