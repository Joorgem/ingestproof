"""A THROWAWAY PROBE. Delete this file and its line in `nightly.yml` once it has answered.

THE QUESTION. `req~ac-08a~1`'s acceptance test has to start a Spark session inside pytest,
and measured on the development machine that DEADLOCKS under pytest's output capture: three
runs with capture all hung in `JavaSparkContext(jconf)` waiting on the py4j socket -- one for
420s producing not one line -- while two runs with `-s` got past it and the same session built
outside pytest came up in 33.4s. The plausible mechanism is the Ivy resolution flooding a
captured pipe nobody drains.

The nightly ring runs `uv run pytest -m nightly`, on Linux, WITHOUT `-s`. If the deadlock is
pytest's capture rather than Windows', the acceptance file would hang the ring for its whole
timeout instead of failing, and `tests/acceptance/**` is frozen: that defect would cost a
human commit to correct after the fact.

So this asks the mechanism and nothing about the criterion. It is not a gate, it covers no
requirement, and it carries no `[utest->...]` tag on purpose -- a tag here would move OFT's
count for a file that is meant to be deleted.

WHAT ITS TWO OUTCOMES MEAN.

ANSWERED, run 33225216543 of 2026-08-29: `1 passed, 480 deselected in 42.69s`. Capture does
NOT deadlock the JVM on the runner; the deadlock is the development machine's. What is still
open, and is why this file has not been deleted yet, is which Delta coordinate is actually
resolved -- see the test's own docstring.

    passes   pytest's capture does not deadlock the JVM on the runner. The deadlock is the
             development machine's, the ac-08a draft's structure stands, and the numbers it
             prints are the ones that file's docstring should cite.

    times out capture is the cause and it is not Windows-specific. The ac-08a draft cannot
             build a session the way it does, and the fix has to be inside the frozen file:
             jars resolved ahead of the launch rather than by Ivy at launch, so there is no
             flood to deadlock on.

IT IS DECLARED IN THE RING, AND THAT IS THE GATE WORKING RATHER THAN BEING WORKED AROUND. A
`nightly`-marked test under `tests/unit/**` is exactly what the `ring` job's UNDECLARED check
exists to catch, because that path is writable by a turn and `prompt.md` counts `skip` and
`xfail` into the ledger but not `nightly`. This one is a human's, in the same commit as its
declaration, which is the only way it runs at all.

THE TIMEOUT IS THE ASSERTION. `pyproject.toml`'s `addopts` carries `--timeout=60` and a cold
session is 33s before any Ivy resolution, so 60 is not a budget this can live inside. 420 is
chosen against the measurement that matters: the development machine's capture deadlock
survived 420 seconds and produced nothing, so a run that gets past it here is answering the
question rather than merely being luckier. On Linux pytest-timeout uses SIGALRM and reports a
FAILURE, so a deadlock lands as a red test rather than as a killed process.
"""

from __future__ import annotations

import os
import pathlib
import platform
import sys
import time

import pytest

pytestmark = [pytest.mark.nightly, pytest.mark.timeout(420)]


def _report(line: str) -> None:
    """Say it where a PASSING test's output survives.

    Measured on run 33225216543: this probe passed in 42.69s and every `print` it made was
    swallowed -- pytest shows captured stdout only for a FAILING test, and the job's command
    is `uv run pytest -m nightly` with no `-rA` and no `-s`. The command lives in a frozen
    file and is a gate; widening it so a throwaway probe can talk would be the probe changing
    the thing it was written to ask about. `$GITHUB_STEP_SUMMARY` is the runner's own channel
    for exactly this and costs the gate nothing.
    """
    print(line, flush=True)
    page = os.environ.get("GITHUB_STEP_SUMMARY")
    if page:
        with pathlib.Path(page).open("a", encoding="utf-8") as handle:
            handle.write("- " + line + "\n")


def test_a_spark_session_starts_and_delta_round_trips_under_capture(tmp_path) -> None:
    """Build a session, write a Delta table, read it back. Print what it took.

    Everything printed here reaches the run log rather than an assertion, because the facts
    worth having are the ones a PASS carries: which Delta coordinate `configure_spark_with_
    delta_pip` actually resolved, and how long the launch took. Measured on the development
    machine, the Ivy cache came back holding `io.delta_delta-spark_2.12-3.3.1.jar` -- Scala
    2.12 and Delta 3.3.1 -- against an installed delta-spark 4.4.0 on a pyspark 4.2.0 that is
    Scala 2.13. That pairing is either wrong or resolved differently than it reads, and this
    is the cheapest place to find out which.
    """
    started = time.monotonic()

    import delta
    import pyspark
    from delta import configure_spark_with_delta_pip
    from pyspark.sql import SparkSession

    _report(f"platform: {platform.platform()}")
    _report(f"python: {sys.version.split()[0]}")
    _report(f"pyspark: {pyspark.__version__}")
    _report(f"delta-spark: {getattr(delta, '__version__', 'unknown')}")

    builder = (
        SparkSession.builder.master("local[1]")
        .appName("probe")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "1")
    )
    configured = configure_spark_with_delta_pip(builder)
    _report("builder configured; asking for the session now")

    session = configured.getOrCreate()
    session.sparkContext.setLogLevel("ERROR")
    launched = time.monotonic()
    _report(f"session up in {launched - started:.1f}s")
    _report(f"jars.packages: {session.conf.get('spark.jars.packages', '(unset)')}")

    try:
        location = (tmp_path / "probe").as_posix()
        frame = session.createDataFrame(
            [("a", "one"), ("b", "two"), ("a", "three")], "k string, v string"
        )
        frame.write.format("delta").mode("overwrite").save(location)
        back = session.read.format("delta").load(location).where("k = 'a'").collect()

        assert sorted(row.v for row in back) == ["one", "three"], back
        _report(f"delta round trip done at {time.monotonic() - started:.1f}s")
    finally:
        session.stop()
