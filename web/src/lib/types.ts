export type Decision = "allow" | "ask" | "block";
export type Tag = "outside" | "private" | "sends_out";
export type CallStatus = "pending" | "ran" | "blocked" | "denied" | "timeout" | "waiting";

export interface GNode {
  id: string;
  kind: "call" | "data" | "destination";
  label: string;
  step?: number;
  tool?: string;
  tags?: Tag[];
  decision?: Decision | null;
  reason?: string | null;
  resolution?: string | null;
  preview?: string;
  chars?: number;
  trusted?: boolean;
}

export interface GEdge {
  id: string;
  source: string;
  target: string;
  type: "PRODUCED" | "FED_INTO" | "SENT_TO";
  how?: "context" | "content" | "similar";
  score?: number;
}

export interface Source {
  call_id: string;
  step: number;
  tool: string;
  label: string;
  outside: boolean;
  private: boolean;
  chain: string[];
}

export interface CallItem {
  kind: "call";
  id: string;
  step: number;
  tool: string;
  label?: string;
  args: Record<string, unknown>;
  at?: string;
  tags?: Tag[];
  decision?: Decision | null;
  reason?: string | null;
  resolution?: string | null;
  path?: string[] | null;
  output?: string | null;
  status: CallStatus;
  check_ms?: number;
  sources?: Source[];
  untrusted?: string[];
}

export interface MessageItem {
  kind: "message";
  role: "user" | "agent" | "error";
  text: string;
  at?: string;
}

export type TimelineItem = CallItem | MessageItem;

export interface SessionInfo {
  id: string;
  title: string;
  mode: "scripted" | "live" | "proxy";
  lineage: "strict" | "precise";
  scenario?: string | null;
  started_at: string;
  steps?: number;
  blocks?: number;
  asks?: number;
  running?: boolean;
}

export interface Snapshot {
  session: SessionInfo;
  timeline: (TimelineItem & Record<string, unknown>)[];
  pending: string[];
  running: boolean;
  live: boolean;
  graph: { nodes: GNode[]; edges: GEdge[] };
}

export interface Scenario {
  id: string;
  title: string;
  description: string;
  user: string;
  lineage?: "strict" | "precise" | null;
}

export interface Config {
  mode: "scripted" | "live";
  lineage: "strict" | "precise";
  live_available: boolean;
  trusted: string[];
  store_path: string;
  ask_timeout: number;
}

export interface ServerEvent {
  type: string;
  session?: string;
  seq?: number;
  data: any; // eslint-disable-line @typescript-eslint/no-explicit-any
}

export interface CypherResult {
  columns: string[];
  rows: Record<string, unknown>[];
  truncated: boolean;
}
