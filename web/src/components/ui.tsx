import type { ButtonHTMLAttributes, ReactNode } from "react";
import type { Decision, Tag } from "../lib/types";

type Variant = "primary" | "ghost" | "danger" | "outline";

export function Button({
  variant = "outline", size = "md", className = "", children, ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: "md" | "lg" }) {
  const styles: Record<Variant, string> = {
    primary: "bg-accent text-white border-accent hover:brightness-110",
    outline: "bg-surface text-text border-border hover:bg-surface-2",
    ghost: "bg-transparent text-muted border-transparent hover:text-text hover:bg-surface-2",
    danger: "bg-surface text-sendsout border-sendsout/35 hover:bg-sendsout/10",
  };
  const sizes = { md: "h-8 px-3 text-[13px]", lg: "h-10 px-4 text-[14px]" };
  return (
    <button
      className={`inline-flex items-center gap-2 rounded-md border font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${sizes[size]} ${styles[variant]} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}

const pillStyle: Record<Decision, string> = {
  allow: "text-allow bg-allow/10",
  ask: "text-ask bg-ask/10",
  block: "text-sendsout bg-sendsout/10",
};

export function VerdictPill({ decision, title }: { decision: Decision; title?: string }) {
  return (
    <span title={title} className={`rounded-full px-2 py-0.5 text-[12px] font-medium capitalize ${pillStyle[decision]}`}>
      {decision}
    </span>
  );
}

export type ChipTone = "neutral" | "accent" | "block" | "ask" | "allow";

const chipStyle: Record<ChipTone, string> = {
  neutral: "bg-surface-2 text-muted",
  accent: "bg-accent/10 text-accent",
  block: "bg-sendsout/10 text-sendsout",
  ask: "bg-ask/10 text-ask",
  allow: "bg-allow/10 text-allow",
};

export function Chip({ tone = "neutral", children }: { tone?: ChipTone; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[12px] font-medium ${chipStyle[tone]}`}>
      {children}
    </span>
  );
}

const tagColor: Record<Tag, string> = { outside: "bg-outside", private: "bg-private", sends_out: "bg-sendsout" };
export const tagName: Record<Tag, string> = { outside: "Outside", private: "Private", sends_out: "Sends out" };

export function TagDots({ tags }: { tags?: Tag[] }) {
  if (!tags?.length) return null;
  return (
    <span className="flex items-center gap-1" aria-label={tags.map((t) => tagName[t]).join(", ")}>
      {tags.map((t) => (
        <span key={t} title={tagName[t]} className={`h-2 w-2 rounded-full ${tagColor[t]}`} />
      ))}
    </span>
  );
}

export function TagLegend() {
  return (
    <div className="flex items-center gap-4 text-[12px] text-muted">
      {(Object.keys(tagName) as Tag[]).map((t) => (
        <span key={t} className="flex items-center gap-1.5">
          <span className={`h-2 w-2 rounded-full ${tagColor[t]}`} />
          {tagName[t]}
        </span>
      ))}
    </div>
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="rounded border border-border bg-surface-2 px-1.5 font-mono text-[11px] text-muted">{children}</kbd>
  );
}

export function Segmented<T extends string>({
  value, options, onChange, title,
}: { value: T; options: T[]; onChange: (v: T) => void; title?: string }) {
  return (
    <div title={title} className="flex h-8 items-center rounded-md border border-border bg-surface-2 p-0.5">
      {options.map((o) => (
        <button
          key={o}
          onClick={() => onChange(o)}
          className={`h-full rounded px-3 text-[12px] font-medium capitalize transition-colors ${
            o === value ? "bg-surface text-text shadow-[0_1px_2px_rgb(14_26_43/0.08)]" : "text-muted hover:text-text"
          }`}
        >
          {o}
        </button>
      ))}
    </div>
  );
}

export const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
export const modKey = isMac ? "⌘" : "Ctrl";
