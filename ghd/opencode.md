# OpenCode V2 for ghd

Verified on 2026-11-03 with OpenCode 2.2.5, including authenticated synthetic
reviews through both subscription providers. The implementation uses built-in
Code Mode, subagents and MCP, plus two local plugins for review persistence and
progress. No third-party authentication or orchestration package is required.

## Install and connect

The [V2 installation guide](https://opencode.ai/v2/docs/) specifies
`anomalyco/tap/opencode-v2` for Homebrew and `@opencode/cli` for npm. V1 also
installs an `opencode` command, so check `opencode --version`. `Brewfile` installs
the V2 formula; `ghd/install.sh` links the agents and plugins on `dot` runs.

```sh
opencode upgrade 2.2.5
opencode service restart
opencode auth login openai
claude auth login
opencode auth login claude-agent --method claude-login
opencode mcp auth atlassian
opencode models
```

OpenAI's built-in connection supports ChatGPT Plus/Pro. Select “Sign in with
ChatGPT” when connecting OpenAI; no API key is required for that method.
[V2 providers](https://opencode.ai/v2/docs/providers/)

Claude subscription access uses provider **`claude-agent`**, introduced in
OpenCode 2.2.3, rather than the API-key `anthropic` provider. It runs the local
Claude binary through Anthropic's Agent SDK and uses its existing login without
extracting OAuth tokens. Claude Code >=2.1.248 is required. This is a first-party
OpenCode integration; the implementation does not establish a separate
Anthropic endorsement of OpenCode. [Provider source](https://github.com/anomalyco/opencode/blob/v2.2.5/packages/core/src/plugin/provider/claude-agent/index.ts),
[login source](https://github.com/anomalyco/opencode/blob/v2.2.5/packages/core/src/plugin/provider/claude-agent/integration.ts),
[provider spec](https://github.com/anomalyco/opencode/blob/v2.2.5/specs/v2/claude-agent-provider.md)

The picker uses `openai/gpt-6.1-sol#high` and `claude-agent/opus#high`. Claude's
catalog comes from the installed Claude Code; `opus` selects its advertised
Opus alias. Check `opencode models` before pinning a different identifier.
[Model discovery source](https://github.com/anomalyco/opencode/blob/v2.2.5/packages/core/src/plugin/provider/claude-agent/provider.ts)

After upgrading, restart an idle background service so interactive clients and
authentication commands use the current binary. `--standalone` can be used for
an isolated command instead. Reviews and PR chat always use it so their plugins
receive the invoking process's environment. Restarting a service with active
sessions would interrupt those sessions. [CLI commands](https://opencode.ai/v2/docs/cli/commands/)

## Review configuration

Global agent files live in `~/.config/opencode/agents/`; plugins are discovered
under `~/.config/opencode/plugins/`. `pr-review` is the primary agent,
`ghd-reviewer` is the scoped specialist, and `ghd-chat` discusses the supplied
snapshot with every tool denied. Existing skills under `~/.agents/skills` and
repository `.agents/skills` are discovered automatically.
[Agents](https://opencode.ai/v2/docs/agents/), [plugins](https://opencode.ai/v2/docs/plugins/),
[skills](https://opencode.ai/v2/docs/skills/)

V2 uses ordered `permissions` rules with `action`, `resource` and `effect`.
Specialists have their own rules, so each review agent explicitly denies
unlisted actions and allows inspection commands. The native `subagent` tool
inherits the review model when neither its call nor agent specifies a model.
Independent foreground calls can run together; in 2.2.5 this tool is direct
and is not in Code Mode's catalog. [Permissions](https://opencode.ai/v2/docs/permissions/),
[tagged subagent source](https://github.com/anomalyco/opencode/blob/v2.2.5/packages/core/src/tool/plugin/subagent.ts)

The review plugin registers direct `save_finding` and `finish_review` tools
through `ctx.tool.transform`. Both restrict writes to the root review session
and `pr-review` agent. The existing progress plugin follows child session
ownership. The V2 CLI JSON stream emits text and completed tool calls; the
plugin side channel supplies progress while specialists run.
[Plugin API](https://opencode.ai/v2/docs/build/plugins/server/),
[tagged JSON renderer](https://github.com/anomalyco/opencode/blob/v2.2.5/packages/cli/src/run/noninteractive.ts)

Atlassian uses `mcp.servers.atlassian`, a remote server at
`https://mcp.atlassian.com/v1/mcp/authv2`. The installer preserves existing MCP
configuration and adds the server only when missing. Review permissions allow
Jira reads; unavailable access becomes a coverage gap.
[MCP configuration](https://opencode.ai/v2/docs/mcp-servers/)

Implementation choices above are based on the released 2.2.5 APIs. The live docs
can describe later behavior; for example, `run --archived` was documented but
absent from this release, so ghd does not use it.
