import cytoscape, { type Core, type ElementDefinition, type EventObject } from "cytoscape";
import dagre from "cytoscape-dagre";
import { Maximize2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { T } from "../lib/tokens";
import type { GEdge, GNode } from "../lib/types";

cytoscape.use(dagre);

interface Props {
  nodes: Record<string, GNode>;
  edges: Record<string, GEdge>;
  highlight: { nodeIds: Set<string>; edgeIds: Set<string> } | null;
  lastCheckMs?: number | null;
  onClearHighlight: () => void;
}

type Hover = { kind: "node"; node: GNode } | { kind: "edge"; edge: GEdge } | null;

const STYLE: cytoscape.StylesheetJson = [
  {
    selector: "node",
    style: {
      "font-family": "Inter Variable, Inter, sans-serif",
      color: T.text,
      "text-wrap": "wrap",
      "transition-property": "opacity, border-color, background-color",
      "transition-duration": 150,
      "transition-timing-function": "ease-out",
    },
  },
  {
    selector: "node.call",
    style: {
      shape: "round-rectangle",
      width: "data(w)",
      height: "data(h)",
      "background-color": T.surface2,
      "border-width": 1,
      "border-color": T.border,
      label: "data(display)",
      "font-size": 12,
      "text-valign": "center",
      "text-halign": "center",
      "text-max-width": "200px",
      "line-height": 1.35,
    },
  },
  { selector: "node.call.outside", style: { "border-color": T.outside, "border-width": 1.5 } },
  { selector: "node.call.private", style: { "border-color": T.private, "border-width": 1.5 } },
  {
    selector: "node.call.outside.private",
    style: { "border-color": T.outside, "outline-color": T.private, "outline-width": 1.5, "outline-offset": 2 },
  },
  { selector: "node.call.sends_out", style: { "border-color": T.sendsout, "border-width": 1.5 } },
  { selector: "node.call.block", style: { "background-color": "#FDECE7" } },
  { selector: "node.call.ask", style: { "background-color": "#FFF4E0" } },
  {
    selector: "node.data",
    style: {
      shape: "ellipse",
      width: 10,
      height: 10,
      "background-color": "#A9B6C6",
    },
  },
  {
    selector: "node.destination",
    style: {
      shape: "round-rectangle",
      width: "data(w)",
      height: 24,
      "background-color": T.surface,
      "border-width": 1,
      "border-color": T.sendsout,
      "border-style": "dashed",
      label: "data(display)",
      "font-family": "JetBrains Mono, monospace",
      "font-size": 11,
      "text-valign": "center",
    },
  },
  { selector: "node.destination.trusted", style: { "border-color": T.allow, "border-style": "solid" } },
  {
    selector: "edge",
    style: {
      width: 1,
      "curve-style": "bezier",
      "line-color": "#B8C4D2",
      "target-arrow-color": "#B8C4D2",
      "target-arrow-shape": "triangle",
      "arrow-scale": 0.6,
      "transition-property": "opacity, line-color, width",
      "transition-duration": 150,
      "transition-timing-function": "ease-out",
    },
  },
  { selector: "edge.FED_INTO.context", style: { "line-color": "#D3DCE6", "target-arrow-color": "#D3DCE6" } },
  { selector: "edge.FED_INTO.content", style: { "line-color": "#8796A8", "target-arrow-color": "#8796A8" } },
  {
    selector: "edge.FED_INTO.similar",
    style: {
      "line-style": "dashed",
      "line-dash-pattern": [4, 3],
      "line-color": T.accent,
      "target-arrow-color": T.accent,
      label: "data(scoreLabel)",
      "font-size": 10,
      "font-family": "JetBrains Mono, monospace",
      color: T.accent,
      "text-background-color": T.surface,
      "text-background-opacity": 1,
      "text-background-padding": "2px",
    },
  },
  { selector: "edge.SENT_TO", style: { "line-color": "#F0B3A2", "target-arrow-color": "#F0B3A2" } },
  { selector: ".new", style: { opacity: 0 } },
  { selector: ".dim", style: { opacity: 0.3 } },
  {
    selector: "node.hl",
    style: {
      "border-color": T.sendsout,
      "border-width": 2,
      "underlay-color": T.sendsout,
      "underlay-opacity": 0.18,
      "underlay-padding": 6,
      "underlay-shape": "round-rectangle",
    },
  },
  { selector: "node.data.hl", style: { "background-color": T.sendsout, "underlay-shape": "ellipse" } },
  {
    selector: "edge.hl",
    style: { "line-color": T.sendsout, "target-arrow-color": T.sendsout, width: 2, "z-index": 10 },
  },
  // A paraphrase match stays dashed and keeps its score when it is part of the path.
  { selector: "edge.similar.hl", style: { "line-style": "dashed", color: T.sendsout } },
];

function toElement(item: GNode | GEdge): ElementDefinition {
  if ("source" in item) {
    const e = item as GEdge;
    const classes = [e.type, e.how ?? ""].join(" ");
    return {
      group: "edges",
      data: { ...e, scoreLabel: e.score != null ? `similar ${e.score.toFixed(2)}` : "" },
      classes,
    };
  }
  const n = item as GNode;
  const display =
    n.kind === "call" ? `${n.step}. ${n.tool}\n${trim(n.label, 26)}` :
    n.kind === "data" ? trim(n.label, 30) : n.label;
  const classes = [n.kind, ...(n.tags ?? []), n.decision ?? "", n.trusted ? "trusted" : ""].join(" ");
  const lines = display.split("\n");
  const longest = Math.max(...lines.map((l) => l.length));
  const w = Math.max(44, Math.round(longest * (n.kind === "destination" ? 7.2 : 6.6) + (n.kind === "destination" ? 28 : 22)));
  const h = Math.round(lines.length * 16 + 16);
  return { group: "nodes", data: { ...n, display, w, h }, classes };
}

/** Fit the graph, but never zoom in past 1.2x (a two-node graph should not fill the panel). */
function fitCapped(c: Core, eles?: cytoscape.Collection, padding = 28) {
  c.fit(eles, padding);
  if (c.zoom() > 1.3) {
    c.zoom(1.3);
    c.center(eles);
  }
}

function trim(s: string, n: number) {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

export function GraphPanel({ nodes, edges, highlight, lastCheckMs, onClearHighlight }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const cy = useRef<Core | null>(null);
  const layout = useRef<cytoscape.Layouts | null>(null);
  const highlightRef = useRef(highlight);
  highlightRef.current = highlight;
  const [hover, setHover] = useState<Hover>(null);

  useEffect(() => {
    const c = cytoscape({
      container: box.current,
      style: STYLE,
      minZoom: 0.25,
      maxZoom: 2.5,
      boxSelectionEnabled: false,
      autoungrabify: false,
    });
    c.on("mouseover", "node", (e: EventObject) => setHover({ kind: "node", node: e.target.data() }));
    c.on("mouseover", "edge", (e: EventObject) => setHover({ kind: "edge", edge: e.target.data() }));
    c.on("mouseout", "node, edge", () => setHover(null));
    c.on("tap", (e: EventObject) => {
      if (e.target === c) onClearHighlight();
    });
    cy.current = c;
    (window as unknown as { __gsGraph?: Core }).__gsGraph = c; // for end-to-end checks
    const ro = new ResizeObserver(() => {
      c.resize();
      if (c.elements().empty()) return;
      const hl = c.elements(".hl");
      if (hl.nonempty()) fitCapped(c, hl, 40);
      else fitCapped(c);
    });
    if (box.current) ro.observe(box.current);
    return () => {
      ro.disconnect();
      c.destroy();
      cy.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Sync elements: add new ones (fading in), update changed ones, drop removed ones.
  useEffect(() => {
    const c = cy.current;
    if (!c) return;
    const wanted = new Map<string, ElementDefinition>();
    Object.values(nodes).forEach((n) => wanted.set(n.id, toElement(n)));
    Object.values(edges).forEach((e) => {
      if (nodes[e.source] && nodes[e.target]) wanted.set(e.id, toElement(e));
    });
    let added = 0;
    c.batch(() => {
      c.elements().forEach((el) => {
        if (!wanted.has(el.id())) el.remove();
      });
      wanted.forEach((def, id) => {
        const el = c.getElementById(id);
        if (el.nonempty()) {
          el.data(def.data);
          el.classes(def.classes as string);
        } else {
          c.add({ ...def, classes: `${def.classes} new` });
          added++;
        }
      });
    });
    if (added) {
      // Positions are computed at once (no competing animated layouts); new elements fade in.
      layout.current?.stop();
      layout.current = c.layout({
        name: "dagre", rankDir: "TB", nodeSep: 28, rankSep: 18, edgeSep: 10, animate: false, fit: false,
      } as cytoscape.LayoutOptions);
      layout.current.run();
      if (!highlightRef.current) fitCapped(c);
      requestAnimationFrame(() => c.elements(".new").removeClass("new"));
    }
  }, [nodes, edges]);

  // Highlight the path and dim everything else.
  useEffect(() => {
    const c = cy.current;
    if (!c) return;
    c.batch(() => {
      c.elements().removeClass("hl dim");
      if (!highlight) return;
      c.nodes().forEach((n) => {
        n.addClass(highlight.nodeIds.has(n.id()) ? "hl" : "dim");
      });
      c.edges().forEach((e) => {
        e.addClass(highlight.edgeIds.has(e.id()) ? "hl" : "dim");
      });
    });
    if (highlight && highlight.nodeIds.size) fitCapped(c, c.elements(".hl"), 40);
    else if (c.elements().nonempty()) fitCapped(c);
  }, [highlight, nodes, edges]);

  const empty = Object.keys(nodes).length === 0;
  return (
    <div className="relative min-h-0 flex-1">
      <div ref={box} className="absolute inset-0" />
      {empty && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center px-8 text-center text-[13px] text-muted">
          Every tool call and piece of data appears here as the agent works.
        </div>
      )}
      {!empty && (
        <div className="pointer-events-none absolute bottom-3 right-4 text-[12px] text-muted">
          {Object.keys(nodes).length} nodes · {Object.keys(edges).length} edges
          {lastCheckMs != null && ` · last check ${lastCheckMs.toFixed(1)} ms`}
        </div>
      )}
      <button
        title="Fit graph"
        onClick={() => cy.current && fitCapped(cy.current)}
        className="absolute right-4 top-3 rounded-md border border-border bg-surface p-2 text-muted hover:text-text"
      >
        <Maximize2 size={14} />
      </button>
      {hover && <Inspector hover={hover} />}
    </div>
  );
}

function Inspector({ hover }: { hover: NonNullable<Hover> }) {
  return (
    <div className="pointer-events-none absolute bottom-3 left-4 max-w-[65%] rounded-lg border border-border bg-surface px-3 py-2 text-[12px] shadow-[0_4px_16px_rgb(14_26_43/0.08)]">
      {hover.kind === "edge" ? (
        <div className="font-mono">
          {hover.edge.type}
          {hover.edge.how && <span className="text-muted"> how: {hover.edge.how}</span>}
          {hover.edge.score != null && <span className="text-accent"> score: {hover.edge.score.toFixed(3)}</span>}
        </div>
      ) : hover.node.kind === "data" ? (
        <>
          <div className="mb-1 text-muted">Data · {hover.node.chars} chars</div>
          <div className="line-clamp-4 whitespace-pre-wrap font-mono text-[12px] text-text/85">{hover.node.preview}</div>
        </>
      ) : hover.node.kind === "destination" ? (
        <div>
          <span className="font-mono">{hover.node.label}</span>
          <span className={hover.node.trusted ? "text-allow" : "text-sendsout"}>
            {hover.node.trusted ? "  trusted" : "  not trusted"}
          </span>
        </div>
      ) : (
        <>
          <div>
            <span className="font-medium">{hover.node.step}. {hover.node.tool}</span>
            <span className="ml-2 font-mono text-muted">{hover.node.label}</span>
          </div>
          {hover.node.reason && <div className="mt-1 text-muted">{hover.node.reason}</div>}
        </>
      )}
    </div>
  );
}
