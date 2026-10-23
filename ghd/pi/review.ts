// ghd's pi extension: the review harness around the pr-review skill.
//
// `ghd review <repo> <pr> pi` loads this with `-e`. The orchestrator session
// gets save_finding (validated through `ghd check`), finish_review (writes
// both output files and ends the run) and review_pass (a specialist child pi
// process reporting candidates through report_candidates). Every session is
// read-only: a tool_call handler blocks edits and git, GitHub, file and
// install writes. Progress events go straight to <review>.progress. Sessions
// start with --no-extensions so personal pi packages never load; only the
// codemode (and, for the orchestrator, mcp) built-ins are added back.
import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync, appendFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { StringEnum } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { blockedCommand, CATEGORIES, duplicateOf, type Finding, renderMarkdown, type Review, SEVERITIES, SPECIALISTS, summariseUsage } from "./lib.ts";

const HERE = import.meta.dirname;
const OUT = process.env.GHD_REVIEW!;
const HEAD = process.env.GHD_HEAD!;
const MERGE_BASE = process.env.GHD_MERGE_BASE;
const MODEL = process.env.GHD_MODEL;
const ROLE = process.env.GHD_ROLE ?? "orchestrator";

const FindingSchema = Type.Object({
  file: Type.String({ description: "repo-relative path" }),
  line: Type.Integer({ description: "line number in the file at head, inside a diff hunk; prefer added lines" }),
  start_line: Type.Optional(Type.Integer({ description: "opens a multi-line range in the same hunk" })),
  anchor: Type.String({ description: "exact text of `line` at head" }),
  category: StringEnum(CATEGORIES),
  severity: StringEnum(SEVERITIES),
  title: Type.String({ description: "short title" }),
  comment: Type.String({ description: "what a reviewer posts: 1-2 sentences, problem then fix, concrete identifiers, no labels" }),
  detail: Type.Optional(Type.String({ description: "evidence for the human: quoted lines and reasoning, markdown" })),
});
const Dropped = Type.Array(Type.Object({ candidate: Type.String(), reason: Type.String() }));

const progress = (event: Record<string, unknown>) => appendFileSync(`${OUT}.progress`, JSON.stringify({ session: ROLE, ...event }) + "\n");
const readJson = <T>(path: string, fallback: T): T => (existsSync(path) ? JSON.parse(readFileSync(path, "utf8")) : fallback);
const text = (value: string) => ({ content: [{ type: "text" as const, text: value }] });

async function check(findings: Finding[]): Promise<string[]> {
  const dir = mkdtempSync(join(tmpdir(), "ghd-check-"));
  const file = join(dir, "candidate.findings");
  writeFileSync(file, JSON.stringify({ tldr: "pending", findings }));
  const args = [join(HERE, "..", "check.py"), file, ...(MERGE_BASE ? ["--head", HEAD] : [])];
  return new Promise((resolve) => {
    const child = spawn("python3", args, { stdio: ["ignore", "pipe", "pipe"] });
    let out = "";
    child.stdout.on("data", (d) => (out += d));
    child.stderr.on("data", (d) => (out += d));
    child.on("close", (code) => {
      rmSync(dir, { recursive: true, force: true });
      resolve(code === 0 ? [] : out.trim().split("\n").filter(Boolean));
    });
  });
}

function piInvocation(args: string[]) {
  const script = process.argv[1];
  return script && existsSync(script) && !script.startsWith("/$bunfs/")
    ? { command: process.execPath, args: [script, ...args] }
    : { command: "pi", args };
}

function runSpecialist(specialist: string, skill: string | undefined, prompt: string, signal: AbortSignal | undefined, onEvent: (event: any) => void) {
  const dir = mkdtempSync(join(tmpdir(), "ghd-pass-"));
  const report = join(dir, "candidates.json");
  const guidelines = skill && existsSync(skill) ? skill : join(HERE, "specialists", `${specialist}.md`);
  const args = ["-p", "--mode", "json", "--no-session", "--tools", "read,bash,codemode,report_candidates",
    "--no-extensions", "-e", "builtin:codemode", "-e", join(HERE, "review.ts"),
    "--append-system-prompt", join(HERE, "specialist.md"), "--append-system-prompt", guidelines,
    ...(MODEL ? ["--model", MODEL] : []), prompt];
  const invocation = piInvocation(args);
  return new Promise<{ report: any; usage: ReturnType<typeof summariseUsage>; stderr: string }>((resolve) => {
    const child = spawn(invocation.command, invocation.args, {
      stdio: ["ignore", "pipe", "pipe"],
      env: { ...process.env, GHD_ROLE: "specialist", GHD_SPECIALIST: specialist, GHD_SPECIALIST_OUT: report },
    });
    const events: any[] = [];
    let buffer = "", stderr = "";
    const take = (line: string) => {
      if (!line.trim()) return;
      try { const event = JSON.parse(line); events.push(event); onEvent(event); } catch { }
    };
    child.stdout.on("data", (data) => {
      buffer += data;
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      lines.forEach(take);
    });
    child.stderr.on("data", (data) => (stderr += data));
    child.on("close", () => {
      take(buffer);
      const result = { report: readJson(report, null), usage: summariseUsage(events), stderr: stderr.trim() };
      rmSync(dir, { recursive: true, force: true });
      resolve(result);
    });
    child.on("error", (error) => resolve({ report: null, usage: { ...summariseUsage([]), error: String(error) }, stderr }));
    signal?.addEventListener("abort", () => child.kill("SIGTERM"), { once: true });
  });
}

export default function (pi: ExtensionAPI) {
  pi.on("tool_call", async (event: any) => {
    const reason = ["edit", "write"].includes(event.toolName)
      ? "files belong to the human: findings go through save_finding"
      : event.toolName === "bash" ? blockedCommand(event.input?.command ?? "") : null;
    return reason ? { block: true, reason } : undefined;
  });
  pi.on("tool_execution_end", async (event: any) => {
    if (!["codemode", "save_finding", "finish_review", "review_pass", "report_candidates"].includes(event.toolName)) {
      progress({ kind: "tool", label: ROLE === "specialist" ? `${process.env.GHD_SPECIALIST}:${event.toolName}` : event.toolName });
    }
  });

  if (ROLE === "specialist") {
    pi.registerTool({
      name: "report_candidates", label: "Report candidates",
      description: "Final action of a specialist pass: hand the verified candidates, the discarded ones and any coverage gaps back to the orchestrator. Ends the pass.",
      promptSnippet: "Report verified candidates to the orchestrator; ends the pass",
      promptGuidelines: ["Call report_candidates exactly once, as your last action. An empty candidates list is a valid result."],
      parameters: Type.Object({
        candidates: Type.Array(FindingSchema),
        dropped: Dropped,
        coverage_gaps: Type.Array(Type.String()),
      }),
      async execute(_id, params: any) {
        writeFileSync(process.env.GHD_SPECIALIST_OUT!, JSON.stringify({ ...params, specialist: process.env.GHD_SPECIALIST }));
        return { ...text(`Reported ${params.candidates.length} candidate(s).`), details: undefined, terminate: true };
      },
    });
    return;
  }

  const meta = readJson<any>(`${OUT}.json`, {});
  const findingsFile = `${OUT}.findings`;
  const review = (): Review => readJson(findingsFile, { tldr: "pending", findings: [] });

  pi.registerTool({
    name: "review_pass", label: "Specialist pass",
    description: "Run one specialist review pass in a separate read-only pi session and get its verified candidates back. When the repository has its own review skill for the pass, name its SKILL.md as `skill`: it becomes the pass's guidelines in place of the generic checklist. Launch all in-scope passes at once from one codemode script with Promise.all.",
    promptSnippet: "Run a specialist review pass (correctness, deep, security, risk, quality, design, completeness)",
    parameters: Type.Object({
      specialist: StringEnum(SPECIALISTS),
      scope: Type.String({ description: "exact assigned paths and hunks, ticket content, access and index availability, and what to focus on" }),
      skill: Type.Optional(Type.String({ description: "repo-relative path of the repository review skill to apply, e.g. .agents/skills/bugs-review/SKILL.md; its steps and zones replace the generic checklist" })),
    }),
    outputSchema: Type.Object({
      specialist: Type.String(), candidates: Type.Array(FindingSchema), dropped: Dropped, coverage_gaps: Type.Array(Type.String()),
      usage: Type.Object({ turns: Type.Integer(), cost: Type.Number(), error: Type.Optional(Type.String()) }),
    }),
    async execute(_id, params: any, signal) {
      progress({ kind: "agent_start", label: params.specialist });
      const prompt = [`Specialist pass: ${params.specialist}`, `Packet: ${OUT}.packet.md`, `Head: ${HEAD}`,
        params.skill ? `Repository review skill in your system prompt: ${params.skill}; its references live next to it.` : "", "", "Scope:", params.scope].join("\n");
      const run = await runSpecialist(params.specialist, params.skill, prompt, signal, (event) => {
        if (event.type === "tool_execution_end" && event.toolName !== "codemode") progress({ kind: "tool", label: `${params.specialist}:${event.toolName}` });
      });
      progress({ kind: "agent_end", label: params.specialist });
      const report = run.report ?? { candidates: [], dropped: [], coverage_gaps: [`${params.specialist} pass ended without a report${run.usage.error ? `: ${run.usage.error}` : ""}${run.stderr ? `; ${run.stderr.slice(0, 300)}` : ""}`] };
      const structured = { specialist: params.specialist, candidates: report.candidates, dropped: report.dropped, coverage_gaps: report.coverage_gaps,
        usage: { turns: run.usage.turns, cost: run.usage.cost, ...(run.usage.error ? { error: run.usage.error } : {}) } };
      return { ...text(JSON.stringify(structured, null, 1)), structuredContent: structured, details: structured, isError: !run.report };
    },
  });

  pi.registerTool({
    name: "save_finding", label: "Save finding",
    description: "Record one verified finding. Runs `ghd check` on it (anchor and line at head, category, severity) and rejects duplicates of saved findings; a rejection explains what to fix.",
    promptSnippet: "Record one verified finding; validated against head",
    parameters: FindingSchema,
    outputSchema: Type.Object({ ok: Type.Boolean(), problems: Type.Array(Type.String()), count: Type.Integer() }),
    async execute(_id, params: any) {
      const current = review();
      const twin = duplicateOf(params, current.findings);
      const problems = twin ? [`duplicate of saved finding ${twin} (${current.findings[twin - 1].title}); merge them instead`] : await check([params]);
      if (!problems.length) writeFileSync(findingsFile, JSON.stringify({ ...current, findings: [...current.findings, params] }, null, 2));
      const count = current.findings.length + (problems.length ? 0 : 1);
      const structured = { ok: !problems.length, problems, count };
      return { ...text(problems.length ? `Rejected: ${problems.join("; ")}` : `Saved finding ${count}: ${params.title}`), structuredContent: structured, details: structured, isError: problems.length > 0 };
    },
  });

  pi.registerTool({
    name: "finish_review", label: "Finish review",
    description: "Final action: the TLDR for the author, dropped candidates, the re-review table when the brief named a previous review, which passes ran, and coverage gaps. Writes the review files and ends the run.",
    promptSnippet: "Finish the review: TLDR, dropped candidates, passes; writes the files and ends the run",
    promptGuidelines: ["Call finish_review exactly once, as the last action, after every save_finding. Do not write review files yourself."],
    parameters: Type.Object({
      tldr: Type.String({ description: "2-4 lines to the PR author: what the PR does, the worst finding or that it looks good, risk only if real" }),
      dropped: Dropped,
      since_last_review: Type.Optional(Type.Array(Type.Object({ finding: Type.String(), status: StringEnum(["fixed", "open", "dropped"] as const), note: Type.Optional(Type.String()) }))),
      passes: Type.Array(Type.Object({ specialist: Type.String(), status: StringEnum(["ran", "skipped"] as const), note: Type.Optional(Type.String()) })),
      coverage_gaps: Type.Array(Type.String()),
    }),
    async execute(_id, params: any) {
      const final: Review = { ...review(), ...params };
      const problems = await check(final.findings);
      progress({ kind: "check", ok: !problems.length });
      if (problems.length) return { ...text(`Not finished: ${problems.join("; ")}`), details: undefined, isError: true };
      writeFileSync(findingsFile, JSON.stringify(final, null, 2));
      writeFileSync(`${OUT}.md`, renderMarkdown(final, { repo: meta.repo, pr: meta.pr, title: meta.title, tool: meta.tool, model: meta.model ?? MODEL ?? "", sha: HEAD }));
      progress({ kind: "file", label: findingsFile });
      progress({ kind: "file", label: `${OUT}.md` });
      return { ...text(`Review finished with ${final.findings.length} finding(s).`), details: undefined, terminate: true };
    },
  });
}
