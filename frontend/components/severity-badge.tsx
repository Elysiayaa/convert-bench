import { Severity } from "@/lib/badcases";

const severityStyles: Record<Severity, string> = {
  warning: "border-amber-700/70 bg-amber-500/10 text-amber-200",
  error: "border-red-700/70 bg-red-500/10 text-red-200",
  critical: "border-red-950 bg-red-950/80 text-red-100",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span className={`inline-flex rounded-full border px-2.5 py-1 font-mono text-xs font-medium ${severityStyles[severity]}`}>
      {severity}
    </span>
  );
}
