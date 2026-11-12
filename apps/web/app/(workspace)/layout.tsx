import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { AppFooter } from "../../components/app-footer";
import { AppHeader } from "../../components/app-header";
import type { MerchantUser } from "../../lib/api";
import { SESSION_COOKIE } from "../../lib/session";

export const dynamic = "force-dynamic";

const API_PROXY_URL = process.env.API_PROXY_URL ?? "http://localhost:8000";

function roleLabel(role: string): string {
  if (role === "owner") {
    return "Owner";
  }
  if (role === "support") {
    return "Support";
  }
  return role;
}

export default async function WorkspaceLayout({ children }: { children: ReactNode }) {
  const cookieStore = await cookies();
  const session = cookieStore.get(SESSION_COOKIE)?.value;
  if (!session) {
    redirect("/login");
  }

  const response = await fetch(`${API_PROXY_URL}/api/auth/me`, {
    headers: { cookie: `${SESSION_COOKIE}=${session}` },
    cache: "no-store",
  });
  if (!response.ok) {
    redirect("/login");
  }

  const body = (await response.json()) as { user: MerchantUser };
  const user = body.user;

  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <AppHeader displayName={user.display_name} roleLabel={roleLabel(user.role)} merchantName={user.merchant_name} />
      <main className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-8 md:px-6 lg:px-8">{children}</main>
      <AppFooter />
    </div>
  );
}
