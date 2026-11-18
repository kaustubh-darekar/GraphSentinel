import { Route, ShieldAlert, ShieldX } from "lucide-react";
import type { ReactNode } from "react";
import type { CallItem } from "../lib/types";
import { Button } from "./ui";

/** Renders a guard reason with Outside / Private highlighted and destinations in mono. */
export function Reason({ text }: { text: string }) {
  const body = text.replace(/^(Blocked|Ask):\s*/, "");
  const parts: ReactNode[] = [];
  const re = /(Outside|Private)( \([^)]*\))?|((?:#[\w-]+|[\w.+-]+@[\w.-]+\w)(?:, )?)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(body))) {
    parts.push(body.slice(last, m.index));
    if (m[1]) {
      parts.push(
        <span key={m.index}>
          <b className={`font-semibold ${m[1] === "Outside" ? "text-outside" : "text-private"}`}>{m[1]}</b>
          {m[2]}
        </span>,
      );
    } else {
      parts.push(
        <code key={m.index} className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[12.5px]">{m[3]}</code>,
      );
    }
    last = m.index + m[0].length;
  }
  parts.push(body.slice(last));
  return <>{parts}</>;
}

interface Props {
  call: CallItem;
  pending: boolean;
  pathActive: boolean;
  onShowPath: () => void;
  onDecide: (d: "allow" | "deny" | "allow_once") => void;
}

export function VerdictCard({ call, pending, pathActive, onShowPath, onDecide }: Props) {
  const block = call.decision === "block";
  const overridden = call.resolution === "overridden";
  const tone = block ? "border-sendsout/25 bg-sendsout/[0.05]" : "border-ask/30 bg-ask/[0.06]";
  const Icon = block ? ShieldX : ShieldAlert;
  const title = block ? "Blocked" : pending ? "Needs your approval" : "Held for approval";
  return (
    <div className={`mx-3 mb-3 rounded-lg border p-4 ${tone}`}>
      <div className="flex items-center gap-2">
        <Icon size={16} className={block ? "text-sendsout" : "text-ask"} />
        <span className={`text-[13px] font-semibold ${block ? "text-sendsout" : "text-ask"}`}>{title}</span>
        {call.check_ms != null && (
          <span className="ml-auto text-[12px] text-muted">checked in {call.check_ms.toFixed(1)} ms</span>
        )}
      </div>
      <p className="mt-2 text-[14px] leading-relaxed text-text">
        Data from <Reason text={(call.reason ?? "").replace(/^(Blocked|Ask): data from /, "")} />
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {(call.path?.length ?? 0) > 0 && (
          <Button onClick={onShowPath} variant={pathActive ? "primary" : "outline"}>
            <Route size={14} /> {pathActive ? "Hide path" : "Show path"}
          </Button>
        )}
        {block && !overridden && call.status === "blocked" && (
          <Button variant="danger" onClick={() => onDecide("allow_once")}>Allow once</Button>
        )}
        {!block && pending && (
          <>
            <Button variant="primary" onClick={() => onDecide("allow")}>Allow</Button>
            <Button onClick={() => onDecide("deny")}>Deny</Button>
          </>
        )}
        <Outcome call={call} pending={pending} />
      </div>
    </div>
  );
}

function Outcome({ call, pending }: { call: CallItem; pending: boolean }) {
  if (pending) return <span className="ml-1 text-[12px] text-muted">The agent is waiting for you.</span>;
  const r = call.resolution;
  const msg =
    r === "overridden" ? "Allowed once by you. Sent." :
    r === "approved" ? "You allowed it. Sent." :
    r === "denied" ? "Denied. Nothing was sent." :
    r === "timeout" ? "No answer in time, so it was denied." :
    call.decision === "block" ? "Nothing was sent." : "";
  return msg ? <span className="ml-1 text-[12px] text-muted">{msg}</span> : null;
}
