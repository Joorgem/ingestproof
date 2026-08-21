"""ASM-6: how the big corpus arrives, and why it is pinned twice over.

It is in no repository -- 14 GB, git-ignored. And TWO different files carry the name
`Estabelecimentos6.zip`: 2026-06 at 366,882,667 bytes and 2026-07 at 368,109,911. So the
month and the SHA-256 are both part of the pin, and no acceptance criterion may cite "the
Estabelecimentos6" without them.

It caches OUTSIDE the work tree, runs in the nightly ring, and never on the VPS: the KVM
has 4 GB and the flagship already measured Spark dying at about 1.8 GB free.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import urllib.request
from base64 import b64encode
from collections.abc import Callable
from dataclasses import dataclass, replace
from os import environ
from pathlib import Path

WEBDAV_BASE = "https://arquivos.receitafederal.gov.br/public.php/webdav"
# The public Nextcloud share id for the RFB open data. It is the share's address, not a
# credential: it is sent as the HTTP basic user with an empty password, exactly as the
# published share link does.
SHARE_TOKEN = "YggdBLfdninEJX9"  # gitleaks:allow
CHUNK = 1 << 20
# PER SOCKET OPERATION, not per download -- the whole 366 MB took 8m39s on a GitHub runner,
# but no single 1 MB read comes anywhere near this. `urlopen` without it defaults to None,
# and a stalled socket then holds the runner until the platform's own limit (360 minutes on
# GitHub Actions) instead of failing the night in two minutes.
SOCKET_TIMEOUT = 120


class CorpusMismatch(RuntimeError):
    """The file on disk is not the file the pin names."""


@dataclass(frozen=True)
class CorpusFile:
    month: str
    filename: str
    size: int
    sha256: str
    inner_member: str
    inner_size: int

    def url(self) -> str:
        return f"{WEBDAV_BASE}/{self.month}/{self.filename}"

    def replacing(self, **changes: object) -> CorpusFile:
        return replace(self, **changes)  # type: ignore[arg-type]


PINNED = CorpusFile(
    month="2026-06",
    filename="Estabelecimentos6.zip",
    size=366_882_667,
    sha256="76dbe5d9fc9f92df1f8626a924f31c2c4a22819419ee33e5fae9bb7a30d8bb9e",
    inner_member="K3241.K03200Y6.D60613.ESTABELE",
    inner_size=1_153_737_686,
)


def corpus_home() -> Path:
    # The DEFAULT branch is the requirement (ASM-10), not the override: `Path.home()` puts
    # the cache outside every work tree. Rewriting it as `Path.cwd()` resolves to
    # `<repo>/.ingestproof-corpus` -- a 366 MB file inside the repository -- so the default
    # carries its own test rather than being reached only when the env var is unset.
    return Path(
        environ.get("INGESTPROOF_CORPUS_HOME") or (Path.home() / ".ingestproof-corpus")
    )


# THE PIN ARRIVES AS None, never as `= PINNED`, in all four functions below. A default is
# bound at `def` time, so a function whose default IS the module global can never see that
# global replaced: a caller that patches `tools.fetch_corpus.PINNED` and then calls
# `is_cached()` keeps measuring the original pin. Measured with `= PINNED` in place:
# test_a_present_and_correct_file_is_cached fails, while its corrupt-file neighbour passes
# anyway -- the real pin refuses a 9-byte file on size, so the same defect shows up once as
# a visible red and once as a green that proves nothing. One rule, no exception to
# remember: `CorpusFile | None = None`, resolved with `is None` in the body. Not `or`:
# truthiness would depend on CorpusFile never growing a `__bool__` or a `__len__`, and that
# is the kind of invariant that stops being true without anything going red.
def cached_path(pinned: CorpusFile | None = None) -> Path:
    if pinned is None:
        pinned = PINNED
    return corpus_home() / pinned.month / pinned.filename


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(path: Path, pinned: CorpusFile | None = None) -> None:
    if pinned is None:
        pinned = PINNED
    if not path.is_file():
        # A path that is not there disagrees with the pin as surely as wrong bytes do, and
        # --verify-local is typed by hand: a mistyped path must read as this module's own
        # sentence, not as a FileNotFoundError raised out of stat() below.
        raise CorpusMismatch(
            f"{path}: no such file -- the pin names {pinned.filename} for {pinned.month}"
        )
    actual_size = path.stat().st_size
    if actual_size != pinned.size:
        raise CorpusMismatch(
            f"{path}: size is {actual_size}, the pin says {pinned.size} "
            f"(month {pinned.month} -- the other month's file is a different size)"
        )
    actual = sha256_of(path)
    if actual != pinned.sha256:
        raise CorpusMismatch(f"{path}: sha256 is {actual}, the pin says {pinned.sha256}")


def is_cached(pinned: CorpusFile | None = None) -> bool:
    if pinned is None:
        pinned = PINNED
    # No separate exists() branch any more: a missing file is already a CorpusMismatch, so
    # one except arm answers absent, wrong-sized and wrong-hashed with the same rule.
    try:
        verify(cached_path(pinned), pinned)
    except CorpusMismatch:
        return False
    return True


def _install_atomically(
    target: Path, pinned: CorpusFile, fill: Callable[[Path], None]
) -> Path:
    """Fill a `.part` sibling, verify THAT, and only then move it into place.

    Never straight into `cached_path()`. A dropped connection, a cancelled runner or a failed
    verify would otherwise leave a corrupt file sitting at the canonical name, and consumers
    do not all go through `is_cached()` -- the inner-member check opens `cached_path()` bare,
    and later tasks will copy that shape. The failure mode has to be "no file", never "the
    wrong file at the right name".

    A SIBLING, not the system temp directory: `Path.replace` is atomic only within a single
    filesystem, and the cache home is easily on a different volume from temp.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + ".part")
    try:
        fill(part)
        verify(part, pinned)
        part.replace(target)
    finally:
        # Every exit, KeyboardInterrupt included. After a successful replace there is
        # nothing left at this name, and missing_ok covers a fill that never got started.
        part.unlink(missing_ok=True)
    return target


def download(pinned: CorpusFile | None = None) -> Path:
    if pinned is None:
        pinned = PINNED
    target = cached_path(pinned)
    if is_cached(pinned):
        return target
    credential = b64encode(f"{SHARE_TOKEN}:".encode()).decode()
    request = urllib.request.Request(  # noqa: S310 -- pinned https URL
        pinned.url(), headers={"Authorization": f"Basic {credential}"}
    )

    def fetch(part: Path) -> None:
        with (
            urllib.request.urlopen(  # noqa: S310 -- pinned https URL
                request, timeout=SOCKET_TIMEOUT
            ) as response,
            part.open("wb") as handle,
        ):
            for block in iter(lambda: response.read(CHUNK), b""):
                handle.write(block)

    return _install_atomically(target, pinned, fetch)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify-local",
        metavar="PATH",
        help="check an existing copy against the pin and seed the cache from it, "
             "instead of re-downloading 366 MB",
    )
    args = parser.parse_args(argv)

    if args.verify_local:
        source = Path(args.verify_local)
        verify(source, PINNED)
        target = cached_path()

        def copy_in(part: Path) -> None:
            # Streamed, not `target.write_bytes(source.read_bytes())`: that held all 366 MB
            # resident at once, in a module whose docstring cites a 4 GB machine.
            shutil.copyfile(source, part)

        # `if not target.exists()` used to guard this, and that is a weaker property than
        # the line below claims: a target holding some other month's bytes was left exactly
        # where it was while the operator read that the cache had been seeded. is_cached()
        # asks the same question the message answers.
        if not is_cached():
            _install_atomically(target, PINNED, copy_in)
        print(f"{source} matches the pin; cache seeded at {target}")
        return 0

    path = download()
    print(f"{path}  {path.stat().st_size} bytes  sha256 ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
