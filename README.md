# Cerebrium agent skills

Official [Agent Skills](https://agentskills.io) and hosted docs MCP for
[Cerebrium](https://www.cerebrium.ai), the serverless GPU and CPU platform for real-time AI
workloads. The skills teach a coding agent to write a valid `cerebrium.toml`, pick hardware and a
region, deploy, call the endpoint, and debug the result without leaving the terminal. The MCP
gives it live search over the documentation.

Works with Claude Code, Codex, Cursor, GitHub Copilot, Windsurf, Cline and anything else that
reads the Agent Skills format.

## Install

Any agent (installs the skills into every detected harness):

```bash
npx skills add CerebriumAI/cerebrium-skills -g -y
npx add-mcp https://cerebrium.ai/docs/mcp -n cerebrium-docs -g -y
```

Claude Code (one plugin bundles the skills and the docs MCP):

```
/plugin marketplace add CerebriumAI/cerebrium-skills
/plugin install cerebrium@cerebrium
```

Codex:

```bash
codex plugin marketplace add CerebriumAI/cerebrium-skills
```

Or agent-driven: paste this into the agent of your choice.

```
Install the Cerebrium agent toolkit following instructions from
github.com/CerebriumAI/cerebrium-skills: use `npx skills add` and `npx add-mcp`,
global and auto-confirmed for all agents (-g -y).
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
| `cerebrium-hardware` | The 13 accepted `compute` identifiers, per-GPU and per-plan limits, preference lists, per-region availability, spot versus on-demand, persistent storage. |
| `cerebrium-deploy` | Deploy loop and flags, endpoint URL and auth, REST/SSE/WebSocket/async shapes, secrets and automatic env vars, non-interactive CI/CD. |
| `cerebrium-troubleshoot` | Log and container inspection, a symptom-to-cause table, the cold-start playbook. |

Skills load progressively: an agent sees only the names and descriptions until a task matches,
then reads one lane. The docs MCP (`.mcp.json`, hosted at `https://cerebrium.ai/docs/mcp`) is
read-only: documentation search and filesystem, no account access, no key needed.

## Try it

- "Deploy this FastAPI app to Cerebrium on an H100 with auth enabled, then follow the logs."
- "My Cerebrium app queues requests under load. Work out why and fix the config."
- "Which GPU and region fit a 13B vLLM model on Cerebrium, and what should the cerebrium.toml be?"

## Related surfaces

- Any docs page as markdown: append `.md` to the URL
- Page index: `https://cerebrium.ai/docs/llms.txt`
- Runnable examples: [CerebriumAI/examples](https://github.com/CerebriumAI/examples)

## Accuracy

Every default, enum, flag and signature here was read out of the CLI source and the API
validator rather than copied from a docs page. See [CONTRIBUTING.md](CONTRIBUTING.md) for where
to check each kind of claim, and keep it that way.

MIT licensed.
