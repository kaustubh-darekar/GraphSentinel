import { Play, ShieldCheck } from "lucide-react";
import { Button } from "./ui";

export function EmptyState({ onRunDemo }: { onRunDemo: () => void }) {
  return (
    <div className="flex flex-1 items-center justify-center px-8">
      <div className="max-w-[460px] text-center">
        <div className="mx-auto grid h-12 w-12 place-items-center rounded-xl bg-accent/10">
          <ShieldCheck size={24} className="text-accent" />
        </div>
        <h1 className="mt-5 text-[20px] font-semibold tracking-tight">Watch an agent get stopped before it leaks</h1>
        <p className="mt-2 text-[14px] leading-relaxed text-muted">
          A poisoned email tells the agent to send salaries.xlsx outside. GraphSentinel traces the data
          through a Relate graph and blocks the send, with the path as the reason.
        </p>
        <Button variant="primary" size="lg" className="mt-6" onClick={onRunDemo}>
          <Play size={14} /> Run the poisoned email demo
        </Button>
        <p className="mt-3 text-[12px] text-muted">or pick another scenario on the left</p>
      </div>
    </div>
  );
}
