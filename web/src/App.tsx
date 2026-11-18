import { SquareTerminal, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Chat } from "./components/Chat";
import { CommandPalette } from "./components/CommandPalette";
import { Composer } from "./components/Composer";
import { CypherDrawer } from "./components/CypherDrawer";
import { EmptyState } from "./components/EmptyState";
import { GraphPanel } from "./components/GraphPanel";
import { Sidebar } from "./components/Sidebar";
import { Button, Chip, Segmented, TagLegend, modKey, type ChipTone } from "./components/ui";
import { api } from "./lib/api";
import { useHotkey, useSessionList, useSessionStream } from "./lib/hooks";
import { pathElements } from "./lib/session";
import type { CallItem, Config, Scenario } from "./lib/types";

const DEMO = "01_poisoned_email";

function loadWidth(): number {
  try {
    return Number(localStorage.getItem("gs.graphWidth")) || 50;
  } catch {
    return 50;
  }
}

export default function App() {
  const [config, setConfig] = useState<Config | null>(null);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [sessions, refreshSessions] = useSessionList();
  const [selected, setSelected] = useState<string | null>(null);
  const [pathFor, setPathFor] = useState<string | null>(null);
  const [palette, setPalette] = useState(false);
  const [console_, setConsole] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [graphWidth, setGraphWidth] = useState(loadWidth);
  const state = useSessionStream(selected);

  useEffect(() => {
    api.config().then(setConfig).catch((e) => setError(`API not reachable: ${e.message}`));
    api.scenarios().then(setScenarios).catch(() => undefined);
  }, []);

  useEffect(() => setPathFor(null), [selected]);

  const fail = (e: unknown) => setError((e as Error).message);

  const runScenario = useCallback(async (id: string) => {
    try {
      const { id: sid } = await api.runScenario(id);
      setSelected(sid);
      refreshSessions();
    } catch (e) {
      fail(e);
    }
  }, [refreshSessions]);

  const setLineage = async (l: "strict" | "precise") => {
    try {
      setConfig(await api.setLineage(l));
    } catch (e) {
      fail(e);
    }
  };

  const clearHistory = async () => {
    try {
      const { kept } = await api.clearHistory();
      if (!kept) setSelected(null);
      refreshSessions();
    } catch (e) {
      fail(e);
    }
  };

  const decide = async (callId: string, d: "allow" | "deny" | "allow_once") => {
    try {
      await api.decide(callId, d);
    } catch (e) {
      fail(e);
    }
  };

  const sendLive = async (text: string) => {
    try {
      if (selected && state.live) await api.sendMessage(selected, text);
      else {
        const { id } = await api.startLive(text);
        setSelected(id);
        refreshSessions();
      }
    } catch (e) {
      fail(e);
    }
  };

  useHotkey("k", useCallback(() => setPalette((o) => !o), []));
  useHotkey("j", useCallback(() => setConsole((o) => !o), []));
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setPathFor(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const pathCall = state.items.find((i): i is CallItem => i.kind === "call" && i.id === pathFor);
  const highlight = useMemo(
    () => (pathCall?.path?.length ? pathElements(pathCall.path, state.edges, pathCall.id) : null),
    [pathCall?.path, pathCall?.id, state.edges],
  );

  const liveOk = !!config?.live_available;
  const composerHint = selected && state.live ? "Reply to the agent…" : "Ask the live agent, e.g. Summarise my unread emails";
  const status = sessionStatus(state);

  return (
    <div className="flex h-full bg-bg text-text">
      <Sidebar
        config={config}
        sessions={sessions}
        scenarios={scenarios}
        selectedId={selected}
        onSelect={setSelected}
        onRunScenario={runScenario}
        onOpenPalette={() => setPalette(true)}
        onClearHistory={clearHistory}
      />

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-4 border-b border-border bg-surface px-6">
          <div className="flex min-w-0 flex-1 items-center gap-3">
            <h2 className="truncate text-[15px] font-semibold">{state.info?.title ?? "No run selected"}</h2>
            {status && <Chip tone={status.tone}>{status.text}</Chip>}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[12px] text-muted">Lineage</span>
            <Segmented
              title="Lineage for new runs: strict counts everything the agent has seen; precise counts copied or similar content only"
              value={config?.lineage ?? "strict"}
              options={["strict", "precise"] as const as unknown as ("strict" | "precise")[]}
              onChange={setLineage}
            />
          </div>
          <Button onClick={() => setConsole((o) => !o)} title={`Cypher console (${modKey}+J)`}>
            <SquareTerminal size={14} /> Console
          </Button>
        </header>

        {error && (
          <div className="flex items-center justify-between border-b border-sendsout/25 bg-sendsout/[0.06] px-6 py-2 text-[13px] text-sendsout">
            {error}
            <button onClick={() => setError(null)} className="text-[12px] text-muted hover:text-text">Dismiss</button>
          </div>
        )}

        <div className="flex min-h-0 flex-1">
          <div className="flex min-w-[360px] flex-1 flex-col">
            {selected ? (
              <Chat
                state={state}
                activePath={pathFor}
                onShowPath={(c) => setPathFor((p) => (p === c.id ? null : c.id))}
                onDecide={decide}
              />
            ) : (
              <EmptyState onRunDemo={() => runScenario(DEMO)} />
            )}
            {liveOk && <Composer placeholder={composerHint} disabled={state.running} onSend={sendLive} />}
          </div>

          <ResizeHandle width={graphWidth} onChange={setGraphWidth} />

          <section style={{ width: `${graphWidth}%` }} className="flex min-w-[320px] flex-col bg-surface">
            <header className="flex h-12 shrink-0 items-center gap-3 border-b border-border px-4">
              <span className="text-[13px] font-medium">Lineage graph</span>
              {pathCall && (
                <button onClick={() => setPathFor(null)} title="Clear the path (Esc)">
                  <Chip tone="block">
                    Path for step {pathCall.step} <X size={12} />
                  </Chip>
                </button>
              )}
              <span className="ml-auto"><TagLegend /></span>
            </header>
            <GraphPanel
              nodes={state.nodes}
              edges={state.edges}
              lastCheckMs={state.lastCheckMs}
              highlight={highlight}
              onClearHighlight={() => setPathFor(null)}
            />
          </section>
        </div>

        {console_ && <CypherDrawer sessionId={selected} onClose={() => setConsole(false)} />}
      </main>

      <CommandPalette
        open={palette}
        onOpenChange={setPalette}
        scenarios={scenarios}
        config={config}
        sessionId={selected}
        onRunScenario={runScenario}
        onSetLineage={setLineage}
        onOpenConsole={() => setConsole(true)}
        onClearHistory={clearHistory}
      />
    </div>
  );
}

function ResizeHandle({ width, onChange }: { width: number; onChange: (w: number) => void }) {
  const dragging = useRef(false);
  useEffect(() => {
    const move = (e: MouseEvent) => {
      if (!dragging.current) return;
      const pct = ((window.innerWidth - e.clientX) / (window.innerWidth - 240)) * 100;
      onChange(Math.min(70, Math.max(25, pct)));
    };
    const up = () => {
      if (!dragging.current) return;
      dragging.current = false;
      document.body.style.cursor = "";
      try {
        localStorage.setItem("gs.graphWidth", String(width));
      } catch {
        /* storage unavailable */
      }
    };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
    return () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    };
  }, [onChange, width]);
  return (
    <div
      onMouseDown={() => {
        dragging.current = true;
        document.body.style.cursor = "col-resize";
      }}
      className="w-[5px] shrink-0 cursor-col-resize border-l border-border bg-transparent transition-colors hover:border-accent hover:bg-accent/20"
      title="Drag to resize"
    />
  );
}

/** One short status for the open run. */
function sessionStatus(state: ReturnType<typeof useSessionStream>): { tone: ChipTone; text: string } | null {
  if (!state.info) return null;
  const calls = state.items.filter((i): i is CallItem => i.kind === "call");
  const blocks = calls.filter((c) => c.decision === "block").length;
  if (state.pending.length) return { tone: "ask", text: "Needs your approval" };
  if (state.running) return { tone: "accent", text: "Running" };
  if (blocks) return { tone: "block", text: blocks === 1 ? "1 send blocked" : `${blocks} sends blocked` };
  if (calls.some((c) => c.decision === "ask")) return { tone: "ask", text: "Asked before sending" };
  return calls.length ? { tone: "allow", text: "No leaks" } : null;
}
