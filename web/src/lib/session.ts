import type { CallItem, CallStatus, GEdge, GNode, MessageItem, ServerEvent, SessionInfo, Snapshot, TimelineItem } from "./types";

export interface SessionState {
  info: SessionInfo | null;
  items: TimelineItem[];
  nodes: Record<string, GNode>;
  edges: Record<string, GEdge>;
  pending: string[];
  running: boolean;
  live: boolean;
  lastCheckMs: number | null;
}

export const emptySession: SessionState = {
  info: null, items: [], nodes: {}, edges: {}, pending: [], running: false, live: false, lastCheckMs: null,
};

function statusFromSnapshot(c: Record<string, unknown>): CallStatus {
  if (c.output != null) return "ran";
  if (c.decision === "block") return "blocked";
  if (c.decision === "ask") {
    if (c.resolution === "timeout") return "timeout";
    if (c.resolution === "denied") return "denied";
    return "waiting";
  }
  return "pending";
}

function fromSnapshot(s: Snapshot): SessionState {
  const nodes: Record<string, GNode> = {};
  const edges: Record<string, GEdge> = {};
  s.graph.nodes.forEach((n) => (nodes[n.id] = n));
  s.graph.edges.forEach((e) => (edges[e.id] = e));
  const items: TimelineItem[] = s.timeline.map((t) =>
    t.kind === "call"
      ? ({ ...(t as unknown as CallItem), tags: nodes[t.id as string]?.tags, status: statusFromSnapshot(t) } as CallItem)
      : ({ kind: "message", role: t.role, text: t.text, at: t.at } as MessageItem),
  );
  return { info: s.session, items, nodes, edges, pending: s.pending, running: s.running, live: s.live, lastCheckMs: null };
}

function updateCall(state: SessionState, id: string, patch: Partial<CallItem>): TimelineItem[] {
  return state.items.map((it) => (it.kind === "call" && it.id === id ? { ...it, ...patch } : it));
}

function addMessage(state: SessionState, m: MessageItem): SessionState {
  const dup = state.items.some(
    (it) => it.kind === "message" && it.role === m.role && it.text === m.text && (!m.at || !it.at || it.at === m.at),
  );
  return dup ? state : { ...state, items: [...state.items, m] };
}

export function reduce(state: SessionState, ev: ServerEvent): SessionState {
  const d = ev.data ?? {};
  switch (ev.type) {
    case "snapshot_reset":
      return emptySession;
    case "snapshot":
      return fromSnapshot(d as Snapshot);
    case "session_started":
      return { ...state, running: true };
    case "user_message":
      return addMessage(state, { kind: "message", role: "user", text: d.text, at: d.at });
    case "agent_message":
      return addMessage(state, { kind: "message", role: "agent", text: d.text, at: d.at });
    case "error":
      return addMessage(state, { kind: "message", role: "error", text: d.message });
    case "call_recorded": {
      if (state.items.some((it) => it.kind === "call" && it.id === d.call_id)) return state;
      const call: CallItem = {
        kind: "call", id: d.call_id, step: d.step, tool: d.tool, args: d.args,
        label: d.node?.label, tags: d.node?.tags, status: "pending",
      };
      return { ...state, running: true, items: [...state.items, call] };
    }
    case "graph_delta": {
      const nodes = { ...state.nodes };
      const edges = { ...state.edges };
      (d.nodes as GNode[]).forEach((n) => (nodes[n.id] = { ...nodes[n.id], ...n }));
      (d.edges as GEdge[]).forEach((e) => (edges[e.id] = e));
      return { ...state, nodes, edges };
    }
    case "verdict": {
      const nodes = { ...state.nodes };
      if (nodes[d.call_id]) nodes[d.call_id] = { ...nodes[d.call_id], decision: d.decision, reason: d.reason };
      const status: CallStatus = d.decision === "ask" ? "waiting" : d.decision === "block" ? "blocked" : "pending";
      return {
        ...state, nodes, lastCheckMs: d.check_ms,
        items: updateCall(state, d.call_id, {
          decision: d.decision, reason: d.reason, path: d.path, check_ms: d.check_ms,
          sources: d.sources, untrusted: d.untrusted, status,
        }),
      };
    }
    case "ask_pending":
      return state.pending.includes(d.call_id) ? state : { ...state, pending: [...state.pending, d.call_id] };
    case "resolution":
      return {
        ...state, pending: state.pending.filter((p) => p !== d.call_id),
        items: updateCall(state, d.call_id, { resolution: d.resolution }),
      };
    case "call_result":
      return { ...state, items: updateCall(state, d.call_id, { status: d.status, output: d.output }) };
    case "session_idle":
    case "session_finished":
      return { ...state, running: false };
    default:
      return state;
  }
}

/** Node ids and edge ids on a verdict path (chains joined end to end), plus where the
 * checked call was about to send the data. */
export function pathElements(path: string[] | null | undefined, edges: Record<string, GEdge>, callId?: string) {
  const nodeIds = new Set(path ?? []);
  const edgeIds = new Set<string>();
  const byPair = new Map<string, string>();
  Object.values(edges).forEach((e) => byPair.set(`${e.source}|${e.target}`, e.id));
  (path ?? []).forEach((id, i, arr) => {
    if (i === 0) return;
    const e = byPair.get(`${arr[i - 1]}|${id}`);
    if (e) edgeIds.add(e);
  });
  if (callId) {
    Object.values(edges).forEach((e) => {
      if (e.type === "SENT_TO" && e.source === callId) {
        edgeIds.add(e.id);
        nodeIds.add(e.target);
      }
    });
  }
  return { nodeIds, edgeIds };
}
