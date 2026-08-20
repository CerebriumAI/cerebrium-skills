#!/usr/bin/env python3
"""Compare the Cerebrium CLI surface against what the skill documents.

Reads the JSON written by tools/surfacedump against a checkout of
CerebriumAI/cerebrium, and the skill markdown in this repository. Prints every
divergence and exits non-zero when any of them is an error.

Two directions, deliberately not symmetric.

  CLI has it, skill does not      error.    An agent that reads the skill will
                                            never reach the feature.
  Skill has it, CLI does not      error for commands and flags, advisory for
                                            cerebrium.toml keys. The CLI uploads
                                            the TOML verbatim, so its struct is
                                            a subset of the keys the backend
                                            accepts and a key it does not parse
                                            is not automatically wrong.

Scope rules, chosen so each direction fails in the safe way.

  Documented-for-a-command, forward direction: the flag appears anywhere in the
  same markdown section (## heading to the next ## heading) as the command.
  Generous, because docs routinely mention a shared flag once per section.

  Attributed-to-a-command, reverse direction: the flag is on the same table row
  or example line as the command. Strict, and prose is skipped entirely,
  because "given --region" in a sentence that happens to name a command is not
  a claim that the command takes that flag.

Usage:
    python3 tools/check_drift.py --surface surface.json --skills skills [--ref v2.6.0]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from dataclasses import dataclass, field

# Cobra builds these itself, they are not part of the documented surface.
BUILTIN_COMMANDS = {"help", "completion"}

FLAG_RE = re.compile(r"(?<![\w-])--([a-z0-9][a-z0-9-]*)(?![\w-])")
SHORT_RE = re.compile(r"(?<![\w-])-([A-Za-z])(?![\w-])")
COMMAND_TOKEN_RE = re.compile(r"[a-z][a-z0-9-]*$")


@dataclass
class Finding:
    kind: str
    severity: str  # "error" or "advisory"
    subject: str
    detail: str
    where: str = ""

    def line(self) -> str:
        location = f" [{self.where}]" if self.where else ""
        return f"{self.severity.upper():9} {self.kind:24} {self.subject}{location}\n          {self.detail}"


@dataclass
class Doc:
    """One markdown file, sliced the two ways the checks need."""

    path: str
    sections: list[tuple[str, list[str]]] = field(default_factory=list)
    # (line number, text) for table rows and fenced code lines only
    literal_lines: list[tuple[int, str]] = field(default_factory=list)
    text: str = ""


def load_docs(root: pathlib.Path) -> list[Doc]:
    docs = []
    for path in sorted(root.rglob("*.md")):
        raw = path.read_text(encoding="utf-8")
        lines = raw.splitlines()
        doc = Doc(path=str(path), text=raw)

        heading, bucket = "(preamble)", []
        in_fence = False
        for number, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("```"):
                in_fence = not in_fence
                continue
            if not in_fence and stripped.startswith("## "):
                doc.sections.append((heading, bucket))
                heading, bucket = stripped[3:].strip(), []
            bucket.append(line)
            if in_fence or stripped.startswith("|"):
                doc.literal_lines.append((number, line))
        doc.sections.append((heading, bucket))
        docs.append(doc)
    return docs


def mentions(text: str, command_path: str) -> bool:
    """True when the text names this exact command, e.g. `cerebrium apps get`."""
    pattern = r"(?<![\w-])cerebrium\s+" + r"\s+".join(map(re.escape, command_path.split())) + r"(?![\w-])"
    return re.search(pattern, text) is not None


def flags_in(text: str) -> set[str]:
    return {"--" + m.group(1) for m in FLAG_RE.finditer(text)} | {
        "-" + m.group(1) for m in SHORT_RE.finditer(text)
    }


def documented_names(flag: dict) -> set[str]:
    names = {"--" + flag["name"]}
    if flag.get("shorthand"):
        names.add("-" + flag["shorthand"])
    return names


def check_commands(surface: dict, docs: list[Doc], skip: set[str]) -> list[Finding]:
    findings = []
    real = {c["path"] for c in surface["commands"] if c["path"]}
    for command in surface["commands"]:
        path = command["path"]
        if not path or command.get("hidden") or not command["runnable"]:
            continue
        if path.split()[0] in BUILTIN_COMMANDS or path in skip:
            continue
        if not any(mentions(doc.text, path) for doc in docs):
            findings.append(
                Finding(
                    "command-undocumented",
                    "error",
                    f"cerebrium {path}",
                    "the CLI has this command and no skill file names it",
                )
            )

    # The other direction: a command the skill names that the CLI does not have.
    roots = {p.split()[0] for p in real}
    for doc in docs:
        for number, line in doc.literal_lines:
            for match in re.finditer(r"(?<![\w-])cerebrium\s+(.*)", line):
                tokens = match.group(1).split()
                if not tokens or tokens[0].startswith("-"):
                    continue
                if not COMMAND_TOKEN_RE.match(tokens[0]) or tokens[0] not in roots:
                    if COMMAND_TOKEN_RE.match(tokens[0]) and tokens[0] not in roots:
                        findings.append(
                            Finding(
                                "command-invented",
                                "error",
                                f"cerebrium {tokens[0]}",
                                "the skill names this command and the CLI does not have it",
                                f"{doc.path}:{number}",
                            )
                        )
                    continue
                # Walk as deep as the CLI actually goes, no further.
                path = tokens[0]
                for token in tokens[1:]:
                    if not COMMAND_TOKEN_RE.match(token) or f"{path} {token}" not in real:
                        break
                    path = f"{path} {token}"
    return findings


def check_flags(surface: dict, docs: list[Doc], expectations: dict) -> list[Finding]:
    findings = []
    global_flags = set()
    for flag in surface["global_flags"]:
        global_flags |= documented_names(flag)

    skip_missing = {
        (item["command"], item["flag"]) for item in expectations.get("ignore_missing_flags", [])
    }
    skip_invented = {
        (item["command"], item["flag"]) for item in expectations.get("ignore_invented_flags", [])
    }

    for flag in surface["global_flags"]:
        if flag.get("hidden"):
            continue
        names = documented_names(flag)
        if not any(any(n in doc.text for n in names) for doc in docs):
            findings.append(
                Finding(
                    "global-flag-undocumented",
                    "error",
                    "/".join(sorted(names)),
                    "valid on every command and no skill file names it",
                )
            )

    by_path = {c["path"]: c for c in surface["commands"] if c["path"]}
    for path, command in sorted(by_path.items()):
        if command.get("hidden") or path.split()[0] in BUILTIN_COMMANDS:
            continue

        # Forward: section scope.
        section_text = ""
        for doc in docs:
            for heading, lines in doc.sections:
                body = "\n".join(lines)
                if mentions(body, path):
                    section_text += "\n" + body
        for flag in command["flags"] or []:
            if flag.get("hidden"):
                continue
            names = documented_names(flag)
            if ("--" + flag["name"]) in {f for _, f in skip_missing if _ == path}:
                continue
            if (path, "--" + flag["name"]) in skip_missing:
                continue
            if not section_text:
                continue  # command itself is undocumented, already reported
            if not any(name in section_text for name in names):
                findings.append(
                    Finding(
                        "flag-undocumented",
                        "error",
                        f"cerebrium {path} {'/'.join(sorted(names))}",
                        f"the CLI accepts it ({flag['usage']}) and the skill section documenting "
                        f"this command does not name it",
                    )
                )

        # Reverse: line scope, tables and examples only.
        if command.get("unknown_flags_ok"):
            continue  # every --key value pair is passed through, none can be invented
        known = set(global_flags)
        for flag in command["flags"] or []:
            known |= documented_names(flag)
        for name in command.get("inherited") or []:
            known.add("--" + name)
        for doc in docs:
            for number, line in doc.literal_lines:
                if not mentions(line, path):
                    continue
                # A deeper command on the same line owns the flags, not this one.
                if any(other != path and other.startswith(path + " ") and mentions(line, other)
                       for other in by_path):
                    continue
                for candidate in sorted(flags_in(line) - known):
                    if (path, candidate) in skip_invented:
                        continue
                    findings.append(
                        Finding(
                            "flag-invented",
                            "error",
                            f"cerebrium {path} {candidate}",
                            "the skill documents this flag and the CLI does not accept it",
                            f"{doc.path}:{number}",
                        )
                    )
    return findings


def check_config(surface: dict, docs: list[Doc], expectations: dict) -> list[Finding]:
    findings = []
    skip = {
        (item["section"], item["key"]) for item in expectations.get("ignore_missing_config_keys", [])
    }
    config_docs = [d for d in docs if "[cerebrium." in d.text]

    for section in surface["config_sections"]:
        name = section["section"]
        region = ""
        for doc in config_docs:
            region += "\n" + section_region(doc, name)
        if not region.strip():
            findings.append(
                Finding(
                    "config-section-undocumented",
                    "error",
                    f"[{name}]",
                    "the CLI parses this table and no skill file documents it; keys: "
                    + ", ".join(section["keys"] or ["(free form)"]),
                )
            )
            continue
        if section.get("free_form"):
            continue
        for key in section["keys"]:
            if (name, key) in skip:
                continue
            # A subsection heading such as [cerebrium.dependencies.conda] counts
            # as documenting the `conda` key of [cerebrium.dependencies].
            if not re.search(r"(?<![\w])" + re.escape(key) + r"(?![\w])", region):
                findings.append(
                    Finding(
                        "config-key-undocumented",
                        "error",
                        f"[{name}] {key}",
                        "the CLI parses this key and the skill section for this table does not name it",
                    )
                )

    # Advisory only. The CLI uploads cerebrium.toml verbatim, so a key it does
    # not parse may still be a key the backend accepts.
    known_sections = {s["section"] for s in surface["config_sections"]}
    for doc in config_docs:
        for name in sorted({m.group(1) for m in re.finditer(r"\[(cerebrium\.[a-z0-9_.]+)\]", doc.text)}):
            if name in known_sections:
                continue
            if any(name.startswith(k + ".") for k in known_sections):
                continue
            findings.append(
                Finding(
                    "config-section-unparsed",
                    "advisory",
                    f"[{name}]",
                    "the skill documents this table and the CLI struct has no field for it; "
                    "legitimate if the backend parses it from the uploaded file",
                    doc.path,
                )
            )
    return findings


def section_region(doc: Doc, section: str) -> str:
    """The part of a doc that documents one cerebrium.toml table.

    Prefers the exact `[section]` marker, falls back to the first `[section.`
    prefix so `[cerebrium.dependencies]` finds the block that opens with
    `[cerebrium.dependencies.pip]`.
    """
    for marker in (f"[{section}]", f"[{section}."):
        for _, lines in doc.sections:
            body = "\n".join(lines)
            if marker in body:
                return body
    return ""


def check_prose(surface: dict, docs: list[Doc]) -> list[Finding]:
    """Two claims in the skill that a CLI fact contradicts.

    Each fires only while the fact holds, so neither is a hardcoded opinion
    about how the docs should read.
    """
    findings = []

    has_json_output = any(
        flag["name"] == "output" and "json" in flag.get("usage", "").lower()
        for command in surface["commands"]
        for flag in command["flags"] or []
    )
    if has_json_output:
        for doc in docs:
            for number, line in enumerate(doc.text.splitlines(), start=1):
                if "--no-color" in line and re.search(r"pars(e|ing)", line, re.IGNORECASE):
                    findings.append(
                        Finding(
                            "prose-stale",
                            "error",
                            "--no-color recommended for parsing",
                            "the CLI has --output json, so the colour flags are no longer the "
                            "way to get machine readable output",
                            f"{doc.path}:{number}",
                        )
                    )

    if surface.get("raw_toml_uploaded"):
        for doc in docs:
            for number, line in enumerate(doc.text.splitlines(), start=1):
                if re.search(r"ignored in silence|silently ignored", line, re.IGNORECASE):
                    findings.append(
                        Finding(
                            "prose-stale",
                            "error",
                            "unrecognised keys ignored in silence",
                            "the CLI uploads cerebrium.toml verbatim, so only the CLI ignores an "
                            "unrecognised key and the backend may not",
                            f"{doc.path}:{number}",
                        )
                    )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--surface", required=True, type=pathlib.Path)
    parser.add_argument("--skills", required=True, type=pathlib.Path)
    parser.add_argument(
        "--expectations",
        type=pathlib.Path,
        default=pathlib.Path(__file__).with_name("expectations.json"),
    )
    parser.add_argument("--ref", default="", help="CLI ref the surface came from, for the report")
    args = parser.parse_args()

    surface = json.loads(args.surface.read_text(encoding="utf-8"))
    expectations = (
        json.loads(args.expectations.read_text(encoding="utf-8"))
        if args.expectations.is_file()
        else {}
    )
    docs = load_docs(args.skills)
    if not docs:
        print(f"no markdown found under {args.skills}", file=sys.stderr)
        return 2

    skip_commands = set(expectations.get("ignore_missing_commands", []))
    findings = (
        check_commands(surface, docs, skip_commands)
        + check_flags(surface, docs, expectations)
        + check_config(surface, docs, expectations)
        + check_prose(surface, docs)
    )

    ref = args.ref or "(unspecified ref)"
    errors = [f for f in findings if f.severity == "error"]
    advisories = [f for f in findings if f.severity == "advisory"]

    print(f"cerebrium CLI {ref} against {args.skills}")
    print(f"{len(surface['commands']) - 1} commands, "
          f"{len(surface['config_sections'])} cerebrium.toml tables\n")

    for finding in errors:
        print(finding.line())
    if advisories:
        print("\nadvisory, not a failure:")
        for finding in advisories:
            print(finding.line())

    print()
    if errors:
        print(f"drift: {len(errors)} error(s), {len(advisories)} advisory")
        return 1
    print(f"no drift: 0 errors, {len(advisories)} advisory")
    return 0


if __name__ == "__main__":
    sys.exit(main())
