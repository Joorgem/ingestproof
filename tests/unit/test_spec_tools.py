from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.needs_check import items_without_needs
from tools.oft import (
    OFT_SHA256,
    OFT_VERSION,
    check_counts,
    java_executable,
    report_item_count,
)
from tools.spec_hashes import item_hash, verify, write
from tools.spec_hashes import main as spec_hashes_main
from tools.spec_parse import parse_dir, parse_file

SAMPLE = """# Title

## A criterion
`req~ac-01~1`

The body of the first criterion.

Needs: impl, utest

## A terminating one
`req~ac-02~3`

The body of the second.
"""


@pytest.fixture()
def spec_repo(tmp_path: Path) -> Path:
    (tmp_path / ".spec").mkdir()
    (tmp_path / ".spec" / "acceptance.md").write_text(SAMPLE, encoding="utf-8")
    return tmp_path


def test_the_parser_reads_id_name_revision_and_title(spec_repo: Path) -> None:
    items = parse_file(spec_repo / ".spec" / "acceptance.md")

    assert [i.id for i in items] == ["req~ac-01~1", "req~ac-02~3"]
    assert items[0].name == "ac-01"
    assert items[0].revision == 1
    assert items[1].revision == 3
    assert items[0].title == "A criterion"


def test_the_parser_reads_needs_and_leaves_it_empty_when_absent(spec_repo: Path) -> None:
    items = parse_file(spec_repo / ".spec" / "acceptance.md")

    assert items[0].needs == ["impl", "utest"]
    assert items[1].needs == []


def test_an_item_without_needs_is_reported(spec_repo: Path) -> None:
    # Measured: OFT treats a Needs-less item as terminating, so it traces clean and the
    # coverage gate is inert on it. This check is the whole reason the gate has teeth.
    offenders = items_without_needs(parse_dir(spec_repo))

    assert [i.id for i in offenders] == ["req~ac-02~3"]


def test_the_real_spec_has_needs_on_every_item() -> None:
    offenders = items_without_needs(parse_dir(Path(".")))

    assert offenders == [], f"missing Needs: {[i.id for i in offenders]}"


def test_the_real_spec_has_unique_ids() -> None:
    ids = [i.id for i in parse_dir(Path("."))]

    assert len(ids) == len(set(ids))


def test_a_fresh_hash_file_verifies_clean(spec_repo: Path) -> None:
    write(spec_repo)

    assert verify(spec_repo) == []


def test_editing_a_body_without_bumping_the_revision_is_reported(spec_repo: Path) -> None:
    write(spec_repo)
    path = spec_repo / ".spec" / "acceptance.md"
    path.write_text(SAMPLE.replace("The body of the first", "A DIFFERENT body of the first"),
                    encoding="utf-8")

    assert verify(spec_repo) == ["req~ac-01~1"]


def test_editing_a_body_and_bumping_the_revision_is_accepted(spec_repo: Path) -> None:
    write(spec_repo)
    path = spec_repo / ".spec" / "acceptance.md"
    path.write_text(
        SAMPLE.replace("`req~ac-01~1`", "`req~ac-01~2`")
              .replace("The body of the first", "A DIFFERENT body of the first"),
        encoding="utf-8",
    )

    # req~ac-01~1 has vanished and req~ac-01~2 is new; neither is a silent edit.
    assert verify(spec_repo) == []


def test_removing_an_item_is_reported(spec_repo: Path) -> None:
    write(spec_repo)
    recorded = json.loads((spec_repo / ".spec" / "hashes.json").read_text(encoding="utf-8"))
    recorded["req~ac-99~1"] = "deadbeef"
    (spec_repo / ".spec" / "hashes.json").write_text(json.dumps(recorded), encoding="utf-8")

    assert verify(spec_repo) == ["req~ac-99~1"]


def test_the_hash_ignores_surrounding_whitespace_but_not_words(spec_repo: Path) -> None:
    items = parse_file(spec_repo / ".spec" / "acceptance.md")
    same = item_hash(items[0])
    (spec_repo / ".spec" / "acceptance.md").write_text(
        SAMPLE.replace("The body of the first criterion.",
                       "   The body of the first criterion.   "),
        encoding="utf-8",
    )
    reparsed = parse_file(spec_repo / ".spec" / "acceptance.md")

    assert item_hash(reparsed[0]) == same


def test_java_resolves_through_java_home_not_the_path(monkeypatch, tmp_path: Path) -> None:
    # Measured 19/08: bare `java` is 11.0.31 here and $JAVA_HOME/bin/java is 17.0.19.
    # OFT 4.9.0 is a Java 17 JAR and dies on 11 with a class-version error that says
    # nothing about PATH.
    fake_home = tmp_path / "jdk"
    (fake_home / "bin").mkdir(parents=True)
    exe = fake_home / "bin" / ("java.exe" if __import__("os").name == "nt" else "java")
    exe.write_text("", encoding="utf-8")
    monkeypatch.setenv("JAVA_HOME", str(fake_home))

    assert java_executable() == exe


def test_java_without_java_home_is_an_explicit_error(monkeypatch) -> None:
    monkeypatch.delenv("JAVA_HOME", raising=False)

    with pytest.raises(RuntimeError, match="JAVA_HOME"):
        java_executable()


def test_the_jar_pin_is_the_measured_one() -> None:
    assert OFT_VERSION == "4.9.0"
    assert OFT_SHA256 == "d4ed42503ae066f51d55c3aad7c6e4b16acb80365921951ef5a065a4dc3d94f3"


DUPLICATE_NEEDS = """# Title

## A criterion
`req~ac-01~1`

Needs: impl

Needs: impl, utest

The body of the first criterion.
"""

# Verbatim in shape from a real run of OFT 4.9.0 over this repository: every item line
# opens `not ok [`, and exactly one line -- the summary -- opens `not ok - `. CRLF is
# what the JAR wrote on Windows, so the reader has to tolerate it.
REPORT = (
    "not ok [ in:  0 /  0   | out:  0 /  0   ] req~ac-01~1 (-impl, -utest)\r\n"
    "\r\n"
    "  A new table enters through one declaration.\r\n"
    "\r\n"
    "not ok - 22 total, 22 direct, 0 transitive defects\r\n"
)


def test_a_second_needs_line_is_refused(tmp_path: Path) -> None:
    # Last-one-wins would silently discard the first line: the requirement set OFT reads
    # changes while the body, the hash and needs_check all stay exactly as they were.
    path = tmp_path / "acceptance.md"
    path.write_text(DUPLICATE_NEEDS, encoding="utf-8")

    with pytest.raises(ValueError, match="second `Needs:` line"):
        parse_file(path)


def test_the_jar_item_count_is_read_from_its_summary_line() -> None:
    assert report_item_count(REPORT) == 22


def test_a_report_with_no_summary_line_reads_as_unknown() -> None:
    # None, never 0: a silently unmatched regex would make the count gate permanently
    # green, which is the same failure the gate exists to prevent.
    assert report_item_count("not ok [ in:  0 /  0   ] req~ac-01~1 (-impl)\r\n") is None


def test_the_count_check_passes_when_the_jar_and_the_parser_agree(spec_repo: Path) -> None:
    (spec_repo / "oft-report.txt").write_text(
        "not ok - 2 total, 2 direct, 0 transitive defects\r\n", encoding="utf-8")

    assert check_counts(spec_repo) == 0


def test_the_count_check_fails_on_an_item_the_parser_cannot_see(spec_repo: Path) -> None:
    (spec_repo / "oft-report.txt").write_text(
        "not ok - 3 total, 3 direct, 0 transitive defects\r\n", encoding="utf-8")

    assert check_counts(spec_repo) == 1


def test_the_count_check_fails_when_the_report_is_missing(spec_repo: Path) -> None:
    assert check_counts(spec_repo) == 1


def test_the_count_check_fails_on_a_report_it_cannot_parse(spec_repo: Path) -> None:
    (spec_repo / "oft-report.txt").write_text("something else entirely\r\n", encoding="utf-8")

    assert check_counts(spec_repo) == 1


def test_a_spec_with_no_items_is_an_error_not_a_success(tmp_path: Path, monkeypatch) -> None:
    # "0 criterion hashes verified" as a success line is backwards for this project: a
    # missing or unreadable .spec/ would go green exactly as loudly as a verified one.
    monkeypatch.chdir(tmp_path)

    assert spec_hashes_main([]) == 1
    assert spec_hashes_main(["update"]) == 1
