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
npx -y skills-ref validate skills/<name>   # exit code is the result, not the console output
claude plugin validate .                   # manifest only, it does not read SKILL.md
```

`claude plugin validate` exits 0 on a skill whose frontmatter breaks the spec, so `skills-ref`
is the gate. CI runs both plus a link check.

## Writing a skill

- One lane per skill, and route from `skills/cerebrium/SKILL.md` rather than growing a monolith.
- Skills live at the repository root under `skills/`. The plugin manifests wrap that same set, they
  do not hold a second copy.
- Keep `SKILL.md` under 500 lines. Long reference material goes in `references/` alongside it and
  is loaded on demand.
- The `description` is the only thing an agent sees before deciding to load the skill. Say what
  the skill does *and* when to reach for it.
- `name` must be lowercase, hyphen-separated, and identical to the directory name.
- Never send an agent to the dashboard for something the CLI can do. An agent has a terminal.
- Flag mutations that cost money or take traffic (`deploy`, `run`, `apps scale`, `apps delete`)
  and tell the agent to confirm with the user first.

## Releasing

Bump `version.txt`, the `version` in `.claude-plugin/marketplace.json` and
`.claude-plugin/plugin.json`, and the `metadata.version` of any changed skill,
then tag. Directory listings pin a `ref` or `sha`, so an untagged change does not reach
installed users.
