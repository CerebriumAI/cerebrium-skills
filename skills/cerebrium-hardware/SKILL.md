---
name: cerebrium-hardware
description: >-
  Choose Cerebrium compute: which GPU identifier to put in cerebrium.toml, VRAM and plan tier per
  accelerator, the CPU and memory ceilings the API enforces per GPU, GPU preference lists and the
  family rule, which regions carry which accelerators, provider pinning, spot versus on-demand,
  and where model weights should live. Use when selecting or changing hardware, when a deploy is
  rejected for an unknown compute type or an invalid CPU, memory or GPU count, or when an app
  cannot find capacity in a region.
license: MIT
metadata:
  author: cerebrium
  version: "0.1.0"
---

# Hardware, regions and storage

## Accepted `compute` values

These 13 identifiers are the complete accepted set. Anything else is rejected at deploy time.

| Identifier | VRAM (GB) | Max `gpu_count` | Max CPU per GPU | Max memory per GPU (GB) | Minimum plan |
| --- | --- | --- | --- | --- | --- |
| `CPU` | n/a | 0 | see below | see below | Hobby |
| `TURING_T4` | 16 | 4 | 11 | 44 | Hobby |
| `ADA_L4` | 24 | 4 | 11 | 44 | Hobby |
| `AMPERE_A10` | 24 | 4 | 11 | 44 | Hobby |
| `ADA_L40` | 48 | 4 | 11 | 92 | Hobby |
| `INF2` | n/a | 12 | 8 | 32 | Hobby |
| `AMPERE_A100_40GB` | 40 | 8 | 22 | 284 | Standard |
| `AMPERE_A100_80GB` | 80 | 8 | 22 | 284 | Standard |
| `BLACKWELL_RTX6000` | 96 | 8 | 24 | 218 | Standard |
| `HOPPER_H100` | 80 | 8 | 24 | 256 | Standard |
| `HOPPER_H200` | 141 | 8 | 24 | 256 | Standard |
| `BLACKWELL_B200` | 180 | 8 | 44 | 496 | Standard |
| `TRN1` | 32 | 16 | 8 | 32 | Enterprise |

`BLACKWELL_B300` appears in the published GPU table and is **not** in the accepted set. Do not
use it.

The per-GPU ceilings multiply by `gpu_count`: `HOPPER_H100` with `gpu_count = 2` allows up to 48
CPU and 512 GB. A request that fills a whole node is additionally capped at 90 percent of the
node's capacity, so the largest configurations land slightly under the multiplied figure.

Other rules the API enforces:

- GPU replicas need whole CPU cores. Fractional `cpu` is rejected unless `compute = "CPU"`.
- `compute = "CPU"` requires `gpu_count = 0`. Any accelerator requires `gpu_count >= 1`.
- `memory` takes at most two decimal places.
- `memory` is host RAM, not VRAM. Size VRAM by picking the accelerator, and start with roughly
  the accelerator's VRAM in host memory so weights can be staged before transfer.

## Plan ceilings come first

The project's plan caps hardware before any of the per-type limits apply, so a valid-looking
config can still be refused:

| | Hobby | Standard | Enterprise |
| --- | --- | --- | --- |
| Max `gpu_count` | 1 | 4 | 8 |
| Max `cpu` | 16 | 80 | 352 |
| Max `memory` (GB) | 60 | 160 | 2048 |
| Max GPU replicas | 5 | 30 | 1200 |
| Max CPU replicas | 500 | 1000 | 2000 |
| Apps | 3 | 100 | 200 |

A project can additionally be granted individual compute types outside its plan, so a type
refused on one project may work on another at the same tier. If a compute type is rejected and
the config looks right, the plan is the thing to check.

### CPU-only replicas

`cpu` must be exactly one of `0.25, 0.5, 1, 2, 3, 4, 6, 8, 10, 12, 16, 24, 32, 48, 64, 80`, and
`memory` must be 160 GB or less.

## Preference lists

`compute` takes a preference-ordered list of up to 5 identifiers. This is the single best lever
for availability: the platform places on the first type with capacity.

```toml
[cerebrium.hardware]
compute = ["HOPPER_H100", "AMPERE_A100_80GB", "ADA_L40"]
gpu_count = 1
cpu = 8
memory = 32.0
```

- Every entry must be in the same hardware family. NVIDIA GPUs cannot be mixed with `CPU` or with
  the AWS accelerators (`INF2`, `TRN1`), because one `(cpu, memory, gpu_count)` tuple has to
  satisfy every entry's limits.
- One tuple has to fit the whole list, so the strictest entry sets the ceiling. `ADA_L40` in the
  list above caps memory at 92 GB per GPU even though H100 would allow 256.
- Only list types the model actually fits on. A model needing 80 GB of VRAM will fail on `ADA_L40`.
- `cerebrium run` uses only the first entry.

## Regions

Generally available:

| Region | Location | Provider note |
| --- | --- | --- |
| `us-east-1` | N. Virginia | |
| `us-central1` | Kansas City | set `provider = "nebius"` |
| `eu-north-1` | Stockholm | |
| `eu-north1` | Finland | set `provider = "nebius"` |

`eu-north-1` (hyphen before the digit) and `eu-north1` are different regions on different
providers. So are `us-east-1` and `us-central1`.

On request via support@cerebrium.ai: `us-west-2`, `eu-west-2`, `eu-central-1`, `ap-south-1`,
`ap-northeast-1`, `sa-east-1`, `ca-central-1`, `me-central-1`. `eu-west-2` (London) is currently
refused at deploy time.

Omit `region` to let the platform place the app wherever there is capacity. Pin one only for data
residency or to sit next to a dependency.

### Accelerators by region

| Region | Available |
| --- | --- |
| `us-east-1` | BLACKWELL_B200, HOPPER_H200, HOPPER_H100, AMPERE_A100_80GB, AMPERE_A100_40GB, ADA_L40, ADA_L4, AMPERE_A10, TURING_T4, INF2, TRN1 |
| `us-central1` | BLACKWELL_RTX6000, BLACKWELL_B200, HOPPER_H200 |
| `eu-north1` | HOPPER_H200, HOPPER_H100, ADA_L40 |
| `eu-north-1` | HOPPER_H100, ADA_L40, ADA_L4, AMPERE_A10, TURING_T4, INF2, TRN1 |

CPU workloads run in every region. Pinning a region that does not carry the requested
accelerator is a common cause of an app that deploys but never gets a replica.

## Spot versus on-demand

```toml
[cerebrium.scaling]
compute_tier = "protected"   # on-demand, higher availability, higher price
```

`interruptible` (the default) is spot capacity: cheaper, and a replica can be reclaimed. Use
`protected` for latency-critical or long-running work that cannot absorb a restart.

## Where weights live

| Path | Scope | Use for |
| --- | --- | --- |
| `/persistent-storage` | one region | Model weights and caches for a single-region app. `HF_HOME` already points at `/persistent-storage/.cache/huggingface`. |
| `/global-persistent-storage` | all regions | Data an app deployed across regions must share. |

Reads from persistent storage are cached within each region, so the second cold start in a region
is faster than the first. Each region fills its own cache, which is the reason to put weights on
the global volume for a multi-region app rather than copying per region.

Baking large weights into the image makes every cold start slower and every rebuild longer.
Download to `/persistent-storage` at first start instead, and keep the weights out of `include`.

Move files from the terminal:

```bash
cerebrium ls --region us-east-1
cerebrium cp ./model.bin -r us-east-1
cerebrium download remote/path ./local/path
cerebrium rm remote/path
cerebrium region set us-east-1     # default region for the file commands
```
