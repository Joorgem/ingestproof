"""The deterministic test environment, asserted rather than assumed.

`derandomize=True` plus `database=None` is what makes a turn reproducible: the seed
becomes a hash of the test's cleaned source, so the same code always draws the same
corpus. The consequence, and it bites (spec section 7.7): RENAMING OR EDITING A PROPERTY
TEST RE-DRAWS ITS ENTIRE CORPUS, so a green can turn red with no production change. The
turn protocol forbids editing a property test in the same commit that touches src/**.
"""
from __future__ import annotations

import os

from hypothesis import settings

settings.register_profile(
    "ci",
    derandomize=True,
    database=None,
    max_examples=200,
    deadline=None,
    print_blob=True,
)
settings.register_profile(
    "dev",
    derandomize=False,
    database=None,
    max_examples=50,
    deadline=None,
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))
