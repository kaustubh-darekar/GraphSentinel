import { Play, X } from "lucide-react";
import { useState } from "react";
import { api } from "../lib/api";
import { PRESETS } from "../lib/presets";
import type { CypherResult } from "../lib/types";
import { Button, Kbd, modKey } from "./ui";

interface Props {
  sessionId: string | null;
  onClose: () => void;
}

export function CypherDrawer({ sessionId, onClose }: Props) {
  const [query, setQuery] = useState(PRESETS[0].query);
  const [result, setResult] = useState<CypherResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ms, setMs] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async (q = query) => {
    setBusy(true);
    setError(null);
    const t0 = performance.now();
    try {
      setResult(await api.cypher(q, sessionId ? { session: sessionId } : {}));
      setMs(performance.now() - t0);
    } catch (e) {
      setResult(null);
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex h-[320px] shrink-0 flex-col border-t border-border bg-surface">
      <div className="flex h-11 items-center gap-3 border-b border-border px-4">
        <span className="text-[13px] font-medium">Cypher console</span>
        <span className="text-[12px] text-muted">read-only, live graph{sessionId ? ", $session = open session" : ""}</span>
        <div className="ml-auto flex items-center gap-2">
          <select
            className="h-8 rounded-md border border-border bg-surface px-2 text-[13px] text-text outline-none"
            value=""
            onChange={(e) => {
              const p = PRESETS[Number(e.target.value)];
              if (p) {
                setQuery(p.query);
                run(p.query);
              }
            }}
          >
            <option value="" disabled>Preset queries</option>
            {PRESETS.map((p, i) => (
              <option key={p.title} value={i} disabled={p.needsSession && !sessionId}>{p.title}</option>
            ))}
          </select>
          <Button variant="primary" onClick={() => run()} disabled={busy}>
            <Play size={11} /> Run <Kbd>{modKey}↵</Kbd>
          </Button>
          <button onClick={onClose} className="p-1 text-muted hover:text-text" title="Close"><X size={14} /></button>
        </div>
      </div>
      <div className="flex min-h-0 flex-1">
        <textarea
          value={query}
          spellCheck={false}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
              e.preventDefault();
              run();
            }
          }}
          className="w-[42%] resize-none border-r border-border bg-bg p-3 font-mono text-[12.5px] leading-relaxed text-text outline-none"
        />
        <div className="min-w-0 flex-1 overflow-auto">
          {error && <div className="p-3 font-mono text-[12.5px] text-sendsout">{error}</div>}
          {result && <ResultTable result={result} ms={ms} />}
          {!error && !result && <div className="p-3 text-[12px] text-muted">Pick a preset or write a query.</div>}
        </div>
      </div>
    </div>
  );
}

function cell(v: unknown): string {
  if (v == null) return "null";
  return typeof v === "string" ? v : JSON.stringify(v);
}

function ResultTable({ result, ms }: { result: CypherResult; ms: number | null }) {
  return (
    <div>
      <div className="sticky top-0 border-b border-border bg-surface px-3 py-1 text-[12px] text-muted">
        {result.rows.length} row{result.rows.length === 1 ? "" : "s"}
        {result.truncated && " (truncated)"}
        {ms != null && ` · ${ms.toFixed(0)} ms round trip`}
      </div>
      <table className="w-full border-collapse font-mono text-[12px]">
        <thead>
          <tr>
            {result.columns.map((c) => (
              <th key={c} className="border-b border-border px-3 py-1.5 text-left font-medium text-muted">{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {result.rows.map((r, i) => (
            <tr key={i} className="hover:bg-surface-2">
              {result.columns.map((c) => (
                <td key={c} className="max-w-[360px] truncate border-b border-border/60 px-3 py-1 align-top" title={cell(r[c])}>
                  {cell(r[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
