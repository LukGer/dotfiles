import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, existsSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("review tools validate, deduplicate, and finish only in the orchestrator", async () => {
  const directory = mkdtempSync(join(tmpdir(), "ghd-opencode-test-"));
  const out = join(directory, "review");
  process.env.GHD_REVIEW = out;
  writeFileSync(`${out}.json`, JSON.stringify({ repo: "o/r", pr: 7, sha: "abc", session: "ses_ghdtest", cwd: directory, title: "Example", tool: "opencode", model: "openai/gpt-6.1-sol#high" }));
  const plugin = (await import("./opencode-plugin.ts")).default;
  const tools = new Map<string, any>();
  const hooks = new Map<string, any>();
  await plugin.setup({
    tool: {
      transform: async (f: any) => { f({ add: (tool: any) => tools.set(tool.name, tool) }); return { dispose: async () => {} }; },
      hook: async (name: string, f: any) => { hooks.set(name, f); return { dispose: async () => {} }; },
    },
  });
  const context = { sessionID: "ses_ghdtest", agent: "pr-review", signal: new AbortController().signal };
  const finding = { file: "a.ts", line: 2, anchor: "bad()", category: "bug", severity: "P1", title: "Crash", comment: "Handle the missing value." };
  const save = (input: any, ctx = context) => tools.get("save_finding").execute(input, ctx);
  await assert.rejects(save(finding, { ...context, agent: "ghd-reviewer" }), /orchestrator/);
  await assert.rejects(save({ ...finding, category: "invalid" }), /category/);
  assert.equal(existsSync(`${out}.findings`), false);
  await save(finding);
  await assert.rejects(save(finding), /duplicate/);
  const finish = tools.get("finish_review");
  await finish.execute({ tldr: "Fix the crash.", dropped: [], passes: [{ specialist: "correctness", status: "ran" }], coverage_gaps: [] }, context);
  assert.equal(JSON.parse(readFileSync(`${out}.findings`, "utf8")).findings.length, 1);
  assert.match(readFileSync(`${out}.md`, "utf8"), /Fix the crash/);
  for (const [tool, input] of [["edit", { path: "a" }], ["shell", { command: "git commit -am x" }], ["subagent", { agent: "general" }]]) {
    await assert.rejects(hooks.get("execute.before")({ tool, input, sessionID: context.sessionID }), /read-only|ghd-reviewer/);
  }
  await hooks.get("execute.before")({ tool: "shell", input: { command: "git diff" }, sessionID: context.sessionID });
});
