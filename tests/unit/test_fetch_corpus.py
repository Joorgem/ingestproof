from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Any

import pytest

from tools.fetch_corpus import (
    PINNED,
    SOCKET_TIMEOUT,
    CorpusMismatch,
    cached_path,
    corpus_home,
    download,
    is_cached,
    main,
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


def test_without_the_override_the_cache_is_under_the_home_directory(
    tmp_path: Path, monkeypatch
) -> None:
    # The test above sets the override, so it can never reach the DEFAULT branch -- and the
    # default is the requirement. Measured: rewrite corpus_home's `Path.home()` as
    # `Path.cwd()`, which puts the cache inside whatever work tree the caller stands in, and
    # the test above still passes. This is the arm that goes red.
    monkeypatch.delenv("INGESTPROOF_CORPUS_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "elsewhere")

    assert corpus_home() == tmp_path / "elsewhere" / ".ingestproof-corpus"


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


def test_a_missing_file_is_refused_in_the_modules_own_error_type(tmp_path: Path) -> None:
    # `--verify-local /no/such/file` used to exit with a bare FileNotFoundError traceback
    # out of path.stat(). A missing file IS a disagreement with the pin, and the operator
    # who mistyped a path should read this module's sentence rather than a stack.
    with pytest.raises(CorpusMismatch, match="no such file"):
        verify(tmp_path / "absent.zip", PINNED)


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


def test_the_url_is_the_rfb_share_and_carries_the_month() -> None:
    assert PINNED.url().endswith("/2026-06/Estabelecimentos6.zip")
    assert PINNED.url().startswith(
        "https://arquivos.receitafederal.gov.br/public.php/webdav/"
    )


def _pin_for(payload: bytes) -> Any:
    return PINNED.replacing(size=len(payload), sha256=hashlib.sha256(payload).hexdigest())


# --- the CLI, whose seeding branch needs no network at all ------------------------------


def test_verify_local_seeds_a_cache_that_is_empty(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    payload = b"pretend corpus"
    source = tmp_path / "already-downloaded.zip"
    source.write_bytes(payload)
    monkeypatch.setenv("INGESTPROOF_CORPUS_HOME", str(tmp_path / "corpus"))
    monkeypatch.setattr("tools.fetch_corpus.PINNED", _pin_for(payload))

    assert main(["--verify-local", str(source)]) == 0

    seeded = tmp_path / "corpus" / "2026-06" / PINNED.filename
    assert seeded.read_bytes() == payload
    assert "cache seeded at" in capsys.readouterr().out


def test_verify_local_does_not_call_a_cache_of_other_bytes_seeded(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    # The message asserts "cache seeded at PATH". The old guard was `if not target.exists()`,
    # so a target holding some other month's bytes was left exactly where it was while the
    # operator was told the cache had been seeded. Whatever this command prints, the file it
    # names has to be the file the pin names.
    payload = b"pretend corpus"
    source = tmp_path / "already-downloaded.zip"
    source.write_bytes(payload)
    home = tmp_path / "corpus" / "2026-06"
    home.mkdir(parents=True)
    occupied = home / PINNED.filename
    occupied.write_bytes(b"a different month, same filename")
    monkeypatch.setenv("INGESTPROOF_CORPUS_HOME", str(tmp_path / "corpus"))
    monkeypatch.setattr("tools.fetch_corpus.PINNED", _pin_for(payload))

    assert main(["--verify-local", str(source)]) == 0

    assert "cache seeded at" in capsys.readouterr().out
    assert occupied.read_bytes() == payload


# --- the fetch itself, over a fake socket -----------------------------------------------
#
# The one live run proved the happy path once and then filled the cache, so the early exit
# in download() short-circuits every night that follows: the real network path will not run
# again while the pin holds. These are the only ongoing guard on the atomic-write rule.


class _FakeResponse:
    """Enough of an HTTPResponse for download(): a context manager that reads in blocks."""

    def __init__(self, payload: bytes, fail_after: int | None = None) -> None:
        self._buffer = io.BytesIO(payload)
        self._fail_after = fail_after
        self._reads = 0

    def read(self, size: int) -> bytes:
        self._reads += 1
        if self._fail_after is not None and self._reads > self._fail_after:
            raise OSError("connection reset by peer")
        return self._buffer.read(size)

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


def _fake_urlopen(
    payload: bytes, calls: list[dict[str, Any]], fail_after: int | None = None
) -> Any:
    def urlopen(request: Any, timeout: Any = None) -> _FakeResponse:
        calls.append({"url": request.full_url, "timeout": timeout})
        return _FakeResponse(payload, fail_after)

    return urlopen


def test_a_download_writes_the_pinned_bytes_and_leaves_no_part_file(
    tmp_path: Path, monkeypatch
) -> None:
    payload = b"pretend corpus"
    monkeypatch.setenv("INGESTPROOF_CORPUS_HOME", str(tmp_path / "corpus"))
    monkeypatch.setattr("tools.fetch_corpus.PINNED", _pin_for(payload))
    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(payload, []))

    target = download()

    assert target == cached_path()
    assert target.read_bytes() == payload
    assert list(target.parent.glob("*.part")) == []


def test_the_fetch_asks_for_the_pinned_url_and_passes_a_socket_timeout(
    tmp_path: Path, monkeypatch
) -> None:
    # Without a timeout, urlopen blocks forever on a stalled socket, and a nightly job that
    # cannot end is one that holds its runner until the platform's own limit fires.
    payload = b"pretend corpus"
    pinned = _pin_for(payload)
    calls: list[dict[str, Any]] = []
    monkeypatch.setenv("INGESTPROOF_CORPUS_HOME", str(tmp_path / "corpus"))
    monkeypatch.setattr("tools.fetch_corpus.PINNED", pinned)
    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(payload, calls))

    download()

    assert calls[0]["url"] == pinned.url()
    assert calls[0]["timeout"] == SOCKET_TIMEOUT
    assert SOCKET_TIMEOUT > 0


def test_a_download_whose_bytes_fail_the_pin_leaves_no_file_at_the_canonical_name(
    tmp_path: Path, monkeypatch
) -> None:
    payload = b"pretend corpus"
    monkeypatch.setenv("INGESTPROOF_CORPUS_HOME", str(tmp_path / "corpus"))
    monkeypatch.setattr(
        "tools.fetch_corpus.PINNED", PINNED.replacing(size=len(payload), sha256="0" * 64)
    )
    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(payload, []))

    with pytest.raises(CorpusMismatch, match="sha256"):
        download()

    # Never a wrong file at the right name: consumers do not all go through is_cached().
    # The inner-member check in the plan opens cached_path() bare, and later tasks will
    # copy that shape.
    assert not cached_path().exists()
    assert list(cached_path().parent.glob("*.part")) == []


def test_a_connection_that_drops_mid_stream_leaves_no_file_at_the_canonical_name(
    tmp_path: Path, monkeypatch
) -> None:
    payload = b"pretend corpus"
    monkeypatch.setenv("INGESTPROOF_CORPUS_HOME", str(tmp_path / "corpus"))
    monkeypatch.setattr("tools.fetch_corpus.PINNED", _pin_for(payload))
    # The first read returns the body; the second -- the read that would have ended the
    # stream -- raises instead, which is what a dropped connection looks like from here.
    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(payload, [], fail_after=1))

    with pytest.raises(OSError, match="connection reset"):
        download()

    assert not cached_path().exists()
    assert list(cached_path().parent.glob("*.part")) == []
