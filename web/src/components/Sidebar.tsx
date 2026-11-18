import { useState } from "react";
import type { Config, Scenario, SessionInfo } from "../lib/types";
import { Kbd, modKey } from "./ui";

interface Props {
  config: Config | null;
  sessions: SessionInfo[];
  scenarios: Scenario[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onRunScenario: (id: string) => void;
  onOpenPalette: () => void;
  onClearHistory: () => void;
}

const RECENT = 8;

function statusDot(s: SessionInfo) {
  if (s.running) return "bg-accent";
  if (s.blocks) return "bg-sendsout";
  if (s.asks) return "bg-ask";
  return "bg-allow";
}

function ago(iso: string) {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "now";
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return new Date(iso).toLocaleDateString([], { month: "short", day: "numeric" });
}

export function Sidebar({
  config, sessions, scenarios, selectedId, onSelect, onRunScenario, onOpenPalette, onClearHistory,
}: Props) {
  const [all, setAll] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const shown = all ? sessions : sessions.slice(0, RECENT);
  return (
    <aside className="flex w-[264px] shrink-0 flex-col border-r border-border bg-surface">
      <div className="flex items-center gap-3 px-5 pb-4 pt-5">
        <img src="/favicon.svg" alt="" className="h-9 w-9 shrink-0" />
        <div className="min-w-0">
          <div className="text-[14px] font-semibold leading-tight">GraphSentinel</div>
          <div className="text-[12px] text-muted">See the connections, Stop the threats.</div>
        </div>
      </div>

      <nav className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">
        <Heading>Run a scenario</Heading>
        <div className="space-y-0.5">
          {scenarios.map((s) => (
            <button
              key={s.id}
              onClick={() => onRunScenario(s.id)}
              className="block w-full rounded-md px-3 py-2 text-left transition-colors hover:bg-surface-2"
            >
              <span className="flex items-center gap-2">
                <span className="truncate text-[13px] font-medium">{s.title}</span>
                {s.lineage && (
                  <span className="rounded-full bg-accent/10 px-2 text-[11px] font-medium text-accent">{s.lineage}</span>
                )}
              </span>
              <span className="mt-0.5 block truncate text-[12px] text-muted">{s.description}</span>
            </button>
          ))}
        </div>

        <div className="mb-1.5 mt-6 flex items-center justify-between px-3">
          <span className="text-[12px] font-medium text-muted">Recent runs</span>
          {sessions.length > 0 && !confirming && (
            <button onClick={() => setConfirming(true)} className="text-[12px] text-muted hover:text-sendsout">
              Clear history
            </button>
          )}
        </div>
        {confirming && (
          <div className="mx-1 mb-2 rounded-md border border-border bg-surface-2 px-3 py-2.5">
            <p className="text-[12px] text-text">Delete all {sessions.length} runs from the graph?</p>
            <div className="mt-2 flex gap-2">
              <button
                onClick={() => {
                  setConfirming(false);
                  onClearHistory();
                }}
                className="rounded-md bg-sendsout px-2.5 py-1 text-[12px] font-medium text-white hover:brightness-110"
              >
                Delete runs
              </button>
              <button onClick={() => setConfirming(false)} className="rounded-md px-2.5 py-1 text-[12px] text-muted hover:text-text">
                Cancel
              </button>
            </div>
          </div>
        )}
        {sessions.length === 0 && <p className="px-3 text-[12px] text-muted">Runs you start appear here.</p>}
        <div className="space-y-0.5">
          {shown.map((s) => (
            <button
              key={s.id}
              onClick={() => onSelect(s.id)}
              className={`flex w-full items-center gap-2.5 rounded-md px-3 py-1.5 text-left text-[13px] transition-colors ${
                s.id === selectedId ? "bg-accent/10 text-text" : "text-text/80 hover:bg-surface-2"
              }`}
            >
              <span className={`h-2 w-2 shrink-0 rounded-full ${statusDot(s)}`} />
              <span className="min-w-0 flex-1 truncate">{s.title}</span>
              <span className="shrink-0 text-[12px] text-muted">{ago(s.started_at)}</span>
            </button>
          ))}
        </div>
        {sessions.length > RECENT && (
          <button onClick={() => setAll((a) => !a)} className="mt-1 px-3 text-[12px] text-accent hover:underline">
            {all ? "Show fewer" : `Show all ${sessions.length}`}
          </button>
        )}
      </nav>

      <div className="flex items-center justify-between border-t border-border px-5 py-3">
        <span className="text-[12px] text-muted">
          {config ? `${config.mode === "live" ? "Live" : "Scripted"} mode` : "Connecting…"}
          {config?.live_available && config.mode !== "live" ? " · live ready" : ""}
        </span>
        <button onClick={onOpenPalette} className="flex items-center gap-1 text-muted hover:text-text" title="Commands">
          <Kbd>{modKey}</Kbd>
          <Kbd>K</Kbd>
        </button>
      </div>
    </aside>
  );
}

function Heading({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`mb-1.5 px-3 text-[12px] font-medium text-muted ${className}`}>{children}</div>;
}
