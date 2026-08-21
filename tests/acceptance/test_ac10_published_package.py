"""req~ac-10~1 -- `pip install ingestproof` works from PyPI, with py.typed and attestations.

Marked `external`: it needs the network and a published artefact, so the inner ring
deselects it. Run it by hand after a release:

    uv run pytest tests/acceptance/test_ac10_published_package.py -m external -vv
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

VERSION = "0.0.1"
PYPI_JSON = f"https://pypi.org/pypi/ingestproof/{VERSION}/json"
PYPI_SIMPLE = "https://pypi.org/simple/ingestproof/"
WHEEL = f"ingestproof-{VERSION}-py3-none-any.whl"

pytestmark = pytest.mark.external


def _pypi_metadata() -> dict[str, object]:
    with urllib.request.urlopen(PYPI_JSON) as response:  # noqa: S310 -- pinned https URL
        return json.loads(response.read())


def _fetch_json(url: str, accept: str = "application/json") -> dict[str, object]:
    request = urllib.request.Request(url, headers={"Accept": accept})  # noqa: S310
    with urllib.request.urlopen(request) as response:  # noqa: S310 -- pinned https URL
        return json.loads(response.read())


def test_the_version_is_published() -> None:
    assert _pypi_metadata()["info"]["version"] == VERSION  # type: ignore[index]


def test_both_a_wheel_and_an_sdist_are_published() -> None:
    urls = _pypi_metadata()["urls"]
    kinds = {entry["packagetype"] for entry in urls}  # type: ignore[union-attr,index]

    assert kinds == {"bdist_wheel", "sdist"}


def test_the_wheel_carries_a_provenance_attestation() -> None:
    # There is no API token in this project by design; OIDC is the whole credential, and
    # the attestation is the observable proof that the OIDC path is what published this.
    # The URL comes from the PEP 740 simple API; /pypi/<name>/<version>/json has no
    # provenance key at all.
    files = _fetch_json(PYPI_SIMPLE, "application/vnd.pypi.simple.v1+json")["files"]
    wheels = [f for f in files if f["filename"] == WHEEL]  # type: ignore[union-attr,index]

    assert wheels, f"{WHEEL} not in {PYPI_SIMPLE}"

    provenance = wheels[0].get("provenance")

    assert provenance, "no provenance URL: attestations did not attach"

    publisher = _fetch_json(provenance)["attestation_bundles"][0]["publisher"]  # type: ignore[index]

    assert publisher["repository"] == "Joorgem/ingestproof"
    assert publisher["workflow"] == "release.yml"
    assert publisher["environment"] is None  # PyPI records "(Any)" as null.


def test_it_installs_into_a_clean_interpreter_and_ships_py_typed(tmp_path: Path) -> None:
    venv = tmp_path / "v"
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    python = venv / ("Scripts" if sys.platform == "win32" else "bin") / (
        "python.exe" if sys.platform == "win32" else "python"
    )
    install = subprocess.run(
        [str(python), "-m", "pip", "install", "--no-cache-dir", f"ingestproof=={VERSION}"],
        capture_output=True, text=True,
    )

    assert install.returncode == 0, install.stderr

    probe = subprocess.run(
        [str(python), "-c",
         "import ingestproof, pathlib, sys;"
         "print(ingestproof.__version__);"
         "print((pathlib.Path(ingestproof.__file__).parent / 'py.typed').exists())"],
        capture_output=True, text=True,
    )

    assert probe.returncode == 0, probe.stderr

    version, has_marker = probe.stdout.split()

    assert version == VERSION
    assert has_marker == "True"
