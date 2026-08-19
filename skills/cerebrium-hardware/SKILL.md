---
name: cerebrium-hardware
description: >-
  Choose Cerebrium compute: which GPU name to put in cerebrium.toml, GPU preference lists,
  which regions have which accelerators, provider pinning (aws, crusoe, nebius), spot versus
  on-demand via compute_tier, and where model weights should live (/persistent-storage versus
  /global-persistent-storage). Use when selecting or changing hardware, when a deploy is
  rejected for an unknown compute type, or when an app cannot find capacity in a region.
license: MIT
metadata:
  author: cerebrium
  version: "0.1.0"
---

# Hardware, regions and storage

## Accepted `compute` values

These 13 names are the complete accepted set. Anything else is rejected at deploy time:

```
CPU
TURING_T4
ADA_L4          ADA_L40
AMPERE_A10      AMPERE_A100_40GB   AMPERE_A100_80GB
HOPPER_H100     HOPPER_H200
BLACKWELL_B200  BLACKWELL_RTX6000
INF2            TRN1
```

`BLACKWELL_B300` appears in some published tables and is **not** accepted. Do not use it.

`memory` is host RAM, not VRAM. Size VRAM by picking the accelerator; size `memory` for the
process that feeds it.

## Preference lists

`compute` takes a preference-ordered list of up to 5 names. This is the single best lever for
availability: the platform places on the first type with capacity.

```toml
[cerebrium.hardware]
compute = ["HOPPER_H100", "AMPERE_A100_80GB", "ADA_L40"]
gpu_count = 1
```

Only list types your code actually fits on. A model that needs 80 GB will fail on `ADA_L40`.

## Regions

Generally available:

| Region | Location | Provider note |
| --- | --- | --- |
| `us-east-1` | N. Virginia | |
| `us-central1` | Kansas City | set `provider = "nebius"` |
| `eu-north-1` | Stockholm | |
| `eu-north1` | Finland | set `provider = "nebius"` |

`us-central1` and `eu-north1` are Nebius regions and look confusingly similar to the AWS names.
`eu-north-1` (hyphen before the digit) and `eu-north1` are different regions on different
providers.

On request via support@cerebrium.ai: `us-west-2`, `eu-west-2`, `eu-central-1`, `ap-south-1`,
`ap-northeast-1`, `sa-east-1`, `ca-central-1`, `me-central-1`.

Omit `region` to let the platform place the app wherever there is capacity. Pin a region only
for data residency, or to sit next to a dependency.

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
