const NOTICES = ["Privacy Policy", "Terms of Service", "Cookie Preferences"];

export function AppFooter() {
  return (
    <footer className="mt-auto flex w-full flex-col items-center justify-between gap-3 border-t border-hairline bg-surface px-4 py-4 md:flex-row md:px-8">
      <p className="text-center text-xs text-muted md:text-left">
        Demo uses PayPal Sandbox. Nothing here moves live money.
      </p>
      <p className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs text-muted">
        {NOTICES.map((notice) => (
          <span key={notice}>{notice}</span>
        ))}
      </p>
    </footer>
  );
}
