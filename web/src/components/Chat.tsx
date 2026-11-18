import { ChevronRight, CircleAlert } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { SessionState } from "../lib/session";
import type { CallItem, MessageItem, TimelineItem } from "../lib/types";
import { TagDots, VerdictPill } from "./ui";
import { VerdictCard } from "./VerdictCard";

interface Props {
  state: SessionState;
  activePath: string | null;
  onShowPath: (call: CallItem) => void;
  onDecide: (callId: string, d: "allow" | "deny" | "allow_once") => void;
}

type Block = { kind: "message"; m: MessageItem; key: string } | { kind: "calls"; calls: CallItem[]; key: string };

/** Consecutive tool calls are shown together as one step list. */
function group(items: TimelineItem[]): Block[] {
  const out: Block[] = [];
  items.forEach((it, i) => {
    if (it.kind === "message") out.push({ kind: "message", m: it, key: `m${i}` });
    else {
      const last = out[out.length - 1];
      if (last?.kind === "calls") last.calls.push(it);
      else out.push({ kind: "calls", calls: [it], key: it.id });
    }
  });
  return out;
}

export function Chat({ state, activePath, onShowPath, onDecide }: Props) {
  const end = useRef<HTMLDivElement>(null);
  const count = state.items.length;
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [count, state.pending.length]);

  return (
    <div className="flex-1 overflow-y-auto px-8 py-6">
      <div className="mx-auto max-w-[680px] space-y-5">
        {group(state.items).map((b) =>
          b.kind === "message" ? (
            <Message key={b.key} m={b.m} />
          ) : (
            <div key={b.key} className="overflow-hidden rounded-xl border border-border bg-surface">
              {b.calls.map((c, i) => (
                <div key={c.id} className={i ? "border-t border-border" : ""}>
                  <CallRow call={c} />
                  {(c.decision === "block" || c.decision === "ask") && (
                    <VerdictCard
                      call={c}
                      pending={state.pending.includes(c.id)}
                      pathActive={activePath === c.id}
                      onShowPath={() => onShowPath(c)}
                      onDecide={(d) => onDecide(c.id, d)}
                    />
                  )}
                </div>
              ))}
            </div>
          ),
        )}
        {state.running && (
          <div className="flex items-center gap-2 text-[13px] text-muted">
            <span className="h-2 w-2 animate-pulse rounded-full bg-accent" /> Working
          </div>
        )}
        <div ref={end} />
      </div>
    </div>
  );
}

function Message({ m }: { m: MessageItem }) {
  if (m.role === "error") {
    return (
      <div className="flex items-start gap-2 rounded-lg border border-sendsout/30 bg-sendsout/[0.05] px-4 py-3 text-[13px] text-sendsout">
        <CircleAlert size={16} className="mt-0.5 shrink-0" /> {m.text}
      </div>
    );
  }
  if (m.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-accent/10 px-4 py-2.5 text-[14px] leading-relaxed">
          {m.text}
        </div>
      </div>
    );
  }
  return <div className="whitespace-pre-wrap text-[14px] leading-[1.65] text-text">{m.text}</div>;
}

function CallRow({ call }: { call: CallItem }) {
  const [open, setOpen] = useState(false);
  const isSend = call.tags?.includes("sends_out");
  const showPill = call.decision && (isSend || call.decision !== "allow");
  return (
    <>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-surface-2"
        aria-expanded={open}
      >
        <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-surface-2 text-[12px] font-medium text-muted">
          {call.step}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2">
            <span className="text-[13px] font-medium">{call.tool}</span>
            <TagDots tags={call.tags} />
          </span>
          {call.label && call.label !== call.tool && (
            <span className="block truncate font-mono text-[12px] text-muted">{call.label}</span>
          )}
        </span>
        {call.status === "pending" && !call.decision && <span className="text-[12px] text-muted">checking</span>}
        {showPill && (
          <VerdictPill
            decision={call.decision!}
            title={call.check_ms != null ? `Checked in ${call.check_ms.toFixed(2)} ms` : undefined}
          />
        )}
        {!showPill && call.status === "ran" && <span className="text-[12px] text-muted">done</span>}
        <ChevronRight size={14} className={`shrink-0 text-muted transition-transform ${open ? "rotate-90" : ""}`} />
      </button>
      {open && (
        <div className="space-y-3 px-4 pb-4 pl-[52px]">
          <Detail label="Arguments" text={JSON.stringify(call.args, null, 2)} />
          {call.output && <Detail label={call.status === "ran" ? "Output" : "Returned to the agent"} text={call.output} />}
        </div>
      )}
    </>
  );
}

function Detail({ label, text }: { label: string; text: string }) {
  return (
    <div>
      <div className="mb-1 text-[12px] text-muted">{label}</div>
      <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded-md bg-surface-2 p-3 font-mono text-[12px] leading-relaxed text-text/90">
        {text}
      </pre>
    </div>
  );
}
