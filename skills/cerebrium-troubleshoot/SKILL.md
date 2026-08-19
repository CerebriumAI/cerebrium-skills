---
name: cerebrium-troubleshoot
description: >-
  Diagnose a Cerebrium app from the terminal: read build and runtime logs, inspect containers,
  list runs, check app state and scaling, and work through the usual failures (build timeouts,
  a custom runtime that never becomes ready, requests that queue, 401s, no replicas in a pinned
  region, slow cold starts). Use when a deploy fails, an app returns errors, latency is bad, or
  an app is not scaling as configured.
license: MIT
metadata:
  author: cerebrium
  version: "0.1.0"
---

# Diagnosing a Cerebrium app

Everything here is terminal-only. Do not send the user to the dashboard for logs, metrics or
timings.

## Inspection loop

```bash
cerebrium apps list                    # what exists, and its state
cerebrium apps get APP_ID              # config actually in effect, including scaling
cerebrium logs APP_NAME                # follows by default
cerebrium logs APP_NAME --no-follow --since 30m
cerebrium containers list APP_NAME     # per-container state: pending, running, restarting
cerebrium runs list APP_NAME           # recent invocations
cerebrium status                       # platform status, before assuming it is your code
```

Start with `apps get`. Config drift (a `max_replicas` or `disable_auth` that is not what the
local TOML says) explains a surprising share of reports, since `cerebrium apps scale` and the
dashboard can both change a live app.

## Common failures

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Build fails partway through apt or pip | A dependency, not the platform. The failing command is in the build log. | `cerebrium logs APP_NAME`, pin the version, batch apt changes (they force a full rebuild). |
| Build times out during model load | `deployment_initialization_timeout` (default 600s) | Raise it, ceiling 830. Better: move weights to `/persistent-storage`. |
| Custom runtime deploys but never serves traffic | `port` does not match the port inside `entrypoint`, or `readycheck_endpoint` is not answering 200 | Align them. An unready instance is silently removed from routing. |
| App is up, requests queue or time out | `max_replicas` is 1 by default | Raise `max_replicas`, and check `replica_concurrency` (1 per replica on GPU). |
| Deployed, but no replica ever starts | The pinned `region` does not carry the requested `compute`, or there is no capacity | Widen `compute` into a preference list, or drop the `region` pin. See **cerebrium-hardware**. |
| 401 or 403 from the endpoint | `disable_auth = false` and no or wrong `Authorization: Bearer` | Send a JWT from API Keys, or a service account token. |
| Anyone on the internet can call it | `disable_auth = true`, which is what `cerebrium init` scaffolds | Set `false` and redeploy. |
| Secret is missing at runtime | Secrets load at container start | `cerebrium secrets add`, then redeploy or restart. |
| Replica restarts under load | `compute_tier = "interruptible"` (spot) reclamation | Set `compute_tier = "protected"`. |

## Cold starts

Measure first: startup timings are in `cerebrium logs APP_NAME`. Do not quote a platform-wide
cold start number, it depends entirely on image size and what the app loads.

Then, in order of payoff:

1. Move every model load and client init to module scope so it happens once per replica.
2. Serve weights from `/persistent-storage` instead of baking them into the image.
3. Use a fast loader (Tensorizer, FlashPack) for large weights.
4. Enable checkpointing to capture state after initialisation.
5. Only then buy warmth: `min_replicas > 0`, `scaling_buffer`, or a longer `cooldown`. This is
   the option that costs money continuously, so raise it with the user first.

Reference: `https://cerebrium.ai/docs/performance/faster-cold-starts` and
`https://cerebrium.ai/docs/performance/checkpointing`.

The full command surface, including the flags for each command, is in **cerebrium-cli**.
