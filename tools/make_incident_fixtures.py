"""The three CSV incidents, written as BYTES.

Every fixture here is a literal `bytes` object and is written in binary mode, because the
content is the product: an editor that normalises a line ending, or a `.gitattributes` that
lets git do it, silently rewrites the RFC 4180 section 2.6 case this library exists to
catch. `tests/fixtures/**` carries `-text` for the same reason.

The three are the flagship's real layer-B incidents (docs/measurements.md section 6), plus
a clean negative control -- without the control, "it flagged something" proves nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

FIXTURES: dict[str, bytes] = {
    # [A] A record with a newline INSIDE a quoted field. Read with multiLine=false the
    # reader emits 3 rows for 2 records; the row count closes around the damage.
    "multiline.csv": b'id,note\n1,"line A\nline B"\n2,ok\n',
    # [B] A doubled quote and a delimiter inside a quoted field. With the escape character
    # absent the delimiter is swallowed and the field ends up as '"say ""hi""'.
    "escape.csv": b'id,name\n1,"say ""hi"", bye"\n',
    # [C] Two columns declared, a row carrying three. PERMISSIVE drops the extra in
    # silence while FAILFAST on the same file raises -- the parser knew and discarded it.
    "extra_field.csv": b"id,name\n1,ok\n2,fine\n3,4,EXTRA\n",
    # The negative control. Same shape, no damage. A detector without one is a detector
    # that has never been shown to be able to stay quiet.
    "clean.csv": b'id,name\n1,ok\n2,"quoted, but well formed"\n3,fine\n',
}


def write_all(root: Path) -> list[Path]:
    target = root / "tests" / "fixtures" / "incidents"
    target.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, payload in FIXTURES.items():
        path = target / name
        path.write_bytes(payload)
        written.append(path)
    return written


if __name__ == "__main__":
    for path in write_all(Path(".")):
        print(f"{path.as_posix()}  {path.stat().st_size} bytes")
    sys.exit(0)
