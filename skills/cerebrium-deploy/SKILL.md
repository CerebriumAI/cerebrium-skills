---
name: cerebrium-deploy
description: >-
  Deploy a Cerebrium app and call it: the deploy loop, the endpoint URL and auth header,
  the REST response shape, streaming (SSE), WebSocket and async invocation, secrets and
  automatic environment variables, and non-interactive deploys from CI with a service
  account token. Use when shipping code to Cerebrium, wiring GitHub Actions, or working out
  how a client should call a deployed app.
license: MIT
metadata:
  author: cerebrium
  version: "0.1.0"
---

# Deploying and calling an app

## The loop

1. `cerebrium init my-app` writes `main.py` and `cerebrium.toml`.
2. Write a function in `main.py` that takes and returns JSON-serialisable values. Everything at
   module scope runs once per replica at startup: load models there, not inside the function.
3. Set the config (see **cerebrium-config**). Do not skip `disable_auth` and `max_replicas`, and
   remember that a key left out of the file is reset to its default on every deploy.
4. `cerebrium run main.py::run --prompt "test"` executes remotely on the configured hardware.
   This bills compute. It is not a local emulator.
5. `cerebrium deploy` builds the image, uploads the code, starts the app, and prints the endpoint.
6. Build output streams from `cerebrium deploy` itself. Once the app is running,
   `cerebrium logs APP_NAME` shows runtime logs (see **cerebrium-troubleshoot**).

Useful deploy flags:

```bash
cerebrium deploy -y                     # or --yes: skip the confirmation prompt
cerebrium deploy --detach               # kick off the build and exit, Ctrl+C will not cancel it
cerebrium deploy --disable-build-logs
cerebrium deploy --config-file ./other.toml
cerebrium deploy --name override-name
cerebrium deploy --log-level DEBUG
```

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

Response:

```json
{ "run_id": "52eda406-...", "run_time_ms": 326.34, "result": { "some": "data" } }
```

- The token comes from the API Keys page of the dashboard, or from a service account.
- With `disable_auth = true` the endpoint takes unauthenticated requests from anyone.
- **A function whose name starts with `_` is not exposed.** Use that for helpers.
- Regional hostnames such as `api.aws.us-east-1.cerebrium.ai` still resolve but proxy through the
  global router and add latency. Prefer `api.cerebrium.ai`.

### Streaming

`yield` from the function. Responses are sent as `text/event-stream` (SSE), one event per yield.

### Async

Append `?async=true` for fire-and-forget. The run is bounded by `response_grace_period`, whose
ceiling is 12 hours, so raise it from the 900 second default for long jobs.

### WebSockets

Require a custom runtime (`[cerebrium.runtime.custom]`) and a `wss://` client. The default Cortex
runtime cannot serve them.

## Secrets and environment variables

```bash
cerebrium secrets add KEY=VALUE OTHER=VALUE   # project-wide
cerebrium secrets add KEY=VALUE --app APP_ID  # scoped to one app
cerebrium secrets list
```

Secrets arrive as environment variables and are read at container start, so an existing replica
needs a restart or redeploy to see a new one.

Set for every app automatically:

| Variable | Value |
| --- | --- |
| `APP_NAME` | app name from `cerebrium.toml` |
| `PROJECT_ID` | project id, `p-` prefixed |
| `BUILD_ID` | current build |
| `HF_HOME` | `/persistent-storage/.cache/huggingface` |

## CI/CD (non-interactive)

`cerebrium login` needs a browser and fails in CI. Use a service account key from the API Keys
page of the dashboard instead, and pass it by environment variable:

```yaml
env:
  CEREBRIUM_SERVICE_ACCOUNT_TOKEN: ${{ secrets.CEREBRIUM_SERVICE_ACCOUNT_TOKEN }}
  CEREBRIUM_PROJECT_ID: ${{ secrets.CEREBRIUM_PROJECT_ID }}
steps:
  - run: pip install cerebrium
  - run: cerebrium projects set $CEREBRIUM_PROJECT_ID
  - run: cerebrium deploy -y --disable-build-logs
```

`--service-account-token <token>` works as a flag on any command if an environment variable is
awkward. Keep separate projects for development and production so a pipeline cannot overwrite a
live app.

## Private base images

Log in to the registry before deploying an app that pulls one:

```bash
docker login -u your-dockerhub-username     # not the bare `docker login` OAuth flow
```
