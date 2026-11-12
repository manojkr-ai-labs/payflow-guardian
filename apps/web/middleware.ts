import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { SESSION_COOKIE } from "./lib/session";

const API_PROXY_URL = process.env.API_PROXY_URL ?? "http://localhost:8000";

async function sessionIsValid(token: string): Promise<boolean> {
  try {
    const response = await fetch(`${API_PROXY_URL}/api/auth/me`, {
      headers: { cookie: `${SESSION_COOKIE}=${token}` },
      cache: "no-store",
    });
    return response.ok;
  } catch {
    return false;
  }
}

function clearSession(response: NextResponse): NextResponse {
  response.cookies.set({
    name: SESSION_COOKIE,
    value: "",
    path: "/",
    maxAge: 0,
    httpOnly: true,
    sameSite: "lax",
  });
  return response;
}

export async function middleware(request: NextRequest) {
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  const isLogin = request.nextUrl.pathname === "/login";

  if (!token) {
    if (isLogin) {
      return NextResponse.next();
    }
    return NextResponse.redirect(new URL("/login", request.url));
  }

  if (!(await sessionIsValid(token))) {
    const response = isLogin ? NextResponse.next() : NextResponse.redirect(new URL("/login", request.url));
    return clearSession(response);
  }

  if (isLogin) {
    return NextResponse.redirect(new URL("/", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
