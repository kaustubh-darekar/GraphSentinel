import { Command } from "cmdk";
import { Download, GitBranch, Play, SquareTerminal, Trash2 } from "lucide-react";
import type { Config, Scenario } from "../lib/types";

interface Props {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  scenarios: Scenario[];
  config: Config | null;
  sessionId: string | null;
  onRunScenario: (id: string) => void;
  onSetLineage: (l: "strict" | "precise") => void;
  onOpenConsole: () => void;
  onClearHistory: () => void;
}

export function CommandPalette(p: Props) {
  const go = (fn: () => void) => () => {
    p.onOpenChange(false);
    fn();
  };
  return (
    <Command.Dialog open={p.open} onOpenChange={p.onOpenChange} label="Command palette" className="cmdk-dialog">
      <Command.Input placeholder="Run a scenario, switch lineage mode, open the console…" />
      <Command.List>
        <Command.Empty>No matches.</Command.Empty>
        <Command.Group heading="Scenarios">
          {p.scenarios.map((s) => (
            <Command.Item key={s.id} value={`run ${s.title}`} onSelect={go(() => p.onRunScenario(s.id))}>
              <Play size={13} /> Run: {s.title}
            </Command.Item>
          ))}
        </Command.Group>
        <Command.Group heading="Lineage">
          {(["strict", "precise"] as const).map((l) => (
            <Command.Item key={l} value={`lineage ${l}`} onSelect={go(() => p.onSetLineage(l))}>
              <GitBranch size={13} /> Switch to {l} lineage
              {p.config?.lineage === l && <span className="ml-auto text-[11px] text-muted">current</span>}
            </Command.Item>
          ))}
        </Command.Group>
        <Command.Group heading="Tools">
          <Command.Item value="open cypher console" onSelect={go(p.onOpenConsole)}>
            <SquareTerminal size={13} /> Open Cypher console
          </Command.Item>
          <Command.Item value="clear history delete all runs" onSelect={go(p.onClearHistory)}>
            <Trash2 size={13} /> Clear history (delete all finished runs)
          </Command.Item>
          {p.sessionId && (
            <Command.Item
              value="export session json"
              onSelect={go(() => window.open(`/api/sessions/${p.sessionId}/export`, "_blank"))}
            >
              <Download size={13} /> Export session as JSON
            </Command.Item>
          )}
        </Command.Group>
      </Command.List>
    </Command.Dialog>
  );
}
