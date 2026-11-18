import type { Config, CypherResult, Scenario, SessionInfo, Snapshot } from "./types";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* not JSON */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json() as Promise<T>;
}

export const api = {
  config: () => req<Config>("/config"),
  setLineage: (lineage: "strict" | "precise") =>
    req<Config>("/config", { method: "PUT", body: JSON.stringify({ lineage }) }),
  scenarios: () => req<Scenario[]>("/scenarios"),
  sessions: () => req<SessionInfo[]>("/sessions"),
  clearHistory: () => req<{ deleted: number; kept: number }>("/sessions", { method: "DELETE" }),
  session: (id: string) => req<Snapshot>(`/sessions/${id}`),
  runScenario: (scenario: string, lineage?: string) =>
    req<{ id: string }>("/sessions", { method: "POST", body: JSON.stringify({ scenario, lineage }) }),
  startLive: (message: string, lineage?: string) =>
    req<{ id: string }>("/sessions", { method: "POST", body: JSON.stringify({ message, lineage }) }),
  sendMessage: (id: string, text: string) =>
    req<unknown>(`/sessions/${id}/messages`, { method: "POST", body: JSON.stringify({ text }) }),
  decide: (callId: string, decision: "allow" | "deny" | "allow_once") =>
    req<unknown>(`/calls/${callId}/decision`, { method: "POST", body: JSON.stringify({ decision }) }),
  cypher: (query: string, params?: Record<string, unknown>) =>
    req<CypherResult>("/cypher", { method: "POST", body: JSON.stringify({ query, params }) }),
  exportUrl: (id: string) => `/api/sessions/${id}/export`,
};

export function wsUrl(path: string): string {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}/api${path}`;
}
