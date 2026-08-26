#!/usr/bin/env bash
# Build the ZIP submitted to the OpenAI plugin portal.
#
# Never zip the repository root by hand. The portal picks one manifest to
# convert, and when the root Agent Plugins `plugin.json` is present it converts
# that one instead of `.claude-plugin/plugin.json`. The Agent Plugins 1.0.0
# schema sets additionalProperties:false and has no `interface` property, so the
# whole interface block -- display name, short description, logo, composer icon,
# default prompts -- is reported as an unknown field and silently dropped.
# Excluding `plugin.json` and `.agents/` from the archive is what moves the
# portal onto `.claude-plugin/plugin.json`, which is the file it documents.
# Both stay in the repository: Cursor loads the root manifest.

set -eu

repo_root=$(cd "$(dirname "$0")/.." && pwd)
cd "$repo_root"

out=${1:-"$repo_root/cerebrium-openai-plugin.zip"}

for required in .claude-plugin/plugin.json skills/cerebrium/SKILL.md; do
    if [ ! -f "$required" ]; then
        echo "build-openai-archive: missing required file: $required" >&2
        exit 1
    fi
done

rm -f "$out"

# Build from a clean checkout of HEAD so uncommitted or ignored files never ship.
staging=$(mktemp -d)
trap 'rm -rf "$staging"' EXIT
git archive --format=tar HEAD | tar -x -C "$staging"

rm -f "$staging/plugin.json"
rm -rf "$staging/.agents"

(cd "$staging" && zip -q -r "$out" . -x '.git/*')

echo "build-openai-archive: wrote $out"
