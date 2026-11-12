import { Card } from "../../components/card";
import { SandboxChip } from "../../components/status-chip";
import { LoginForm } from "./login-form";

const LINES = [
  "Check a payment against PayPal Sandbox",
  "Read the status in plain language",
  "Approve a refund before it is sent",
];

export default function LoginPage() {
  return (
    <main className="flex min-h-screen w-full flex-col md:flex-row">
      <section className="flex w-full flex-col justify-between border-b border-hairline bg-canvas px-8 py-10 md:w-[58%] md:border-b-0 md:border-r md:px-12 md:py-12 lg:px-20 lg:py-16">
        <div className="flex items-center gap-3">
          <span className="text-[26px] font-semibold leading-8 tracking-tight text-ink">PayFlow Guardian</span>
          <SandboxChip />
        </div>
        <div className="my-14 max-w-xl md:my-auto">
          <h1 className="text-[32px] font-semibold leading-[42px] tracking-tight text-ink sm:text-[40px] sm:leading-[46px]">
            See what PayPal confirmed, then decide the next step.
          </h1>
          <ul className="mt-10 space-y-4">
            {LINES.map((line) => (
              <li key={line} className="border-l-2 border-action py-0.5 pl-3.5 text-[15px] leading-snug text-muted">
                {line}
              </li>
            ))}
          </ul>
        </div>
        <p className="pt-6 text-[13px] leading-5 text-muted">Demo uses PayPal Sandbox. Nothing here moves live money.</p>
      </section>
      <section className="flex w-full items-center justify-center bg-surface p-6 sm:p-10 md:w-[42%] lg:p-12">
        <Card raised className="w-full max-w-[420px] p-8 sm:p-10">
          <p className="text-metadata-caps uppercase text-muted">Merchant sign in</p>
          <h2 className="mt-1.5 text-[26px] font-semibold leading-8 tracking-tight text-ink">Open the workspace</h2>
          <LoginForm />
          <div className="mt-8 border-t border-hairline pt-6">
            <p className="text-metadata-caps uppercase text-muted">Test accounts</p>
            <dl className="mt-3 space-y-2 text-xs text-muted">
              <div className="flex items-center justify-between gap-4">
                <dt className="font-medium text-[#414753]">Owner</dt>
                <dd className="tabular-nums">owner@payflow.test</dd>
              </div>
              <div className="flex items-center justify-between gap-4">
                <dt className="font-medium text-[#414753]">Support</dt>
                <dd className="tabular-nums">support@payflow.test</dd>
              </div>
            </dl>
            <p className="mt-3 text-xs leading-4 text-muted">
              Test example passwords: owner-test-example and support-test-example.
            </p>
          </div>
        </Card>
      </section>
    </main>
  );
}
