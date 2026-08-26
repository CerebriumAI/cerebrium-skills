#!/usr/bin/env python3
"""Prove `check_skill_sameness.py` actually fails, by planting differences and reading its
exit status.

Every case asserts the process exit code, not console output. A guard that prints a failure
and exits 0 reads as a pass to CI, so the exit code is the only thing worth asserting.

The remote copy is served over real HTTP from 127.0.0.1, so the fetch path, the 404 path and
the unreachable-host path are the ones under test rather than a stubbed stand-in.

    python3 tools/test_check_skill_sameness.py
"""

import functools
import http.server
import socket
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_skill_sameness as checker  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / "skills" / "cerebrium" / "SKILL.md"


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve(directory):
    handler = functools.partial(QuietHandler, directory=str(directory))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def closed_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def docs_copy(description, license_value, body):
    """The docs-site shape: its own name and metadata, everything else shared."""
    quoted = description.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    return (
        "---\n"
        "name: Cerebrium\n"
        f'description: "{quoted}"\n'
        f"license: {license_value}\n"
        "metadata:\n"
        "  mintlify-proj: cerebrium\n"
        '  version: "1.0"\n'
        "---\n" + body
    )


def run(url):
    return subprocess.run(
        [sys.executable, str(Path(__file__).parent / "check_skill_sameness.py"),
         "--local-path", str(LOCAL), "--remote-url", url],
        cwd=ROOT, capture_output=True, text=True,
    ).returncode


def main():
    frontmatter, body = checker.split_frontmatter(LOCAL.read_text(encoding="utf-8"), str(LOCAL))
    description = checker.field(frontmatter, "description", str(LOCAL))
    license_value = checker.field(frontmatter, "license", str(LOCAL))
    same = docs_copy(description, license_value, body)

    with tempfile.TemporaryDirectory() as directory:
        served = Path(directory) / "skill.md"
        server = serve(directory)
        url = f"http://127.0.0.1:{server.server_address[1]}/skill.md"

        cases = [
            ("a copy differing only in name and metadata", same, 0),
            ("one character changed in the body", same.replace("serverless", "serverles", 1), 1),
            ("a whole heading removed from the body", same.replace("## Rules for agents", ""), 1),
            ("a line appended to the body", same + "\nAn extra line.\n", 1),
            ("a different description", docs_copy("Something else.", license_value, body), 1),
            ("a different license", docs_copy(description, "Apache-2.0", body), 1),
            ("no frontmatter fence at all", body, 1),
            ("frontmatter that is never closed", "---\nname: Cerebrium\n" + body, 1),
            ("frontmatter with no description", "---\nname: x\nlicense: MIT\n---\n" + body, 1),
        ]

        failures = []
        for label, content, expected in cases:
            served.write_text(content, encoding="utf-8")
            actual = run(url)
            status = "ok" if actual == expected else "FAILED"
            print(f"{status}: {label} -> exit {actual}, expected {expected}")
            if actual != expected:
                failures.append(label)

        served.unlink()
        for label, target, expected in [
            ("the remote file is missing (404)", url, 1),
            ("the remote host refuses the connection", f"http://127.0.0.1:{closed_port()}/skill.md", 1),
        ]:
            actual = run(target)
            status = "ok" if actual == expected else "FAILED"
            print(f"{status}: {label} -> exit {actual}, expected {expected}")
            if actual != expected:
                failures.append(label)

        server.shutdown()

    if failures:
        print(f"\n{len(failures)} case(s) behaved wrongly: {', '.join(failures)}")
        return 1
    print(f"\nall {len(cases) + 2} cases behaved as specified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
