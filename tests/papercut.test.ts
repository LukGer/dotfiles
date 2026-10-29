import { afterAll, beforeAll, expect, test } from "bun:test";
import { mkdtempSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const cli = join(import.meta.dir, "../bin/papercut");
let root: string;
let repository: string;
let worktree: string;
let nested: string;
let outside: string;

function run(cwd: string, command: string[]) {
  const result = Bun.spawnSync(command, {
    cwd,
    env: { ...process.env, HOME: join(root, "home") },
    stdout: "pipe",
    stderr: "pipe",
  });
  return {
    status: result.exitCode,
    stdout: result.stdout.toString(),
    stderr: result.stderr.toString(),
  };
}

function papercut(cwd: string, ...args: string[]) {
  return run(cwd, [process.execPath, cli, ...args]);
}

function git(cwd: string, ...args: string[]) {
  const result = run(cwd, ["git", ...args]);
  expect(result.status, result.stderr).toBe(0);
}

beforeAll(() => {
  root = mkdtempSync(join(tmpdir(), "papercut-test-"));
  repository = join(root, "repository");
  worktree = join(root, "worktree");
  nested = join(worktree, "nested");
  outside = join(root, "outside");
  const other = join(root, "other");
  for (const path of [repository, other, outside, join(root, "home")]) {
    mkdirSync(path);
  }
  git(repository, "init", "-q");
  git(repository, "-c", "user.name=Test", "-c", "user.email=test@example.com",
    "-c", "commit.gpgsign=false", "commit", "--allow-empty", "-qm", "Initial");
  git(repository, "worktree", "add", "--detach", "-q", worktree);
  mkdirSync(nested);
  git(other, "init", "-q");
  for (const [cwd, message] of [
    [repository, "main checkout"],
    [nested, "linked worktree"],
    [repository, "settled entry"],
    [other, "other repository"],
    [outside, "outside Git"],
  ]) {
    const result = papercut(cwd, message);
    expect(result.stderr).toBe("");
    expect(result.stdout).toContain("logged");
  }
  expect(papercut(repository, "dismiss", "3", "--reason", "Deliberate").status).toBe(0);
});

afterAll(() => {
  if (root) rmSync(root, { recursive: true, force: true });
});

test.each([
  ["main checkout, open", "main checkout", false],
  ["main checkout, all", "main checkout", true],
  ["linked worktree, open", "linked worktree", false],
  ["linked worktree, all", "linked worktree", true],
  ["subdirectory, open", "subdirectory", false],
  ["subdirectory, all", "subdirectory", true],
] as const)("current-repo includes all worktrees: %s", (_, location, all) => {
  const cwd = { "main checkout": repository, "linked worktree": worktree, subdirectory: nested }[location];
  const result = papercut(cwd, "list", "--current-repo", "--json", ...(all ? ["--all"] : []));
  expect(result.status, result.stderr).toBe(0);
  expect(JSON.parse(result.stdout).map((row: { message: string }) => row.message))
    .toEqual(all ? ["main checkout", "linked worktree", "settled entry"] : ["main checkout", "linked worktree"]);
});

test.each([false, true])("unfiltered listing keeps all sources (all=%j)", (all) => {
  const result = papercut(outside, "list", "--json", ...(all ? ["--all"] : []));
  expect(result.status, result.stderr).toBe(0);
  expect(JSON.parse(result.stdout).map((row: { message: string }) => row.message))
    .toEqual(all
      ? ["main checkout", "linked worktree", "settled entry", "other repository", "outside Git"]
      : ["main checkout", "linked worktree", "other repository", "outside Git"]);
});

test.each([false, true])("filtered text reports the repository scope (all=%j)", (all) => {
  const result = papercut(nested, "list", ...(all ? ["--all"] : []), "--current-repo");
  expect(result.status, result.stderr).toBe(0);
  expect(result.stdout).toContain(`${all ? "3 total" : "2 open"} papercuts in repository`);
  expect(result.stdout).not.toContain("other repository");
  expect(result.stdout).not.toContain("outside Git");
});

test.each([[[]], [["--json"]], [["--all", "--json"]]])("current-repo outside Git fails with %j", (args) => {
  const result = papercut(outside, "list", "--current-repo", ...args);
  expect(result.status).toBe(1);
  expect(result.stderr).toContain("--current-repo requires a Git repository");
  expect(result.stdout).toBe("");
});

test("current-repo with no entries returns an empty list", () => {
  const empty = join(root, "empty");
  mkdirSync(empty);
  git(empty, "init", "-q");
  const result = papercut(empty, "list", "--current-repo", "--json");
  expect(result.status, result.stderr).toBe(0);
  expect(JSON.parse(result.stdout)).toEqual([]);
});
