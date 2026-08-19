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
is the gate. CI runs both plus a link check.

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
