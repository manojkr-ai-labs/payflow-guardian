export type IconName = "search" | "add" | "arrow_back" | "info";

export function Icon({ name, size = 20 }: { name: IconName; size?: 16 | 20 }) {
  return (
    <span aria-hidden="true" className="material-symbols-outlined" style={{ fontSize: size }}>
      {name}
    </span>
  );
}
