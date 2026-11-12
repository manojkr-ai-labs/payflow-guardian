"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { cn } from "../lib/cn";
import { SandboxChip } from "./status-chip";

const LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/payments", label: "Payments" },
  { href: "/assistant", label: "Assistant" },
  { href: "/refunds", label: "Refunds" },
];

function isCurrent(pathname: string, href: string): boolean {
  if (href === "/") {
    return pathname === "/";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppHeader({
  displayName,
  roleLabel,
  merchantName,
}: {
  displayName: string;
  roleLabel: string;
  merchantName: string;
}) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  async function signOut() {
    setPending(true);
    try {
      await fetch("/api/auth/logout", { method: "POST", credentials: "include" });
      window.location.assign("/login");
    } catch {
      setPending(false);
    }
  }

  return (
    <div className="sticky top-0 z-30">
      <header className="relative h-16 border-b border-hairline bg-surface">
      <div className="mx-auto flex h-16 w-full max-w-[1440px] items-center justify-between gap-4 px-4 md:px-8">
        <div className="flex h-full min-w-0 items-center gap-3 lg:gap-8">
          <div className="flex shrink-0 items-center gap-2">
            <Link href="/" className="text-[16px] font-semibold tracking-tight text-ink focus-ring lg:text-[20px]">
              PayFlow Guardian
            </Link>
            <SandboxChip />
          </div>
          <nav className="hidden h-full items-center gap-3 md:flex lg:gap-8" aria-label="Workspace">
            {LINKS.map((link) => {
              const current = isCurrent(pathname, link.href);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  aria-current={current ? "page" : undefined}
                  className={cn(
                    "flex h-full items-center border-b-2 text-sm font-medium focus-ring",
                    current ? "border-action text-action" : "border-transparent text-muted hover:text-ink",
                  )}
                >
                  {link.label}
                </Link>
              );
            })}
          </nav>
        </div>
        <div className="flex shrink-0 items-center">
          <button
            type="button"
            className="mr-3 h-10 rounded-control px-3 text-sm font-medium text-ink focus-ring md:hidden"
            aria-expanded={open}
            aria-controls="workspace-menu"
            onClick={() => setOpen((value) => !value)}
          >
            {open ? "Close" : "Menu"}
          </button>
          <div className="hidden text-right leading-tight min-[880px]:block">
            <p className="text-[13px] font-medium text-ink">{displayName}</p>
            <p className="hidden text-xs text-muted lg:block">
              {roleLabel} · {merchantName}
            </p>
          </div>
          <button
            type="button"
            className="ml-3 border-hairline text-[13px] font-medium text-muted hover:text-ink focus-ring disabled:text-disabled-text sm:ml-6 sm:border-l sm:pl-6"
            onClick={signOut}
            disabled={pending}
          >
            Sign out
          </button>
        </div>
      </div>
      {open ? (
        <nav
          id="workspace-menu"
          aria-label="Workspace"
          className="absolute left-0 right-0 top-16 border-b border-hairline bg-surface shadow-raised md:hidden"
        >
          <p className="px-4 pb-1 pt-3 text-[13px] font-medium text-ink">{displayName}</p>
          <p className="px-4 pb-2 text-xs text-muted">
            {roleLabel} · {merchantName}
          </p>
          {LINKS.map((link) => {
            const current = isCurrent(pathname, link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                aria-current={current ? "page" : undefined}
                className={cn(
                  "block border-l-2 px-4 py-3 text-sm font-medium focus-ring",
                  current ? "border-action text-action" : "border-transparent text-muted",
                )}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>
      ) : null}
      </header>
    </div>
  );
}
