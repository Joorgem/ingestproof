"""Unit-ring fixtures.

`ingestproof.contracts._REGISTRY` is process-wide, and it has to be: the frozen
acceptance test calls `register("no-such-contract-id")` from a module that imported three
names and was handed no registry. The cost is that a declaration made by one test is
visible to every test after it, in whatever order pytest happens to collect them.

Measured before this file existed: after
`test_one_contract_id_may_not_answer_two_different_tables` ran, `register("shared@1")`
answered `first_table` for the rest of the session. Worse, `tests/unit/test_contracts.py`
defaults `contract_id` to `incidents@1` -- the same id the FROZEN acceptance test
declares -- so one future unit test declaring a varied `incidents@1` would turn
`tests/acceptance/test_ac01_one_declaration.py` red, in a file nobody may edit, for a
reason living in another module.

This file is the smallest place that closes it. `tests/conftest.py` is outside the
writable set, so the fixture cannot be hoisted to cover the acceptance ring as well;
what it can do is stop the unit ring from being the one that leaks.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ingestproof import contracts


@pytest.fixture(autouse=True)
def _isolated_contract_registry() -> Iterator[None]:
    """Restore the registry around every unit test, rather than merely clearing it after.

    Snapshot-and-restore, not clear-on-exit: whatever the acceptance ring declared before
    this ring started is still there when it finishes, so a test that runs later and
    depends on it is unaffected either way.
    """
    saved = dict(contracts._REGISTRY)
    contracts._REGISTRY.clear()
    try:
        yield
    finally:
        contracts._REGISTRY.clear()
        contracts._REGISTRY.update(saved)
