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
import sys
import urllib.request
from base64 import b64encode
from dataclasses import dataclass, replace
from os import environ
from pathlib import Path

WEBDAV_BASE = "https://arquivos.receitafederal.gov.br/public.php/webdav"
# The public Nextcloud share id for the RFB open data. It is the share's address, not a
# credential: it is sent as the HTTP basic user with an empty password, exactly as the
# published share link does.
SHARE_TOKEN = "YggdBLfdninEJX9"  # gitleaks:allow
CHUNK = 1 << 20


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
# remember: `CorpusFile | None = None`, resolved in the body.
def cached_path(pinned: CorpusFile | None = None) -> Path:
    pinned = pinned or PINNED
    return corpus_home() / pinned.month / pinned.filename


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(path: Path, pinned: CorpusFile | None = None) -> None:
    pinned = pinned or PINNED
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
    pinned = pinned or PINNED
    path = cached_path(pinned)
    if not path.exists():
        return False
    try:
        verify(path, pinned)
    except CorpusMismatch:
        return False
    return True


def download(pinned: CorpusFile | None = None) -> Path:
    pinned = pinned or PINNED
    target = cached_path(pinned)
    if is_cached(pinned):
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    credential = b64encode(f"{SHARE_TOKEN}:".encode()).decode()
    request = urllib.request.Request(  # noqa: S310 -- pinned https URL
        pinned.url(), headers={"Authorization": f"Basic {credential}"}
    )
    with urllib.request.urlopen(request) as response, target.open("wb") as handle:  # noqa: S310
        for block in iter(lambda: response.read(CHUNK), b""):
            handle.write(block)
    verify(target, pinned)
    return target


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
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(source.read_bytes())
        print(f"{source} matches the pin; cache seeded at {target}")
        return 0

    path = download()
    print(f"{path}  {path.stat().st_size} bytes  sha256 ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
