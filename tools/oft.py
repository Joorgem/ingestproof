"""OpenFastTrace 4.9.0 -- a Java 17 JAR, not a Python package.

Measured: `openfasttrace`, `open-fasttrace` and `oft-core` are all 404 on PyPI. And bare
`java` on this machine is 11.0.31 while $JAVA_HOME/bin/java is 17.0.19, so invoking the
JAR through PATH fails with an UnsupportedClassVersionError that says nothing about PATH.
Everything here goes through JAVA_HOME.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

OFT_VERSION = "4.9.0"
OFT_SHA256 = "d4ed42503ae066f51d55c3aad7c6e4b16acb80365921951ef5a065a4dc3d94f3"
OFT_URL = (
    f"https://github.com/itsallcode/openfasttrace/releases/download/"
    f"{OFT_VERSION}/openfasttrace-{OFT_VERSION}.jar"
)
DEFAULT_CACHE = Path("vendor") / "oft"


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
    jar = ensure_jar()
    report = root / "oft-report.txt"
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


if __name__ == "__main__":
    sys.exit(trace(Path(".")))
