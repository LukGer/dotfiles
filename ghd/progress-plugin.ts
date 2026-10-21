// OpenCode plugin: forwards tool calls of ghd review sessions (and their
// subagent sessions) to `ghd progress opencode`. ghd/install.sh links it into
// ~/.config/opencode/plugins/. It is a plain {id, setup} object because
// OpenCode's Plugin.define is the identity and this keeps the file dependency-free.
import { spawn } from "node:child_process"

const PROGRESS = `${import.meta.dir}/progress.py`
const GHD_SESSION = /^ses_ghd/

type ToolEvent = {
  tool: string
  sessionID: string
  input: unknown
  status?: "completed" | "error"
  result?: { output?: string }
}

type Context = {
  tool: { hook: (name: "execute.before" | "execute.after", callback: (event: ToolEvent) => Promise<void>) => Promise<{ dispose: () => Promise<void> }> }
  session: { get: (input: { sessionID: string }) => Promise<{ parentID?: string }> }
}

export default {
  id: "ghd.progress",
  async setup(ctx: Context) {
    // The ghd review session that owns a session: itself, or the root of its parent chain.
    const owners = new Map<string, Promise<string | null>>()
    const owner = (sessionID: string): Promise<string | null> => {
      if (!owners.has(sessionID)) {
        owners.set(sessionID, GHD_SESSION.test(sessionID)
          ? Promise.resolve(sessionID)
          : ctx.session.get({ sessionID }).then((session) => (session.parentID ? owner(session.parentID) : null), () => null))
      }
      return owners.get(sessionID)!
    }

    const report = (sessionID: string, phase: "before" | "after", event: ToolEvent) =>
      new Promise<void>((resolve) => {
        const child = spawn("python3", [PROGRESS, "opencode"], { stdio: ["pipe", "ignore", "ignore"] })
        child.on("exit", () => resolve())
        child.on("error", () => resolve())
        child.stdin.end(JSON.stringify({
          sessionID, phase, tool: event.tool, input: event.input,
          output: event.status === "completed" ? event.result?.output ?? "" : "",
        }))
      })

    const registrations = await Promise.all((["before", "after"] as const).map((phase) =>
      ctx.tool.hook(`execute.${phase}`, async (event) => {
        const review = await owner(event.sessionID)
        if (review) await report(review, phase, event)
      })))
    return async () => { await Promise.all(registrations.map((registration) => registration.dispose())) }
  },
}
