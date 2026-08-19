# Cerebrium agent skills

Official [Agent Skills](https://agentskills.io) for [Cerebrium](https://www.cerebrium.ai), the
serverless GPU and CPU platform for real-time AI workloads. They teach a coding agent to write a
valid `cerebrium.toml`, pick hardware and a region, deploy, call the endpoint, and debug the
result without leaving the terminal.

Works with Claude Code, Codex, Cursor, GitHub Copilot, Windsurf, Cline and anything else that
reads the Agent Skills format.

## Install

```bash
# any agent
npx skills add CerebriumAI/cerebrium-skills

# Claude Code
/plugin marketplace add CerebriumAI/cerebrium-skills
/plugin install cerebrium@cerebrium

# Codex
codex plugin marketplace add CerebriumAI/cerebrium-skills
```

Then authenticate the CLI once:

```bash
pip install cerebrium   # or: brew tap cerebriumai/tap && brew install cerebrium
cerebrium login
```

In CI, skip `login` and set `CEREBRIUM_SERVICE_ACCOUNT_TOKEN` instead.

## What is in here

| Skill | Lane |
| --- | --- |
| `cerebrium` | Router and entry point. Reads the task and hands it to the right lane. Also carries the zero-to-deployed path and the safety rules. |
| `cerebrium-cli` | The full command surface: arguments, flags, global flags, non-interactive auth, and which commands mutate live infrastructure. |
| `cerebrium-config` | `cerebrium.toml`: every section, the value the API applies when a key is omitted, accepted ranges, what forces a rebuild. |
| `cerebrium-hardware` | The 13 accepted `compute` names, preference lists, per-region availability, provider pinning, spot versus on-demand, persistent storage. |
| `cerebrium-deploy` | Deploy loop and flags, endpoint URL and auth, REST/SSE/WebSocket/async shapes, secrets and automatic env vars, non-interactive CI/CD. |
| `cerebrium-troubleshoot` | Log and container inspection, a symptom-to-cause table, the cold-start playbook. |

Skills load progressively: an agent sees only the names and descriptions until a task matches,
then reads one lane.

## Related surfaces

- Docs MCP server: `https://cerebrium.ai/docs/mcp`
- Any docs page as markdown: append `.md` to the URL
- Page index: `https://cerebrium.ai/docs/llms.txt`
- Runnable examples: [CerebriumAI/examples](https://github.com/CerebriumAI/examples)

## Accuracy

Every default, enum, flag and signature here was read out of the CLI source and the API
validator rather than copied from a docs page. See [CONTRIBUTING.md](CONTRIBUTING.md) for where
to check each kind of claim, and keep it that way.

MIT licensed.
