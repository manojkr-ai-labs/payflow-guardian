"use client";

import { FormEvent, useState } from "react";

import { Button } from "../../components/button";
import { ErrorBanner } from "../../components/error-banner";
import { TextField } from "../../components/text-field";
import { ApiError, apiRequest, type MerchantUser } from "../../lib/api";

export function LoginForm() {
  const [email, setEmail] = useState("owner@payflow.test");
  const [password, setPassword] = useState("");
  const [emailError, setEmailError] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [formError, setFormError] = useState<ApiError | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextEmailError = email.trim() ? "" : "Enter an email address.";
    const nextPasswordError = password ? "" : "Enter a password.";
    setEmailError(nextEmailError);
    setPasswordError(nextPasswordError);
    setFormError(null);
    if (nextEmailError || nextPasswordError) {
      return;
    }

    setPending(true);
    try {
      await apiRequest<{ user: MerchantUser }>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: email.trim(), password }),
      });
      window.location.assign("/");
    } catch (caught) {
      setFormError(caught instanceof ApiError ? caught : new ApiError("unknown", "Sign in could not be completed."));
      setPending(false);
    }
  }

  return (
    <form className="mt-6 space-y-4" onSubmit={onSubmit} noValidate>
      <TextField
        id="email"
        label="Email address"
        type="email"
        autoComplete="username"
        value={email}
        error={emailError}
        onChange={(event) => setEmail(event.target.value)}
      />
      <TextField
        id="password"
        label="Password"
        type="password"
        autoComplete="current-password"
        value={password}
        error={passwordError}
        onChange={(event) => setPassword(event.target.value)}
      />
      {formError ? <ErrorBanner code={formError.code} message={formError.message} /> : null}
      <Button type="submit" className="w-full" disabled={pending}>
        Sign in
      </Button>
    </form>
  );
}
