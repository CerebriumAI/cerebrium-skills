# Project agent memory

This repository is one artifact distributed to several agent marketplaces at once, so a defect
here reaches every listing. Verify changes by running a validator, not by reading the file.

## The same plugin is declared once per host

`README.md` lists which manifest belongs to which host. The practical consequence is that
metadata is duplicated on purpose and drifts silently:

- A version bump has to touch every manifest that carries one. Find them with
  `grep -rl '"version"' --include='*.json' . | grep -v node_modules`.
- `mcp.json` and `.mcp.json` are both required and neither validates as the other: the Agent
  Plugins standard fixes the path as `mcp.json` and names the remote transport
  `streamable-http`, while the Claude Code convention in `.mcp.json` uses `http` and carries no
  `$schema`. Do not "deduplicate" them.

## Validate against the schema a file declares, not against intuition

`server.json`, `plugin.json` and `mcp.json` each name their own `$schema`. Fetch that URL and
validate the whole document; a length or field check by eye misses the rest. `server.json` in
particular caps `description` at 100 characters, which is easy to exceed while editing prose.

`gemini-extension.json` has no published JSON Schema, so the real check is
`npx -y @google/gemini-cli extensions validate .` (exit 0 = valid). Note that `contextFileName`
makes the file it names mandatory: setting it without adding that file is a hard validation
failure, which is why this repository omits it.

## CI

`.github/workflows/validate.yml` validates every skill against the Agent Skills spec, checks the
marketplace manifests point at real paths, and link-checks all markdown. It does not yet cover
the four distribution manifests above; validate those locally before pushing.

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
