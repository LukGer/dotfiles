import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, existsSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

for (const configured of [undefined, false, "tavily", "random"]) {
  test(`review web search needs no provider form (configured: ${configured})`, async (t) => {
    const directory = mkdtempSync(join(tmpdir(), "ghd-websearch-test-"));
    const out = join(directory, "review");
    const previous = process.env.GHD_REVIEW;
    process.env.GHD_REVIEW = out;
    t.after(() => {
      rmSync(directory, { recursive: true, force: true });
      if (previous === undefined) delete process.env.GHD_REVIEW;
      else process.env.GHD_REVIEW = previous;
    });
    writeFileSync(`${out}.json`, JSON.stringify({ session: "ses_test", cwd: directory }));
    const plugin = (await import("./opencode-plugin.ts")).default;
    let selection = configured;
    let disposed = false;
    const registration = { dispose: async () => {} };
    const cleanup = await plugin.setup({
      websearch: {
        transform: async (transform: any) => {
          transform({ default: { get: () => selection, set: (value: any) => selection = value } });
          return { dispose: async () => { disposed = true; } };
        },
      },
      tool: { hook: async () => registration, transform: async () => registration },
    });
    assert.equal(selection, configured ?? "random", "Web Search would ask for a provider in a headless review");
    await cleanup();
    assert.equal(disposed, true);
  });
}

test("non-review sessions leave web search untouched", async () => {
  const previous = process.env.GHD_REVIEW;
  delete process.env.GHD_REVIEW;
  try {
    const plugin = (await import("./opencode-plugin.ts")).default;
    await plugin.setup({
      websearch: { transform: async () => { assert.fail("not a review"); } },
      tool: {
        hook: async () => { assert.fail("not a review"); },
        transform: async () => { assert.fail("not a review"); },
      },
    });
  } finally {
    if (previous !== undefined) process.env.GHD_REVIEW = previous;
  }
});

test("review tools validate, deduplicate, and finish only in the orchestrator", async () => {
  const directory = mkdtempSync(join(tmpdir(), "ghd-opencode-test-"));
  const out = join(directory, "review");
  process.env.GHD_REVIEW = out;
  writeFileSync(`${out}.json`, JSON.stringify({ repo: "o/r", pr: 7, sha: "abc", session: "ses_ghdtest", cwd: directory, title: "Example", tool: "opencode", model: "openai/gpt-6.1-sol#high", verification_model: "openai/gpt-6-luna", middle_model: "openai/gpt-6.1-terra#high", mode: "specialists" }));
  const plugin = (await import("./opencode-plugin.ts")).default;
  const tools = new Map<string, any>();
  const hooks = new Map<string, any>();
  await plugin.setup({
    websearch: { transform: async () => ({ dispose: async () => {} }) },
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
  const verify = (input: any) => hooks.get("execute.before")({ tool: "subagent", input });
  await verify({ agent: "ghd-reviewer", model: "openai/gpt-6.1-terra#high" });
  await assert.rejects(verify({ agent: "ghd-reviewer", model: "openai/gpt-6-luna" }), /middle model/);
  await assert.rejects(verify({ agent: "ghd-verifier", model: "openai/gpt-6.1-sol#high" }), /cheap|verification model/);
  for (const extra of [{ sessionID: "old" }, { background: true }]) {
    await assert.rejects(verify({ agent: "ghd-verifier", model: "openai/gpt-6-luna", ...extra }), /fresh foreground/);
  }
  await verify({ agent: "ghd-verifier", model: "openai/gpt-6-luna" });
  await assert.rejects(verify({ agent: "ghd-verifier", model: "openai/gpt-6-luna" }), /already|once/);
  await verify({ agent: "ghd-verifier", model: "openai/gpt-6.1-sol#high" });
  await assert.rejects(verify({ agent: "ghd-verifier", model: "openai/gpt-6.1-sol#high" }), /already|once/);
  await save({ ...finding, verification: [{ model: "openai/gpt-6-luna", verdict: "uncertain", reason: "Caller configuration unavailable." }] });
  await assert.rejects(save(finding), /duplicate/);
  const finish = tools.get("finish_review");
  await finish.execute({ tldr: "Fix the crash.", dropped: [], passes: [{ specialist: "correctness", status: "ran" }], coverage_gaps: [] }, context);
  assert.equal(JSON.parse(readFileSync(`${out}.findings`, "utf8")).findings.length, 1);
  const saved = JSON.parse(readFileSync(`${out}.findings`, "utf8"));
  assert.equal(saved.findings[0].verification[0].verdict, "uncertain");
  assert.match(readFileSync(`${out}.md`, "utf8"), /uncertain.*Caller configuration unavailable/);
  for (const [tool, input] of [["edit", { path: "a" }], ["shell", { command: "git commit -am x" }], ["subagent", { agent: "general" }]]) {
    await assert.rejects(hooks.get("execute.before")({ tool, input, sessionID: context.sessionID }), /read-only|ghd-reviewer/);
  }
  await hooks.get("execute.before")({ tool: "shell", input: { command: "git diff" }, sessionID: context.sessionID });
});
