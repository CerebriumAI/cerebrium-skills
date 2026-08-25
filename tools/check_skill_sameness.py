#!/usr/bin/env python3
"""Fail when this repository's skill and the copy served on the docs site diverge.

`skills/cerebrium/SKILL.md` here is the source of truth for the Cerebrium Agent Skill. The
same document is served at `cerebrium.ai/docs/skill.md` out of `CerebriumAI/documentation`.
Two documents under one name is the thing this guards against.

This does NOT compare whole files. It compares:

  * the body, meaning everything after the closing frontmatter `---`, byte for byte
  * the frontmatter `description`
  * the frontmatter `license`

The frontmatter `name` and the whole `metadata` block are allowed to differ, because Mintlify
needs its own `metadata` key and its own page name. Nothing else may differ.

It fails closed. A non-200, an unreachable host, a remote file that does not exist, or
frontmatter that will not parse on either side is a failure, never a skip. A 404 has to read
as red, because the failure mode being guarded against is exactly the docs copy going missing
or being replaced by something else.

Exit status is the result: 0 identical, 1 anything else. There is no advisory mode.

    python3 tools/check_skill_sameness.py
    python3 tools/check_skill_sameness.py --remote-url http://127.0.0.1:8000/skill.md
"""

import argparse
import difflib
import sys
import urllib.error
import urllib.request
from pathlib import Path

REMOTE_URL = "https://raw.githubusercontent.com/CerebriumAI/documentation/master/skill.md"
LOCAL_PATH = "skills/cerebrium/SKILL.md"
COMPARED_FIELDS = ("description", "license")
TIMEOUT_SECONDS = 30


class Mismatch(Exception):
    """Any reason the two copies cannot be shown to be the same."""


def fetch(url):
    """Return the remote document as text, or raise. Never returns on a non-200."""
    if url.startswith("file://") or "://" not in url:
        raise Mismatch(f"{url}: refusing to read the remote copy off the local filesystem")
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:
            if response.status != 200:
                raise Mismatch(f"{url}: HTTP {response.status}")
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        note = " (the docs site is not serving the skill)" if error.code == 404 else ""
        raise Mismatch(f"{url}: HTTP {error.code}{note}") from error
    except urllib.error.URLError as error:
        raise Mismatch(f"{url}: unreachable, {error.reason}") from error
    except UnicodeDecodeError as error:
        raise Mismatch(f"{url}: not UTF-8, {error}") from error


def split_frontmatter(text, source):
    """Return (frontmatter, body). The body starts after the closing fence's newline."""
    lines = text.split("\n")
    if not lines or lines[0].rstrip("\r") != "---":
        raise Mismatch(f"{source}: does not open with a `---` frontmatter fence")
    for index in range(1, len(lines)):
        if lines[index].rstrip("\r") == "---":
            return "\n".join(lines[1:index]), "\n".join(lines[index + 1 :])
    raise Mismatch(f"{source}: frontmatter is never closed by a `---` fence")


def unquote(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        inner = value[1:-1]
        return inner.replace('\\"', '"') if value[0] == '"' else inner.replace("''", "'")
    return value


def field(frontmatter, key, source):
    """Read one top-level scalar, inline or quoted or a `>`/`|` block."""
    lines = frontmatter.split("\n")
    for index, line in enumerate(lines):
        line = line.rstrip("\r")
        if line[:1].isspace() or not line.startswith(key + ":"):
            continue
        rest = line[len(key) + 1 :].strip()
        if rest not in (">", ">-", ">+", "|", "|-", "|+"):
            if not rest:
                raise Mismatch(f"{source}: frontmatter `{key}` is empty")
            return unquote(rest)
        block = []
        for continuation in lines[index + 1 :]:
            continuation = continuation.rstrip("\r")
            if not continuation.strip():
                block.append("")
            elif continuation[:1].isspace():
                block.append(continuation.strip())
            else:
                break
        if not any(block):
            raise Mismatch(f"{source}: frontmatter `{key}` block is empty")
        if rest.startswith("|"):
            return "\n".join(block).strip("\n")
        # A folded scalar: run of lines becomes one line, a blank line becomes a break.
        folded, run = [], []
        for entry in block:
            if entry:
                run.append(entry)
            elif run:
                folded.append(" ".join(run))
                run = []
        if run:
            folded.append(" ".join(run))
        return "\n".join(folded)
    raise Mismatch(f"{source}: frontmatter has no `{key}`")


def report_body_difference(local_body, remote_body, remote_url):
    print(f"the body of {LOCAL_PATH} and {remote_url} differ", file=sys.stderr)
    if "\r\n" in remote_body and "\r\n" not in local_body:
        print("the remote copy uses CRLF line endings and this one uses LF", file=sys.stderr)
    diff = difflib.unified_diff(
        local_body.splitlines(keepends=True),
        remote_body.splitlines(keepends=True),
        fromfile=LOCAL_PATH,
        tofile=remote_url,
        n=2,
    )
    sys.stderr.writelines(diff)
    print(file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--local-path", default=LOCAL_PATH, help=f"default {LOCAL_PATH}")
    parser.add_argument("--remote-url", default=REMOTE_URL, help=f"default {REMOTE_URL}")
    args = parser.parse_args()

    try:
        local_file = Path(args.local_path)
        if not local_file.is_file():
            raise Mismatch(f"{args.local_path}: not found")
        local_frontmatter, local_body = split_frontmatter(
            local_file.read_text(encoding="utf-8"), args.local_path
        )
        remote_frontmatter, remote_body = split_frontmatter(
            fetch(args.remote_url), args.remote_url
        )

        differences = []
        for key in COMPARED_FIELDS:
            here = field(local_frontmatter, key, args.local_path)
            there = field(remote_frontmatter, key, args.remote_url)
            if here != there:
                differences.append(
                    f"frontmatter `{key}` differs\n"
                    f"  {args.local_path}: {here!r}\n"
                    f"  {args.remote_url}: {there!r}"
                )
        if local_body != remote_body:
            report_body_difference(local_body, remote_body, args.remote_url)
            differences.append("the body differs")
    except Mismatch as error:
        print(f"skill sameness check failed: {error}", file=sys.stderr)
        return 1

    if differences:
        for difference in differences:
            print(difference, file=sys.stderr)
        print(
            "\nThese two copies must stay identical. Update whichever one is wrong, in "
            "CerebriumAI/cerebrium-skills or in CerebriumAI/documentation, and land both.",
            file=sys.stderr,
        )
        return 1

    print(f"{args.local_path} matches {args.remote_url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
