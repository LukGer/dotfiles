// Pure helpers for the ghd pi extension, tested with `node --test`.

export const CATEGORIES = ["bug", "security", "risk", "quality", "design", "completeness"] as const;
export const SEVERITIES = ["P0", "P1", "P2", "P3"] as const;
export const SPECIALISTS = ["correctness", "deep", "security", "risk", "quality", "design", "completeness"] as const;

export type Finding = {
  file: string; line: number; start_line?: number; anchor: string;
  category: string; severity: string; title: string; comment: string; detail?: string; specialist?: string;
};
export type Review = {
  tldr: string;
  findings: Finding[];
  dropped?: { candidate: string; reason: string }[];
  since_last_review?: { finding: string; status: string; note?: string }[];
  passes?: { specialist: string; status: string; note?: string }[];
  coverage_gaps?: string[];
};
export type Meta = { repo: string; pr: number | string; title: string; tool: string; model: string; sha: string };

const GIT_WRITES = /\bgit\s+(-[^\s]+\s+)*(add|am|apply|branch\s+(-[dDmM]|--delete)|checkout|cherry-pick|clean|commit|fetch|merge|mv|pull|push|rebase|reset|restore|revert|rm|stash|switch|tag\s+-d|worktree)\b/;
const FILE_WRITES = /\brm\s|\bmv\s|\btee\b|(^|[^&<>0-9])>>?(?!\s*(&|\/dev\/null))/;
const GH_WRITES = /\bgh\s+api\b(?=.*(\s--method\s+(POST|PUT|PATCH|DELETE)|\s-X\s+(POST|PUT|PATCH|DELETE)|\s-[fF]\s|\s--(raw-)?field\b|\s--input\b))|\bgh\s+(pr|issue)\s+(comment|review|edit|close|merge|create|ready|reopen|lock)\b/;
const INSTALLS = /\b(npm|pnpm|yarn|bun)\s+(install|add|i|ci|up|update)\b|\bpip3?\s+install\b|\buv\s+(run|pip|add|sync|tool)\b|\bbrew\s+install\b|\bcargo\s+install\b|\bgo\s+(install|get)\b|\bmise\s+(install|use)\b|\bcurl\b.*\|\s*(ba|z)?sh\b/;

export function blockedCommand(command: string): string | null {
  if (GIT_WRITES.test(command)) return "git state belongs to the human: the review is read-only";
  if (GH_WRITES.test(command)) return "GitHub writes belong to the human: only gh reads are allowed";
  if (INSTALLS.test(command)) return "installs and test runs belong to the human: read the code instead";
  if (FILE_WRITES.test(command)) return "files belong to the human: findings go through save_finding";
  return null;
}

export function duplicateOf(finding: { file: string; line: number }, existing: { file: string; line: number }[]): number | null {
  const index = existing.findIndex((f) => f.file === finding.file && Math.abs(f.line - finding.line) <= 2);
  return index < 0 ? null : index + 1;
}

const cell = (text: string) => text.replace(/\|/g, "\\|").replace(/\s*\n\s*/g, " ");
const pointer = (f: Finding) => `${f.file}:${f.start_line ? `${f.start_line}-` : ""}${f.line}`;
const table = (header: string[], rows: string[][]) =>
  [`| ${header.join(" | ")} |`, `| ${header.map(() => "---").join(" | ")} |`, ...rows.map((r) => `| ${r.map(cell).join(" | ")} |`)];

export function renderMarkdown(review: Review, meta: Meta): string {
  const findings = [...review.findings].sort((a, b) => SEVERITIES.indexOf(a.severity as any) - SEVERITIES.indexOf(b.severity as any));
  const lines = [`# ${meta.repo}#${meta.pr} ${meta.title}`, "", `${meta.sha.slice(0, 7)} · ${meta.tool} ${meta.model}`, "", review.tldr, "", "## Findings", ""];
  lines.push(...(findings.length
    ? table(["#", "Category", "P", "Pointer", "Comment"], findings.map((f, i) => [String(i + 1), f.category, f.severity, pointer(f), f.comment]))
    : ["No findings."]));
  const details = findings.filter((f) => f.detail);
  if (details.length) lines.push("", "## Evidence", ...details.flatMap((f) => ["", `### ${findings.indexOf(f) + 1}. ${f.title} (${pointer(f)})`, "", f.detail!]));
  if (review.since_last_review?.length) {
    lines.push("", "## Since last review", "", ...table(["Previous finding", "Status"],
      review.since_last_review.map((s) => [s.finding, s.note ? `${s.status}: ${s.note}` : s.status])));
  }
  if (review.dropped?.length) lines.push("", "## Dropped", "", ...table(["Candidate", "Reason"], review.dropped.map((d) => [d.candidate, d.reason])));
  if (review.passes?.length || review.coverage_gaps?.length) {
    lines.push("", "## Coverage", "");
    if (review.passes?.length) lines.push(review.passes.map((p) => `${p.specialist} ${p.status}${p.note ? ` (${p.note})` : ""}`).join(" · "));
    if (review.coverage_gaps?.length) lines.push("", ...review.coverage_gaps.map((g) => `- ${g}`));
  }
  return lines.join("\n") + "\n";
}

export type Usage = { turns: number; input: number; output: number; cacheRead: number; cacheWrite: number; cost: number; error?: string };

export function summariseUsage(events: any[]): Usage {
  const usage: Usage = { turns: 0, input: 0, output: 0, cacheRead: 0, cacheWrite: 0, cost: 0 };
  for (const event of events) {
    const message = event.type === "message_end" ? event.message : undefined;
    if (message?.role !== "assistant") continue;
    usage.turns++;
    for (const key of ["input", "output", "cacheRead", "cacheWrite"] as const) usage[key] += message.usage?.[key] ?? 0;
    usage.cost += message.usage?.cost?.total ?? 0;
    if (message.stopReason === "error") usage.error = message.errorMessage ?? "unknown error";
  }
  return usage;
}
