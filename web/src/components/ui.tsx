// The Synapto design-system components (docs/design/design-system/components),
// rebuilt in TSX. Styles are the `sy-*` classes in components.css.

import { useId, type ButtonHTMLAttributes, type ReactNode } from "react";
import { capitalise } from "../format";

const cx = (...names: (string | false | null | undefined)[]) => names.filter(Boolean).join(" ");

export function Button({
  variant = "secondary",
  size = "md",
  icon,
  className,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "md" | "sm";
  icon?: ReactNode;
}) {
  return (
    <button type="button" {...rest} className={cx("sy-btn", `sy-btn-${variant}`, size === "sm" && "sy-btn-sm", className)}>
      {icon && (
        <span className="sy-btn-icon" aria-hidden>
          {icon}
        </span>
      )}
      {children}
    </button>
  );
}

const STATUS_GLYPH = { success: "✓", danger: "✕", warning: "!" } as const;

export function Badge({
  tone = "neutral",
  children,
}: {
  tone?: "neutral" | "accent" | "success" | "warning" | "danger";
  children: ReactNode;
}) {
  const glyph = tone in STATUS_GLYPH ? STATUS_GLYPH[tone as keyof typeof STATUS_GLYPH] : null;
  return (
    <span className={cx("sy-badge", `sy-badge-${tone}`)}>
      {glyph && <span aria-hidden>{glyph}</span>}
      {children}
    </span>
  );
}

export interface TabItem {
  id: string;
  label: string;
  count?: number;
}

export function Tabs({ items, value, onChange }: { items: TabItem[]; value: string; onChange: (id: string) => void }) {
  return (
    <div className="sy-tabs" role="tablist">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          role="tab"
          aria-selected={item.id === value}
          className={cx("sy-tab", item.id === value && "is-active")}
          onClick={() => onChange(item.id)}
        >
          {item.label}
          {item.count != null && <span className="sy-tab-count">{item.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function TextField({
  label,
  value,
  onChange,
  placeholder,
  hint,
  error,
  mono = false,
  disabled,
}: {
  label: ReactNode;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  hint?: ReactNode;
  error?: string | null;
  mono?: boolean;
  disabled?: boolean;
}) {
  const note = useId();
  return (
    <label className="sy-field">
      <span className="sy-field-label">{label}</span>
      <input
        className={cx("sy-input", mono && "is-mono", error && "is-error")}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        spellCheck={false}
        aria-invalid={!!error}
        aria-describedby={note}
      />
      {error ? (
        <span id={note} className="sy-field-error">
          ✕ {error}
        </span>
      ) : (
        hint && (
          <span id={note} className="sy-field-hint">
            {hint}
          </span>
        )
      )}
    </label>
  );
}

export function ProgressRing({ value, size = 40, stroke = 4 }: { value: number; size?: number; stroke?: number }) {
  const v = Math.max(0, Math.min(1, value));
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const mid = size / 2;
  return (
    <span className="sy-ring" style={{ width: size, height: size }} role="img" aria-label={`${Math.round(v * 100)}% complete`}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle className="sy-ring-track" cx={mid} cy={mid} r={r} strokeWidth={stroke} fill="none" />
        <circle
          className={cx("sy-ring-fill", v >= 1 && "is-done")}
          cx={mid}
          cy={mid}
          r={r}
          strokeWidth={stroke}
          fill="none"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - v)}
          strokeLinecap="round"
          transform={`rotate(-90 ${mid} ${mid})`}
        />
      </svg>
      {size >= 36 && <span className="sy-ring-label">{v >= 1 ? "✓" : `${Math.round(v * 100)}%`}</span>}
    </span>
  );
}

const CALLOUT_GLYPH = { info: "i", success: "✓", warning: "!", danger: "✕" } as const;

export function Callout({
  tone = "info",
  title,
  children,
  action,
}: {
  tone?: "info" | "success" | "warning" | "danger";
  title?: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className={cx("sy-callout", `sy-callout-${tone}`)} role={tone === "danger" ? "alert" : "note"}>
      <span className="sy-callout-icon" aria-hidden>
        {CALLOUT_GLYPH[tone]}
      </span>
      <div className="sy-callout-body">
        {title && <strong>{title}</strong>}
        {children && <div>{children}</div>}
      </div>
      {action}
    </div>
  );
}

export type QuizOptionState = "idle" | "selected" | "correct" | "wrong";

export function QuizOption({
  optionId,
  state = "idle",
  disabled,
  onClick,
  children,
}: {
  optionId: string;
  state?: QuizOptionState;
  disabled?: boolean;
  onClick?: () => void;
  children: ReactNode;
}) {
  const mark = state === "correct" ? "✓" : state === "wrong" ? "✕" : optionId;
  return (
    <button
      type="button"
      className={cx("sy-opt", `is-${state}`)}
      aria-pressed={state !== "idle"}
      onClick={onClick}
      disabled={disabled}
    >
      <span className="sy-opt-key">{mark}</span>
      <span className="sy-opt-text">{children}</span>
      {state === "correct" && <span className="sy-opt-tag">Correct</span>}
      {state === "wrong" && <span className="sy-opt-tag">Not quite</span>}
    </button>
  );
}

export function TestResult({
  tests,
  glow = false,
}: {
  tests: { name: string; status: string; message?: string }[];
  /** Mark a run that just passed as live. */
  glow?: boolean;
}) {
  const passed = tests.filter((t) => t.status === "passed").length;
  return (
    <div className={cx("sy-tests", glow && "is-glow")} aria-live="polite">
      <div className="sy-tests-head">
        <span className="sy-overline">Tests</span>
        <Badge tone={passed === tests.length ? "success" : "danger"}>
          {passed} of {tests.length} passed
        </Badge>
      </div>
      {tests.map((t) => {
        const ok = t.status === "passed";
        return (
          <div key={t.name} className={cx("sy-test", ok ? "is-pass" : "is-fail")}>
            <span className="sy-test-mark" aria-hidden>
              {ok ? "✓" : "✕"}
            </span>
            <div className="sy-test-main">
              <span className="sy-test-name">{t.name}</span>
              {!ok && t.message && <pre className="sy-test-msg">{t.message}</pre>}
            </div>
            <span className="sy-test-status">{capitalise(t.status)}</span>
          </div>
        );
      })}
    </div>
  );
}

/** Centred status text for loading and errors inside a page. */
export function Status({ error, children }: { error?: Error; children?: ReactNode }) {
  if (error) {
    return (
      <Callout tone="danger" title="Couldn't load this">
        {error.message}
      </Callout>
    );
  }
  return <p className="status-line">{children ?? "Loading…"}</p>;
}
