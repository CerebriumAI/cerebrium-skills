# Diagnosing a Cerebrium app

Everything here is terminal-only. Do not send the user to the dashboard for logs, metrics or
timings.

## Inspection loop

```bash
cerebrium apps list                    # what exists, and its state
cerebrium apps get APP_ID              # the config actually in effect, including scaling
cerebrium logs APP_NAME                # runtime logs, follows by default
cerebrium logs APP_NAME --no-follow --since 30m
cerebrium containers list APP_NAME     # per-container state: pending, running, restarting
cerebrium runs list APP_NAME           # recent invocations
cerebrium status                       # platform status, before assuming it is your code
```

Start with `apps get`. Comparing it against the local `cerebrium.toml` catches the two most
common surprises at once: a setting someone changed with `cerebrium apps scale`, and a setting
that reverted because the deployed TOML did not carry it.

**Build logs are not in `cerebrium logs`.** They stream from `cerebrium deploy` while the build
runs. If a build failed and the output is gone, redeploy without `--detach` and without
`--disable-build-logs`.

## Common failures

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Build fails partway through apt or pip | A dependency, not the platform | Read the failing command in the deploy output, pin the version, batch apt changes (they force a full rebuild). |
| Build times out during model load | `deployment_initialization_timeout` (default 600s) | Raise it, ceiling 830. Better: move weights to `/persistent-storage`. |
| A setting reverted after a deploy | The key was absent from `cerebrium.toml`, so the deploy reset it | Put every value that matters in the file. See `references/config.md`. |
| Deploy rejected for CPU, memory or GPU count | Per-type limits, or the plan's ceiling, whichever is stricter | Check both tables in `references/hardware.md`. |
| Custom runtime deploys but never serves traffic | `port` does not match the port inside `entrypoint`, or `readycheck_endpoint` is not answering 200 | Align them. An unready instance is silently removed from routing. |
| App is up, requests queue or time out | `max_replicas` is 1 by default | Raise `max_replicas`, and check `replica_concurrency` (1 per replica on an accelerator). |
| Deployed, but no replica ever starts | The pinned `region` does not carry the requested `compute`, or there is no capacity | Widen `compute` into a preference list, or drop the `region` pin. See `references/hardware.md`. |
| Scaling never triggers on CPU or memory | `cpu_utilization` and `memory_utilization` need `min_replicas >= 1` | Set a floor, or scale on concurrency instead. |
| 401 or 403 from the endpoint | `disable_auth = false` and no or wrong `Authorization: Bearer` | Send a JWT from API Keys, or a service account token. |
| Anyone on the internet can call it | `disable_auth = true`, which is what `cerebrium init` scaffolds | Set `false` and redeploy. |
| Secret is missing at runtime | Secrets load at container start | `cerebrium secrets add`, then redeploy or restart. |
| Replica restarts under load | `compute_tier = "interruptible"` (spot) reclamation | Set `compute_tier = "protected"`. |

## Cold starts

Measure first: container startup appears in `cerebrium logs APP_NAME`. Do not quote a
platform-wide cold start number, it depends entirely on image size and what the app loads.

Then, in the order the platform documentation recommends:

1. **Store weights on `/persistent-storage`** instead of baking them into the image. Reads are
   cached per region, so later cold starts in that region are faster.
2. **Run initialisation at module scope** so model loads and client setup happen once per
   container, not per request.
3. **Load weights straight to the GPU** with Tensorizer or FlashPack for large models.
4. **Restore from a checkpoint** (`[cerebrium.experimental] checkpointing = true` plus the
   in-container trigger) when initialisation repeats work that never changes.
5. **Then buy warmth**: `min_replicas`, `scaling_buffer`, a longer `cooldown`, or a lower
   `scaling_target` for headroom. These cost money continuously, so raise them with the user first.

Reference: `https://cerebrium.ai/docs/performance/faster-cold-starts` and
`https://cerebrium.ai/docs/performance/checkpointing`.

The full command surface, including the flags for each command, is in `references/cli.md`.
