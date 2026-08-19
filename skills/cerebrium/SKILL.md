---
name: cerebrium
description: >-
  Use for any Cerebrium task: deploying Python code to serverless GPU or CPU, writing or fixing
  cerebrium.toml, choosing hardware and regions, calling deployed endpoints (REST, streaming,
  WebSocket, async), autoscaling and concurrency, cold starts, secrets, CI/CD, and debugging a
  build or a running app from the terminal. Covers the cerebrium CLI, configuration defaults the
  API actually applies, accepted GPU identifiers with per-plan limits, and troubleshooting.
license: MIT
metadata:
  author: cerebrium
  version: "0.1.0"
---

# Cerebrium

Cerebrium runs Python workloads on serverless GPU and CPU: REST endpoints, SSE streaming,
WebSockets, and async jobs, with scale-to-zero and per-second billing. One `cerebrium.toml`
describes hardware, scaling, dependencies and runtime; one CLI (`cerebrium`) drives everything.

This file carries the workflow and the rules. Load the reference that matches the task:

| Read | When |
| --- | --- |
| [references/cli.md](references/cli.md) | Running any `cerebrium` command: the full surface, flags, non-interactive auth, CI/CD, which commands cost money. |
| [references/config.md](references/config.md) | Writing or fixing `cerebrium.toml`: every key, the default the API applies when it is omitted, accepted ranges, rebuild triggers. |
| [references/hardware.md](references/hardware.md) | Choosing `compute`, `gpu_count`, `region`, `provider`, `compute_tier`: accepted GPU identifiers, per-GPU and per-plan limits, regional availability, storage. |
| [references/troubleshooting.md](references/troubleshooting.md) | A build that failed, an app that 5xxs or queues, slow cold starts, settings that reverted. |

## Rules for agents

1. **Deploys cost money.** `cerebrium deploy`, `cerebrium run` and `cerebrium apps scale` start
   billable compute, and `cerebrium apps delete` is destructive. State what will run on what
   hardware and get the user's confirmation before the first one in a session.
2. **`cerebrium run` is not local.** It packages the working directory, uploads it, and executes
   in the cloud on the hardware in `cerebrium.toml`. There is no local emulator.
3. **A `cerebrium.toml` key you leave out is reset to its default on deploy**, not left alone,
   and a misspelled key is ignored in silence. Keep every value that matters in the file, spelled
   as in [references/config.md](references/config.md).
4. **Never invent config keys or GPU identifiers.** Both are validated server-side and a wrong
   value fails the deploy. The accepted sets are in the references.
5. **Adapt an example before writing from scratch.** `https://github.com/CerebriumAI/examples`
   holds runnable references (vLLM, SDXL, Pipecat voice agents, ASGI apps), each with a working
   `cerebrium.toml`.
6. **Check the live docs when this skill does not cover it**, rather than guessing: the
   `cerebrium-docs` MCP server (search plus docs filesystem), any docs page as markdown by
   appending `.md` to its URL, or the index at `https://cerebrium.ai/docs/llms.txt`.

## First run: check state before acting

```bash
cerebrium version                   # installed? if not: pip install cerebrium
cerebrium projects current          # authenticated, and pointed at the intended project?
```

`cerebrium login` opens a browser and fails without a TTY. In CI or headless environments set
`CEREBRIUM_SERVICE_ACCOUNT_TOKEN` (or pass `--service-account-token`) instead: see
[references/cli.md](references/cli.md).

## Zero to a deployed endpoint

Starting with no account: create one at `https://dashboard.cerebrium.ai`. The dashboard is also
where API keys and authentication tokens are created. Compute is billed per second; current rates
and any starting credit are at `https://www.cerebrium.ai/pricing`.

```bash
pip install cerebrium              # thin wrapper that fetches the Go binary on first use
cerebrium login                    # interactive only, needs an account
cerebrium init my-app && cd my-app
cerebrium deploy
```

The full loop:

1. Create an account at `https://dashboard.cerebrium.ai`, then `cerebrium login`.
2. `cerebrium init my-app` writes `main.py` and `cerebrium.toml`.
3. Write a function in `main.py` that takes and returns JSON-serialisable values. Everything at
   module scope runs once per replica at startup: load models there, not inside the function.
4. Set the config ([references/config.md](references/config.md)). Do not skip `disable_auth`
   (the scaffold ships `true`, which makes the endpoint public) or `max_replicas` (default 1,
   the most common cause of queueing).
5. `cerebrium run main.py::run --prompt "test"` executes remotely on the configured hardware.
6. `cerebrium deploy` builds, uploads, starts the app, and prints the endpoint. Build output
   streams from this command and nowhere else.
7. Once running, `cerebrium logs APP_NAME` shows runtime logs.

## Calling the endpoint

```
POST https://api.cerebrium.ai/v4/{PROJECT_ID}/{APP_NAME}/{FUNCTION_NAME}
```

`PROJECT_ID` already includes its `p-` prefix (`p-abcd1234`), so the path reads
`/v4/p-abcd1234/my-app/run`. Do not add a second `p-`.

```bash
curl -X POST 'https://api.cerebrium.ai/v4/p-abcd1234/my-app/run' \
  -H 'Authorization: Bearer <JWT>' \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "hello"}'
```

Response: `{ "run_id": "...", "run_time_ms": 326.34, "result": { ... } }`

- The token comes from the API Keys page of the dashboard, or from a service account.
- With `disable_auth = true` the endpoint takes unauthenticated requests from anyone.
- A function whose name starts with `_` is not exposed. Use that for helpers.
- **Streaming**: `yield` from the function; the response is `text/event-stream` (SSE).
- **Async**: append `?async=true` for fire-and-forget, bounded by `response_grace_period`
  (default 900 seconds, ceiling 12 hours).
- **WebSockets**: require a custom runtime (`[cerebrium.runtime.custom]`) and a `wss://` client.
- Regional hostnames such as `api.aws.us-east-1.cerebrium.ai` still resolve but proxy through
  the global router and add latency. Prefer `api.cerebrium.ai`.

## Secrets and automatic environment variables

```bash
cerebrium secrets add KEY=VALUE OTHER=VALUE   # project-wide; --app APP_ID scopes to one app
```

Secrets arrive as environment variables, read at container start, so an existing replica needs a
restart or redeploy to see a new one. Set automatically for every app: `APP_NAME`, `PROJECT_ID`
(`p-` prefixed), `BUILD_ID`, and `HF_HOME` (`/persistent-storage/.cache/huggingface`).
