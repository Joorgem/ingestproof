"""The three CSV incidents, written as BYTES.

Every fixture here is a literal `bytes` object and is written in binary mode, because the
content is the product: an editor that normalises a line ending, or a `.gitattributes` that
lets git do it, silently rewrites the RFC 4180 section 2.6 case this library exists to
catch. `tests/fixtures/**` carries `-text` for the same reason.

The three are the flagship's real layer-B incidents (docs/measurements.md section 6), plus
a clean negative control -- without the control, "it flagged something" proves nothing.

Each incident carries a PREDICTION about what the production reader does to these bytes.
Nothing in this repository has measured any of them; the differential task settles each
one, and until it does they are expectations and not results. What HAS been measured about
these bytes is a correct parser's reading of them: docs/duckdb-baseline-output.txt for the
counts, and tests/unit/test_duckdb_baseline.py for the parsed values.
"""
from __future__ import annotations

import sys
from pathlib import Path

# The fixture directory, defined ONCE and anchored on this file rather than on the current
# directory. The generator writes here, the DuckDB baseline reads here, and the tests
# assert against here -- from any working directory, because pytest does not chdir.
ROOT = Path(__file__).resolve().parents[1]
INCIDENTS_RELATIVE = Path("tests") / "fixtures" / "incidents"
INCIDENTS = ROOT / INCIDENTS_RELATIVE

FIXTURES: dict[str, bytes] = {
    # [A] A record with a newline INSIDE a quoted field.
    # PREDICTION, not measured -- for the differential task: read with multiLine=false the
    # reader emits 3 rows for 2 records; the row count closes around the damage.
    "multiline.csv": b'id,note\n1,"line A\nline B"\n2,ok\n',
    # [B] A doubled quote and a delimiter inside a quoted field.
    # PREDICTION, not measured -- for the differential task: with the escape character
    # absent the delimiter is swallowed and the field ends up as '"say ""hi""'.
    "escape.csv": b'id,name\n1,"say ""hi"", bye"\n',
    # [C] Two columns declared, a row carrying three.
    # PREDICTION, not measured -- for the differential task: PERMISSIVE drops the extra in
    # silence while FAILFAST on the same file raises -- the parser knew and discarded it.
    "extra_field.csv": b"id,name\n1,ok\n2,fine\n3,4,EXTRA\n",
    # The negative control. Same shape, no damage. A detector without one is a detector
    # that has never been shown to be able to stay quiet.
    "clean.csv": b'id,name\n1,ok\n2,"quoted, but well formed"\n3,fine\n',
}


def write_all(root: Path) -> list[Path]:
    target = root / INCIDENTS_RELATIVE
    target.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, payload in FIXTURES.items():
        path = target / name
        path.write_bytes(payload)
        written.append(path)
    return written


if __name__ == "__main__":
    # ROOT, not Path("."): run from a subdirectory, the cwd version silently builds a
    # SECOND fixture tree there and reports success, leaving this repository's untouched.
    for path in write_all(ROOT):
        print(f"{path.relative_to(ROOT).as_posix()}  {path.stat().st_size} bytes")
    sys.exit(0)
