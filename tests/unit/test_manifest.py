"""The commit-1 manifest (spec section 7.12), asserted against the interpreter that is
actually running. Every value here was a decision someone would otherwise have to invent.
"""
from __future__ import annotations

import os
import sys

import duckdb
import pytest
from hypothesis import settings

import ingestproof


def test_the_interpreter_is_312_and_not_the_314_loose_on_this_machine() -> None:
    assert sys.version_info[:2] == (3, 12)


def test_the_duckdb_oracle_is_the_pinned_version() -> None:
    # ASM-8: the range lives in pyproject, the pin lives in uv.lock, and this is the
    # assertion that makes the pin real. DuckDB is the oracle of VALUE for the fidelity
    # differential; a silent minor bump changes the oracle.
    assert duckdb.__version__ == "1.5.5"


def test_the_version_is_the_one_that_claims_the_name() -> None:
    assert ingestproof.__version__ == "0.0.1"


def test_the_hypothesis_profile_is_derandomised_with_no_database() -> None:
    assert settings.default.derandomize is True
    assert settings.default.database is None


@pytest.mark.skipif(os.environ.get("CI") != "true", reason="the manifest env is CI's job")
def test_ci_exports_the_deterministic_environment() -> None:
    assert os.environ["PYTHONHASHSEED"] == "0"
    assert os.environ["TZ"] == "UTC"
    assert os.environ["LC_ALL"] == "C.UTF-8"
