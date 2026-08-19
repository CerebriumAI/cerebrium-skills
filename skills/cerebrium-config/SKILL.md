---
name: cerebrium-config
description: >-
  Write, review or fix a cerebrium.toml. Covers every section (deployment, runtime.custom,
  hardware, scaling, dependencies), the value the Cerebrium API applies when a key is omitted,
  the accepted range for each numeric field, and which edits force a full image rebuild. Use
  when authoring or changing Cerebrium configuration, when a deploy is rejected as invalid, or
  when an app scales or authenticates differently than expected.
license: MIT
metadata:
  author: cerebrium
  version: "0.1.0"
---

# cerebrium.toml

One file per app, read by `cerebrium deploy` and `cerebrium run`. Unknown keys are rejected, so
do not invent fields.

Defaults below are the values the app-create API applies when the key is absent. Where a
published table disagrees, prefer these. Set anything that matters explicitly rather than
relying on a default.

## `[cerebrium.deployment]`

| Key | Applied when omitted | Notes |
| --- | --- | --- |
| `name` | required | App name. |
| `python_version` | `3.11` | Changing it forces a full rebuild. |
| `disable_auth` | `true` | **`true` means the endpoint is public.** Set `false` for anything real. |
| `include` / `exclude` | `["*"]` / `[".*"]` | Keep model weights out of `include`. |
| `shell_commands` | `[]` | Run at the end of the build. |
| `pre_build_commands` | `[]` | Run before dependencies install. |
| `docker_base_image_url` | `debian:bookworm-slim` | Changing it forces a full rebuild. |
| `use_uv` | `false` | uv instead of pip. Much faster on large dependency trees. |
| `deployment_initialization_timeout` | `600` | Seconds. Accepted range 60 to 830. Raise it when weights load slowly. |

`cerebrium init` scaffolds `disable_auth = true`. That is a convenience for a first curl, not a
production default. Treat flipping it to `false` as part of the first real deploy.

## `[cerebrium.runtime.custom]`

Only for a custom web server (FastAPI, ASGI, WebSockets, custom batching). Omit it to use the
default Cortex runtime.

| Key | Applied when omitted | Notes |
| --- | --- | --- |
| `port` | `8000` | Must match the port inside `entrypoint`. |
| `entrypoint` | required | List form, e.g. `["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]`. |
| `healthcheck_endpoint` | `""` (TCP ping) | Non-200 marks the instance unhealthy and restarts it. |
| `readycheck_endpoint` | `""` (TCP ping) | Non-200 removes the instance from routing. |

## `[cerebrium.hardware]`

| Key | Applied when omitted | Accepted |
| --- | --- | --- |
| `cpu` | `2.0` | 0.25 to 192 cores. |
| `memory` | `4.0` | 0.05 to 1984 GB. This is RAM, not GPU VRAM. |
| `compute` | `"CPU"` | One name, or a preference-ordered list of up to 5. See **cerebrium-hardware**. |
| `gpu_count` | `0` | 0 to 16. |
| `provider` | platform picks | `aws`, `crusoe` or `nebius`. |
| `region` | platform picks | See **cerebrium-hardware**. |

## `[cerebrium.scaling]`

| Key | Applied when omitted | Accepted | Notes |
| --- | --- | --- | --- |
| `min_replicas` | `0` | 0 to 2000 | Above 0 keeps warm capacity and bills for it. |
| `max_replicas` | `1` | 1 to 2000 | The single most common cause of unexplained queueing. Raise it before load. |
| `replica_concurrency` | `1` on GPU, `100` on CPU | >= 1 | In-flight requests per replica. |
| `scaling_metric` | `concurrency_utilization` | `concurrency_utilization`, `requests_per_second`, `cpu_utilization`, `memory_utilization` | |
| `scaling_target` | `100` | > 0 | Percent for the utilization metrics, absolute rate for `requests_per_second`. |
| `scaling_buffer` | `0` | >= 0 | Extra replicas above what the metric asks for. Only with `concurrency_utilization` or `requests_per_second`. |
| `cooldown` | `10` | 0 to 3600 seconds | Time at reduced load before scaling down. |
| `response_grace_period` | `900` | 16 to 43200 seconds | Also the ceiling on an async run, so 12 hours is the maximum. |
| `evaluation_interval_seconds` | `30` | 6 to 300 | Window metrics are evaluated over. |
| `load_balancing_algorithm` | `round-robin` | `round-robin`, `first-available`, `min-connections`, `random-choice-2` | `first-available` suits `replica_concurrency = 1` GPU work. |
| `compute_tier` | `interruptible` | `interruptible`, `protected` | `protected` is on-demand: higher availability, higher price. |
| `roll_out_duration_seconds` | `0` | >= 0 | Gradual traffic shift to a new revision. Keep 0 while iterating. |

## Dependencies

```toml
[cerebrium.dependencies.pip]
torch = "==2.0.0"        # exact
transformers = "latest"
numpy = ">=1.26"

[cerebrium.dependencies.apt]
ffmpeg = "latest"

[cerebrium.dependencies.conda]
cudatoolkit = "11.7"

[cerebrium.dependencies.paths]
pip = "requirements.txt"
apt = "pkglist.txt"
```

## What forces a full rebuild

Batch these edits together, they are the slow ones:

- `python_version`
- `docker_base_image_url`
- any `[cerebrium.dependencies.apt]` or `[cerebrium.dependencies.conda]` change

Pip-only changes and code changes are much cheaper.

## Worked example

```toml
[cerebrium.deployment]
name = "llm-inference"
python_version = "3.12"
disable_auth = false
include = ["./*", "main.py", "cerebrium.toml"]
exclude = [".*"]
use_uv = true
deployment_initialization_timeout = 800

[cerebrium.hardware]
cpu = 4
memory = 16.0
compute = ["HOPPER_H100", "AMPERE_A100_80GB"]
gpu_count = 1
region = "us-east-1"

[cerebrium.scaling]
min_replicas = 0
max_replicas = 10
replica_concurrency = 1
scaling_metric = "concurrency_utilization"
scaling_target = 100
cooldown = 60
compute_tier = "protected"

[cerebrium.dependencies.pip]
vllm = "latest"
```

## Checklist before deploying

- [ ] `disable_auth` is deliberate, and `false` if the endpoint is not meant to be public
- [ ] `max_replicas` matches the traffic you expect, not the default 1
- [ ] `replica_concurrency` matches the workload (1 for one-request-per-GPU inference)
- [ ] `compute` uses an accepted GPU name (**cerebrium-hardware**) and the region has it
- [ ] weights load from `/persistent-storage`, not baked into the image or in `include`
- [ ] custom runtime: the port in `entrypoint` equals `port`
- [ ] secrets are added with `cerebrium secrets add`, never hardcoded
