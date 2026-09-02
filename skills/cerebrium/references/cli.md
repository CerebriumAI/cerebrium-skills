# CLI reference

Installed with `pip install cerebrium` (a thin wrapper that fetches the Go binary on first use),
`brew tap cerebriumai/tap && brew install cerebrium`, or a release archive from
`https://github.com/CerebriumAI/cerebrium/releases`.

Commands not listed here do not exist. Check before inventing one.

## Global flags

Valid on every command:

| Flag | Effect |
| --- | --- |
| `-v`, `--verbose` | Verbose logging. |
| `--no-color`, `--no-ansi`, `--disable-animation` | Plain output, no colour and no animation. |
| `--service-account-token <token>` | Authenticate without a session. Takes precedence over the environment variable and the stored token. |

When something other than a human reads the output, reach for `-o json` on the commands that
accept it rather than suppressing colour. Those commands are marked below.

## Authentication

```bash
cerebrium login                       # interactive, opens a browser
export CEREBRIUM_SERVICE_ACCOUNT_TOKEN=...   # headless and CI, no login needed
cerebrium save-auth-config ACCESS_TOKEN [REFRESH_TOKEN] [PROJECT_ID]
cerebrium save-auth-config ACCESS_TOKEN --project-id p-abcd1234   # instead of the positional id
```

`login` fails without a TTY by design. In CI, set the environment variable or pass
`--service-account-token`, then select the project with `cerebrium projects set`.

## Project and region

```bash
cerebrium projects list               # -o table|json
cerebrium projects current
cerebrium projects set p-abcd1234     # ids are p- prefixed; `project` is a legacy alias
cerebrium region get
cerebrium region set us-east-1        # default region for the file commands
```

## Build and run

| Command | Notes |
| --- | --- |
| `cerebrium init <name>` | Writes `main.py` and `cerebrium.toml`. Name is required. `--dir` chooses where. |
| `cerebrium deploy` | `--name`, `--config-file ./cerebrium.toml`, `-y`/`--disable-confirmation`/`--yes` (the three are equivalent), `--detach`, `--disable-build-logs`, `--disable-syntax-check`, `--log-level DEBUG\|INFO`. |
| `cerebrium run <file>[::func]` | `--data '{"k":"v"}'`, `-r`/`--region`, and any `--key value` pair is passed through to the function. Runs in the cloud, not locally. |

```bash
cerebrium run main.py::run --prompt "hello"
cerebrium run script.py::process --region us-east-1
cerebrium deploy -y --disable-build-logs
```

Build logs stream from `cerebrium deploy` itself and nowhere else. There is no `builds` command,
and `--detach` or `--disable-build-logs` gives that stream up, so a failed build then has to be
diagnosed by redeploying without them.

## Inspect

| Command | Notes |
| --- | --- |
| `cerebrium apps list` | All apps and their state. `-o`/`--output table\|json`. |
| `cerebrium apps get APP_ID` | The config actually in effect. `-o`/`--output table\|json`. |
| `cerebrium logs APP_NAME` | **Runtime logs only.** Follows by default. `--no-follow`, `--since 30m` (`w\|d\|h\|m\|s` or `YYYY-MM-DD HH:mm:ss`). |
| `cerebrium containers list APP_NAME` | Per-container state. `-o`/`--output table\|json`. |
| `cerebrium runs list APP_NAME` | Recent invocations. `--async` narrows it to asynchronous runs. `-o`/`--output table\|json`. |
| `cerebrium status` | Platform status. `-o`/`--output table\|json`. |
| `cerebrium version` | CLI version. |

## Change live infrastructure

Confirm with the user before any of these:

| Command | Effect |
| --- | --- |
| `cerebrium apps scale APP_ID` | `--min-replicas`, `--max-replicas`, `--cooldown`, `--response-grace-period`. Changes a running app and can start billing immediately. |
| `cerebrium apps delete APP_ID` | Destructive. |
| `cerebrium deploy` | Builds and starts a new revision. |
| `cerebrium run` | Starts billable compute on the configured hardware. |

## Secrets

```bash
cerebrium secrets add KEY=VALUE OTHER=VALUE
cerebrium secrets add KEY=VALUE --app APP_ID     # app-scoped instead of project-wide
cerebrium secrets list                           # -o table|json, --app APP_ID to scope it
cerebrium secrets list --show-values             # values are hidden by default
```

Secrets are read at container start, so an existing replica needs a restart or redeploy.

## Persistent storage

```bash
cerebrium ls [path]                      # -o table|json
cerebrium cp <local_path> [remote_path]
cerebrium download <remote_path> [local_path]
cerebrium rm <remote_path>
```

These act on the default region (`cerebrium region set`) unless given `--region`/`-r`.

## CLI configuration

```bash
cerebrium config list
cerebrium config get <key>
cerebrium config set <key> <value>
cerebrium config edit
cerebrium config telemetry status
cerebrium config telemetry enable
cerebrium config telemetry disable
```

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
