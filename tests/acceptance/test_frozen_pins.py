"""The pins that decide what every other measurement is about, in a file a turn cannot edit.

Each assertion here is a DUPLICATE. The originals are in `tests/unit/test_manifest.py` and
`tests/unit/test_fetch_corpus.py`, and both of those are inside `tests/unit/**`, which is
exactly the tree a turn may write. Until this file existed, a turn could delete the only
mechanical guard on the DuckDB oracle version, the published version, or the corpus
identity, and CI would stay green -- because the thing that had gone missing was the check
itself, and nothing counts checks.

That is not a hypothetical about a hostile agent. It is what a turn does when a test fails
for a reason it cannot fix and the queue is pushing it forward.

Duplication is the whole mechanism, so do not "consolidate" this with the unit tests. Two
copies in two freeze regimes is the point; one copy in the writable one is the defect.

- **ASM-8** -- duckdb 1.5.5 is the oracle of VALUE for the fidelity differential. The range
  lives in `pyproject.toml`, the exact pin lives in `uv.lock`, and an assertion is what
  makes a pin real. A silent minor bump changes the oracle.
- **ASM-6** -- two different `Estabelecimentos6.zip` exist locally, 2026-06 at 366,882,667
  bytes and 2026-07 at 368,109,911. Citing the corpus without a month names two corpora,
  and every record-count measurement in `docs/measurements.md` is about the first.
- The published version is what claims the name on PyPI, and `req~ac-10~1` measures the
  install of that exact string.
"""
from __future__ import annotations

import duckdb

import ingestproof
from tools.fetch_corpus import PINNED


def test_the_duckdb_oracle_is_pinned_at_the_measured_version() -> None:
    assert duckdb.__version__ == "1.5.5"


def test_the_published_version_is_the_one_that_claims_the_name() -> None:
    assert ingestproof.__version__ == "0.0.1"


def test_the_corpus_pin_names_a_month_a_size_and_a_hash() -> None:
    assert PINNED.month == "2026-06"
    assert PINNED.filename == "Estabelecimentos6.zip"
    assert PINNED.size == 366_882_667
    assert PINNED.sha256 == (
        "76dbe5d9fc9f92df1f8626a924f31c2c4a22819419ee33e5fae9bb7a30d8bb9e"
    )


def test_the_corpus_pin_names_its_single_inner_member() -> None:
    assert PINNED.inner_member == "K3241.K03200Y6.D60613.ESTABELE"
    assert PINNED.inner_size == 1_153_737_686
