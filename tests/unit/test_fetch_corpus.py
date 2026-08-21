from __future__ import annotations

from pathlib import Path

import pytest

from tools.fetch_corpus import (
    PINNED,
    CorpusMismatch,
    corpus_home,
    is_cached,
    sha256_of,
    verify,
)


def test_the_pin_carries_a_month_because_two_files_share_the_name() -> None:
    # Measured: 2026-06 is 366,882,667 bytes and 2026-07 is 368,109,911. Citing
    # "Estabelecimentos6" without a month names two different corpora.
    assert PINNED.month == "2026-06"
    assert PINNED.filename == "Estabelecimentos6.zip"
    assert PINNED.size == 366_882_667
    assert PINNED.sha256 == (
        "76dbe5d9fc9f92df1f8626a924f31c2c4a22819419ee33e5fae9bb7a30d8bb9e"
    )


def test_the_pin_also_names_the_single_inner_member() -> None:
    assert PINNED.inner_member == "K3241.K03200Y6.D60613.ESTABELE"
    assert PINNED.inner_size == 1_153_737_686


def test_the_cache_is_outside_every_work_tree(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("INGESTPROOF_CORPUS_HOME", str(tmp_path / "corpus"))

    assert corpus_home() == tmp_path / "corpus"


def test_a_file_with_the_right_bytes_verifies(tmp_path: Path) -> None:
    payload = b"pretend corpus"
    path = tmp_path / "small.zip"
    path.write_bytes(payload)
    pinned = PINNED.replacing(size=len(payload), sha256=sha256_of(path))

    verify(path, pinned)  # must not raise


def test_the_wrong_size_is_refused_before_the_hash_is_computed(tmp_path: Path) -> None:
    path = tmp_path / "small.zip"
    path.write_bytes(b"short")
    pinned = PINNED.replacing(size=999_999, sha256="0" * 64)

    with pytest.raises(CorpusMismatch, match="size"):
        verify(path, pinned)


def test_the_wrong_hash_is_refused(tmp_path: Path) -> None:
    payload = b"pretend corpus"
    path = tmp_path / "small.zip"
    path.write_bytes(payload)
    pinned = PINNED.replacing(size=len(payload), sha256="0" * 64)

    with pytest.raises(CorpusMismatch, match="sha256"):
        verify(path, pinned)


def test_a_missing_file_is_not_cached(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("INGESTPROOF_CORPUS_HOME", str(tmp_path / "empty"))

    assert is_cached() is False


def test_a_present_and_correct_file_is_cached(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "corpus" / "2026-06"
    home.mkdir(parents=True)
    payload = b"pretend corpus"
    path = home / PINNED.filename
    path.write_bytes(payload)
    monkeypatch.setenv("INGESTPROOF_CORPUS_HOME", str(tmp_path / "corpus"))
    monkeypatch.setattr(
        "tools.fetch_corpus.PINNED",
        PINNED.replacing(size=len(payload), sha256=sha256_of(path)),
    )

    assert is_cached() is True


def test_a_present_but_corrupt_file_is_not_cached(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "corpus" / "2026-06"
    home.mkdir(parents=True)
    (home / PINNED.filename).write_bytes(b"truncated")
    monkeypatch.setenv("INGESTPROOF_CORPUS_HOME", str(tmp_path / "corpus"))

    assert is_cached() is False


def test_the_url_is_the_rfb_share_and_carries_the_month(tmp_path: Path) -> None:
    assert PINNED.url().endswith("/2026-06/Estabelecimentos6.zip")
    assert PINNED.url().startswith(
        "https://arquivos.receitafederal.gov.br/public.php/webdav/"
    )
