import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "var(--canvas)",
        surface: "var(--surface)",
        hairline: "var(--hairline)",
        ink: "var(--ink)",
        muted: "var(--muted)",
        action: "var(--action)",
        "action-hover": "var(--action-hover)",
        disabled: "var(--disabled)",
        "disabled-text": "var(--disabled-text)",
        completed: "var(--completed)",
        "completed-surface": "var(--completed-surface)",
        pending: "var(--pending)",
        "pending-surface": "var(--pending-surface)",
        failed: "var(--failed)",
        "failed-surface": "var(--failed-surface)",
        "failed-hover": "var(--failed-hover)",
        refunded: "var(--refunded)",
        "refunded-surface": "var(--refunded-surface)",
      },
      borderRadius: {
        card: "8px",
        control: "6px",
        chip: "4px",
      },
      boxShadow: {
        raised: "0 1px 2px rgba(0, 28, 100, 0.06)",
        modal: "0 4px 16px rgba(0, 28, 100, 0.12)",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "Inter", "sans-serif"],
      },
      fontSize: {
        caption: ["12px", { lineHeight: "16px", fontWeight: "400" }],
        "chip-label": ["12px", { lineHeight: "16px", letterSpacing: "0.01em", fontWeight: "600" }],
        "metadata-caps": ["12px", { lineHeight: "16px", letterSpacing: "0.06em", fontWeight: "600" }],
        "body-medium": ["14px", { lineHeight: "20px", fontWeight: "500" }],
        "title-section": ["18px", { lineHeight: "24px", fontWeight: "600" }],
        "title-page": ["28px", { lineHeight: "36px", letterSpacing: "-0.015em", fontWeight: "600" }],
      },
    },
  },
  plugins: [],
};

export default config;
