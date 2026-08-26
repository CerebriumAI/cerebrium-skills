# Contributing

## The one rule

**Verify against the source of truth, not against the docs.** Every default, enum, flag and
command signature in these skills was read out of the CLI or the API validator, because the
published tables have drifted from both in several places. When a skill and a docs page
disagree, fix the docs page too, and say so in the pull request.

Where to check:

| Claim | Source of truth |
| --- | --- |
| A command exists, its args or its flags | `CerebriumAI/cerebrium`, `internal/commands/**` |
| A `cerebrium.toml` key is accepted | `CerebriumAI/cerebrium`, `pkg/projectconfig/config.go` |
| The value applied when a key is omitted | `dashboard-backend`, `go-build-service/src/functions/rest-api/projects/apps/create_app/api/api.go` |
| An accepted range or enum | `dashboard-backend`, `go-build-service/src/libs/apps/inputs.go` |

## Local checks

```bash
npx -y skills-ref validate skills/cerebrium   # exit code is the result, not the console output
claude plugin validate .                   # manifest only, it does not read SKILL.md
```

`claude plugin validate` exits 0 on a skill whose frontmatter breaks the spec, so `skills-ref`
is the gate. CI never runs `claude plugin validate`. It runs `npx -y skills-ref validate` on
every skill and reads the exit status, checks manifest and frontmatter consistency, and runs a
lychee link check.

## The drift check

`.github/workflows/skill-drift.yml` applies the one rule automatically. It reads the command,
flag and `cerebrium.toml` surface out of the CLI source with `tools/surfacedump`, compares it to
the skill with `tools/check_drift.py`, and fails the pull request when the two disagree. It runs
weekly as well, and opens a pull request with the report when it finds something.

Two things to know before trusting or arguing with it.

- It compares against the latest **released** tag of `CerebriumAI/cerebrium`, never the default
  branch. A flag can exist on the default branch and be in no release, and an agent following
  the skill runs the released binary.
- A `cerebrium.toml` key the skill documents and the CLI does not parse is advisory, never a
  failure. The CLI uploads the file verbatim, so the backend accepts keys the CLI has no field
  for. `[cerebrium.experimental]` is one.

`tools/expectations.json` is the only hand-maintained file. Add an entry there when the checker
is wrong about a specific case, with the reason. An entry that exists only to quieten it is a
bug in the checker.

## Writing a skill

- One skill. `skills/cerebrium/SKILL.md` is the always-loaded core: workflow, rules, endpoint
  shapes. Lookup material (tables, enums, flag lists) lives in `skills/cerebrium/references/` and
  is loaded on demand. Add a new reference file rather than growing the core past ~200 lines, and
  add a new skill only for a genuinely separate tool or job, not another chapter of this one.
- The `description` is the only thing an agent sees before deciding to load the skill. Say what
  the skill does *and* when to reach for it.
- `name` must be lowercase, hyphen-separated, and identical to the directory name.
- Never send an agent to the dashboard for something the CLI can do. An agent has a terminal.
- Flag mutations that cost money or take traffic (`deploy`, `run`, `apps scale`, `apps delete`)
  and tell the agent to confirm with the user first.

## Releasing

Bump the `version` in `.claude-plugin/marketplace.json` and `.claude-plugin/plugin.json`, the
`metadata.version` of any changed skill, and `server.json` if the docs MCP entry changed, then
tag `vX.Y.Z`. Directory listings pin a `ref` or `sha`, so an untagged change does not reach
installed users. The Claude plugin directory mirrors GitHub automatically after first
publication, so no re-submission is needed for updates.

## The docs site serves the same skill

`skills/cerebrium/SKILL.md` is the source of truth for the Cerebrium Agent Skill. The same
document is served at `cerebrium.ai/docs/skill.md` out of `CerebriumAI/documentation`, because
two different documents under one name is how this went wrong once already.

`.github/workflows/skill-sameness.yml` runs `tools/check_skill_sameness.py`, which compares the
body byte for byte plus the frontmatter `description` and `license`. The frontmatter `name` and
the whole `metadata` block are allowed to differ, since Mintlify needs its own. It fails closed:
a 404 or an unreachable host is red, never a skip. It runs daily as well as on pull requests,
because a change in the other repository does not trigger CI here.

So an edit to the skill body is two pull requests, and they have to land together. Open the one
in `CerebriumAI/documentation` first, or this repository's check stays red until it merges.
Relative links do not resolve on the docs site, so a link to a reference file is written with
the relative path as the link text and the absolute GitHub blob URL as the target.
