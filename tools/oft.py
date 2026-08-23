"""OpenFastTrace 4.9.0 -- a Java 17 JAR, not a Python package.

Measured: `openfasttrace`, `open-fasttrace` and `oft-core` are all 404 on PyPI. And bare
`java` on this machine is 11.0.31 while $JAVA_HOME/bin/java is 17.0.19, so invoking the
JAR through PATH fails with an UnsupportedClassVersionError that says nothing about PATH.
Everything here goes through JAVA_HOME.
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

from tools.spec_parse import parse_dir

OFT_VERSION = "4.9.0"
OFT_SHA256 = "d4ed42503ae066f51d55c3aad7c6e4b16acb80365921951ef5a065a4dc3d94f3"
OFT_URL = (
    f"https://github.com/itsallcode/openfasttrace/releases/download/"
    f"{OFT_VERSION}/openfasttrace-{OFT_VERSION}.jar"
)
DEFAULT_CACHE = Path("vendor") / "oft"
REPORT_NAME = "oft-report.txt"
# The count check traces this ONE directory, and nothing else. Everything the fix rests on
# is in `check_counts` and `trace_spec_only` below.
SPEC_DIR = ".spec"
COUNT_REPORT_NAME = "oft-spec-count.txt"
# Derived from a real report, not guessed. Every ITEM line opens `not ok [`; the one
# summary line opens `not ok - 22 total, 22 direct, 0 transitive defects`. Anchored at
# line start and left unanchored at the end, so the CRLF the JAR writes on Windows and
# an `ok - ` summary once coverage exists both still match.
SUMMARY = re.compile(r"^(?:not )?ok - (?P<total>\d+) total\b", re.MULTILINE)


def java_executable() -> Path:
    home = os.environ.get("JAVA_HOME")
    if not home:
        raise RuntimeError(
            "JAVA_HOME is unset. OFT 4.9.0 needs the JDK 17 it points at; bare `java` on "
            "this machine resolves to 11 and fails with a class-version error."
        )
    exe = Path(home) / "bin" / ("java.exe" if os.name == "nt" else "java")
    if not exe.exists():
        raise RuntimeError(f"JAVA_HOME points at {home}, but {exe} does not exist")
    return exe


def assert_java_17() -> None:
    out = subprocess.run(
        (str(java_executable()), "-version"), capture_output=True, text=True, check=True
    )
    banner = out.stderr or out.stdout
    if 'version "17' not in banner:
        raise RuntimeError(f"OFT 4.9.0 needs Java 17; JAVA_HOME gives:\n{banner.strip()}")


def ensure_jar(cache: Path | None = None) -> Path:
    target = (cache or DEFAULT_CACHE) / f"openfasttrace-{OFT_VERSION}.jar"
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == OFT_SHA256:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(OFT_URL) as response:  # noqa: S310 -- pinned https release URL
        payload = response.read()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != OFT_SHA256:
        raise RuntimeError(f"OFT jar sha256 is {digest}, expected {OFT_SHA256}")
    target.write_bytes(payload)
    return target


def trace(root: Path) -> int:
    assert_java_17()
    # Both paths absolute. The subprocess runs with cwd=root, so a path built from a
    # relative `root` is resolved twice -- once here against the process cwd and again
    # inside the child -- and the jar lands in one place while the child looks in
    # another. It coincides only while root is ".". Same shape as the `--root` bug the
    # freeze checker had: a parameter that lies everywhere except at its default.
    base = root.resolve()
    jar = ensure_jar(base / DEFAULT_CACHE)
    report = base / REPORT_NAME
    result = subprocess.run(
        (str(java_executable()), "-jar", str(jar), "trace",
         "-o", "plain", "-f", str(report), ".spec", "src", "tests", "loop", "tools"),
        cwd=root,
    )
    if report.exists():
        # A criterion contains U+222A and the Windows console default is cp1252, where a
        # bare print() of the report raises UnicodeEncodeError. CI's C.UTF-8 never hits
        # it; the laptop always does. Degrade the character, never the run.
        encoding = sys.stdout.encoding or "utf-8"
        text = report.read_text(encoding="utf-8")
        print(text.encode(encoding, errors="replace").decode(encoding, errors="replace"))
    return result.returncode


def trace_spec_only(root: Path) -> Path:
    """Write a plain report of `.spec` ALONE, and return where it went.

    Separate from `trace` because the two want different inputs. `trace` wants the whole
    tree, because coverage is the thing it reports. `check_counts` wants only the
    directory both counters read, because anything else changes the number it compares.

    The JAR's exit code is discarded on purpose: `.spec` traced without a source tree has
    every criterion uncovered, so this trace ALWAYS exits non-zero and the code says
    nothing about whether the count is readable. `check_counts` reads the report instead.
    """
    assert_java_17()
    base = root.resolve()
    jar = ensure_jar(base / DEFAULT_CACHE)
    report = base / COUNT_REPORT_NAME
    subprocess.run(
        (str(java_executable()), "-jar", str(jar), "trace",
         "-o", "plain", "-f", str(report), SPEC_DIR),
        cwd=root,
    )
    return report


def report_item_count(report_text: str) -> int | None:
    """The `N total` from OFT's plain-report summary line, or None if there is no summary.

    None rather than 0, deliberately: a regex that silently stopped matching would make
    check_counts permanently green, which is the exact failure the check exists to catch.
    """
    match = SUMMARY.search(report_text)
    return int(match.group("total")) if match else None


def check_counts(root: Path) -> int:
    """Fail when the JAR and tools/spec_parse disagree on how many items `.spec` has.

    tools/spec_parse is deliberately NARROWER than OFT: it requires backticks, pins the
    type to `req`, requires a lowercase name and refuses a second `Needs:` line. So an
    item written in any other OFT-legal form is visible to the JAR and invisible to the
    inner ring -- never hashed, never Needs-checked. The two counts agreeing is the only
    thing watching that gap.

    IT READS THE SPEC-ONLY REPORT, NOT `oft-report.txt`, and that is the whole of it.
    OFT's `N total` counts every IMPORTED COVERAGE TAG as a specobject alongside the
    criteria. Measured with JAR 4.9.0 against the shipped `.spec/`, with the tags written
    as `impl->req~ac-01~1` and `utest->req~ac-01~1` inside square brackets -- unbracketed
    here because a well-formed tag in a docstring IS a tag, and writing one in this table
    would have added itself to the numbers it reports:

        0 tags                                  22 total, 22 direct
        1 tag  (impl)                           23 total, 22 direct
        2 tags (impl and utest)                 24 total, 21 direct
        the same 2 tags, tracing `.spec` alone  22 total, 22 direct

    So against the full trace this check is unsatisfiable from the first coverage tag
    onwards, and the gap widens with every tag after it. It was green only while coverage
    was zero -- green for a reason other than the one it claims. Against `.spec` alone the
    two counters read the same directory and nothing else, which is the comparison the
    docstring above always described.
    """
    report = root / COUNT_REPORT_NAME
    if not report.exists():
        print(
            f"{COUNT_REPORT_NAME} is missing; trace_spec_only has to run first",
            file=sys.stderr,
        )
        return 1
    counted = report_item_count(report.read_text(encoding="utf-8"))
    if counted is None:
        print(
            f"no summary line in {COUNT_REPORT_NAME}; the counts cannot be compared",
            file=sys.stderr,
        )
        return 1
    if counted == 0:
        # Same principle as report_item_count returning None rather than 0, one layer up.
        # `ok - 0 total` is what the JAR writes for a tree with no `.spec`, and
        # tools/spec_parse returns [] for that same tree -- so without this the check
        # passed by reading nothing twice and said "agree on 0 specification items".
        # This step BLOCKS, and trace_spec_only discards the JAR's exit code on purpose,
        # so a trace that read nothing has nowhere else to show up.
        print(
            f"{COUNT_REPORT_NAME} reports 0 items in {SPEC_DIR}. A trace that read "
            f"nothing agrees with a parser that read nothing; that is not agreement.",
            file=sys.stderr,
        )
        return 1
    parsed = len(parse_dir(root))
    if counted != parsed:
        print(
            f"OpenFastTrace sees {counted} specification items in {SPEC_DIR} and "
            f"tools/spec_parse sees {parsed}. They read the same directory, so a criterion "
            f"is written in a form only one of them accepts.",
            file=sys.stderr,
        )
        return 1
    print(f"OpenFastTrace and tools/spec_parse agree on {parsed} specification items")
    return 0


if __name__ == "__main__":
    # `python -m tools.oft` stays the trace, unchanged.
    if sys.argv[1:2] == ["check-counts"]:
        # The trace and the comparison are one command, because a stale report is a
        # comparison against a `.spec` that no longer exists.
        trace_spec_only(Path("."))
        sys.exit(check_counts(Path(".")))
    sys.exit(trace(Path(".")))
