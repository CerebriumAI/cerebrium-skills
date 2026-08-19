---
name: cerebrium
description: >-
  Start here for any Cerebrium task: deploying Python code to serverless GPU or CPU,
  writing or fixing cerebrium.toml, choosing hardware and regions, calling deployed
  endpoints (REST, streaming, WebSocket, async), autoscaling and concurrency, cold
  starts, secrets, CI/CD, and debugging a build or a running app. Routes to the right
  Cerebrium skill (cerebrium-config, cerebrium-hardware, cerebrium-deploy,
  cerebrium-troubleshoot). Use when it is unclear which one applies.
license: MIT
metadata:
  author: cerebrium
  version: "0.1.0"
---

# Cerebrium (router)

Cerebrium runs Python workloads on serverless GPU and CPU: REST endpoints, SSE streaming,
WebSockets, and async jobs, with scale-to-zero and per-second billing. One `cerebrium.toml`
describes hardware, scaling, dependencies and runtime.

This skill routes. It does no work itself. Read the matching skill next.

## Lanes

| Lane | Use it for |
| --- | --- |
| **cerebrium-cli** | Any `cerebrium` command: the full surface, arguments, flags, global flags, non-interactive auth, and which commands cost money. Read this before running one. |
| **cerebrium-config** | Writing or fixing `cerebrium.toml`: every section, the values the API actually applies when you omit a field, accepted ranges, what triggers a full rebuild. |
| **cerebrium-hardware** | Picking `compute`, `gpu_count`, `region`, `provider`, `compute_tier`, and where model weights live. Includes the exact accepted GPU names and per-region availability. |
| **cerebrium-deploy** | The deploy loop, calling the endpoint, auth, streaming/WebSocket/async shapes, secrets, and non-interactive CI/CD. |
| **cerebrium-troubleshoot** | A build that failed, an app that 5xxs, slow cold starts, replicas that will not scale. Log and container inspection from the terminal. |

## First run: check state before acting

Do this before the first deploy in a session. Every step is terminal-only, no browser needed.

```bash
cerebrium --version                 # installed? if not: pip install cerebrium (or brew install cerebrium)
cerebrium projects current          # authenticated, and pointed at the intended project?
```

If not authenticated: `cerebrium login` opens a browser. In a headless or CI environment do not
run `login`. Set `CEREBRIUM_SERVICE_ACCOUNT_TOKEN` (or pass `--service-account-token`) instead:
see **cerebrium-deploy**.

## Zero to a deployed endpoint

```bash
pip install cerebrium              # thin wrapper that fetches the Go binary on first use
cerebrium login                    # interactive only
cerebrium init my-app && cd my-app
cerebrium deploy
```

`init` writes `main.py` and `cerebrium.toml`. Read **cerebrium-config** before editing the TOML:
the scaffold is not a safe production default (it ships `disable_auth = true`, which makes the
endpoint public).

## Rules for agents

1. **Deploys cost money.** `cerebrium deploy`, `cerebrium run` and `cerebrium apps scale` all
   start billable compute, and `cerebrium apps delete` is destructive. State what will run and on
   what hardware, and get the user's confirmation before the first one in a session.
2. **`cerebrium run` is not local.** It packages the working directory, uploads it, and executes
   in the cloud on the hardware in `cerebrium.toml`. There is no local emulator.
3. **Adapt an example before writing from scratch.** `https://github.com/CerebriumAI/examples`
   holds runnable references (vLLM, SDXL, Pipecat voice agents, ASGI apps), each with a working
   `cerebrium.toml`.
4. **Never invent config keys or GPU names.** Both are validated server-side and a wrong value
   fails the deploy. The accepted sets are in **cerebrium-config** and **cerebrium-hardware**.
5. **Check the live docs when this skill does not cover it**, rather than guessing:
   - MCP server: `https://cerebrium.ai/docs/mcp` (search plus docs filesystem)
   - Any docs page as markdown: append `.md` to its URL
   - Page index: `https://cerebrium.ai/docs/llms.txt`
