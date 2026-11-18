import { ArrowUp } from "lucide-react";
import { useState } from "react";

interface Props {
  placeholder: string;
  disabled?: boolean;
  onSend: (text: string) => Promise<void> | void;
}

export function Composer({ placeholder, disabled, onSend }: Props) {
  const [text, setText] = useState("");
  const send = async () => {
    const t = text.trim();
    if (!t || disabled) return;
    setText("");
    await onSend(t);
  };
  return (
    <div className="px-8 pb-6 pt-2">
      <div className="mx-auto flex max-w-[680px] items-end gap-2 rounded-xl border border-border bg-surface px-4 py-3 shadow-[0_1px_3px_rgb(14_26_43/0.06)] focus-within:border-accent/60">
        <textarea
          rows={1}
          value={text}
          disabled={disabled}
          placeholder={placeholder}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          className="max-h-32 min-h-[20px] flex-1 resize-none bg-transparent text-[14px] outline-none placeholder:text-muted disabled:opacity-50"
        />
        <button
          onClick={send}
          disabled={disabled || !text.trim()}
          className="rounded-lg bg-accent p-1.5 text-white transition-opacity disabled:opacity-30"
          title="Send"
        >
          <ArrowUp size={14} />
        </button>
      </div>
    </div>
  );
}
