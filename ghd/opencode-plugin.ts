import { spawn } from "node:child_process";
import { appendFileSync, existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { blockedCommand, CATEGORIES, duplicateOf, renderMarkdown, SEVERITIES, VERDICTS, verificationBudget, type Finding, type Review, type Meta } from "./review-lib.ts";

const object = (properties: Record<string, unknown>, required = Object.keys(properties)) => ({ type: "object", properties, required, additionalProperties: false });
const string = { type: "string" };
const strings = { type: "array", items: string };
const finding = object({
  file: string, line: { type: "integer" }, start_line: { type: "integer" }, anchor: string,
  category: { enum: CATEGORIES }, severity: { enum: SEVERITIES }, title: string, comment: string, detail: string,
  verification: { type: "array", minItems: 1, maxItems: 2, items: object({ model: string, verdict: { enum: VERDICTS }, reason: string }) },
}, ["file", "line", "anchor", "category", "severity", "title", "comment"]);
const dropped = { type: "array", items: object({ candidate: string, reason: string }) };

type ToolContext = { sessionID: string; agent: string; signal: AbortSignal };
type Tool = { name: string; description: string; input: unknown; options: { codemode: boolean }; execute: (input: any, context: ToolContext) => Promise<{ content: string }> };
type Registration = { dispose: () => Promise<void> };
type Context = { websearch: {
  transform: (callback: (editor: { default: { get: () => string | false | undefined; set: (selection: string | false) => void } }) => void) => Promise<Registration>;
}; tool: {
  transform: (callback: (editor: { add: (tool: Tool) => void }) => void) => Promise<Registration>;
  hook: (name: "execute.before", callback: (event: { tool: string; input: any }) => Promise<void>) => Promise<Registration>;
} };

export default {
  id: "ghd.review",
  async setup(ctx: Context) {
    const out = process.env.GHD_REVIEW;
    if (!out) return;
    const meta: Meta & { session: string; cwd: string; merge_base?: string } = JSON.parse(readFileSync(`${out}.json`, "utf8"));
    const findingsFile = `${out}.findings`;
    const review = (): Review => existsSync(findingsFile) ? JSON.parse(readFileSync(findingsFile, "utf8")) : { tldr: "pending", findings: [] };
    const progress = (event: Record<string, unknown>) => appendFileSync(`${out}.progress`, JSON.stringify({ session: meta.session, ...event }) + "\n");
    const orchestrator = (context: ToolContext) => {
      if (context.sessionID !== meta.session || context.agent !== "pr-review") throw new Error("Only the review orchestrator can save findings or finish.");
    };
    const check = async (review: Review, signal: AbortSignal) => {
      const directory = mkdtempSync(join(tmpdir(), "ghd-check-"));
      const file = join(directory, "review.findings");
      writeFileSync(file, JSON.stringify(review));
      try {
        await new Promise<void>((resolve, reject) => {
          const child = spawn("python3", [join(import.meta.dirname, "check.py"), file, ...(meta.merge_base ? ["--head", meta.sha] : [])], { cwd: meta.cwd, signal, stdio: ["ignore", "pipe", "pipe"] });
          let output = "";
          child.stdout.on("data", (data) => output += data);
          child.stderr.on("data", (data) => output += data);
          child.on("error", reject);
          child.on("close", (code) => code === 0 ? resolve() : reject(new Error(output.trim() || "Finding validation failed")));
        });
      } finally { rmSync(directory, { recursive: true, force: true }); }
    };
    const spendVerification = verificationBudget(meta.verification_model ?? "openai/gpt-6-luna", meta.model);
    const registrations = [];
    registrations.push(await ctx.websearch.transform((editor) => {
      if (editor.default.get() === undefined) editor.default.set("random");
    }));
    registrations.push(await ctx.tool.hook("execute.before", async (event) => {
      if (["edit", "write", "patch", "opencode_worktree_create", "opencode_worktree_remove", "opencode_session_move"].includes(event.tool)) throw new Error("Review is read-only; save findings through save_finding.");
      if (event.tool === "shell") {
        const reason = blockedCommand(event.input?.command ?? "");
        if (reason) throw new Error(`Review is read-only: ${reason}`);
      }
      if (event.tool === "subagent") {
        if (event.input?.agent === "ghd-verifier") {
          if (event.input.sessionID || event.input.background) throw new Error("Verification uses one fresh foreground batch, without follow-ups.");
          spendVerification(event.input.model);
        } else if (event.input?.agent !== "ghd-reviewer") throw new Error("Review passes must use ghd-reviewer or ghd-verifier.");
      }
    }));
    registrations.push(await ctx.tool.transform((editor) => {
      editor.add({
        name: "save_finding", description: "Save one verified finding after validating its category, severity, head anchor and line. Rejects duplicate pointers. Only the orchestrator may call this.",
        input: finding, options: { codemode: false },
        async execute(input: Finding, context) {
          orchestrator(context);
          await check({ tldr: "pending", findings: [input] }, context.signal);
          const current = review();
          const duplicate = duplicateOf(input, current.findings);
          if (duplicate) throw new Error(`duplicate of saved finding ${duplicate}; consolidate the evidence`);
          writeFileSync(findingsFile, JSON.stringify({ ...current, findings: [...current.findings, input] }, null, 2));
          progress({ kind: "file", label: findingsFile });
          return { content: `Saved finding ${current.findings.length + 1}: ${input.title}` };
        },
      });
      editor.add({
        name: "finish_review", description: "Final action after all specialist results and save_finding calls: validate and write the review. Return a brief final reply afterwards.",
        input: object({
          tldr: string, dropped,
          since_last_review: { type: "array", items: object({ finding: string, status: { enum: ["fixed", "open", "dropped"] }, note: string }, ["finding", "status"]) },
          passes: { type: "array", items: object({ specialist: string, status: { enum: ["ran", "skipped"] }, note: string }, ["specialist", "status"]) },
          coverage_gaps: strings,
        }, ["tldr", "dropped", "passes", "coverage_gaps"]), options: { codemode: false },
        async execute(input: Omit<Review, "findings">, context) {
          orchestrator(context);
          const final = { ...review(), ...input };
          await check(final, context.signal);
          writeFileSync(findingsFile, JSON.stringify(final, null, 2));
          writeFileSync(`${out}.md`, renderMarkdown(final, meta));
          progress({ kind: "file", label: findingsFile });
          progress({ kind: "file", label: `${out}.md` });
          progress({ kind: "check", ok: true });
          return { content: `Review finished with ${final.findings.length} finding(s).` };
        },
      });
    }));
    return async () => { await Promise.all(registrations.map((registration) => registration.dispose())); };
  },
};
