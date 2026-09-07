#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nothing may decide behaviour from ``scitex_todo`` alone.

``scitex_todo`` was renamed to ``scitex_cards`` on 2026-07-16 and scitex-cards
0.41.0 (2026-08-16) DELETED the alias — ``import scitex_todo`` now raises
ModuleNotFoundError. Anything still probing only the old name silently decides
"not installed" on a host where the board is installed, mounted and serving.

That is not hypothetical. It shipped in two places:

    apps/infra/workspace_app/registry.py   the launcher tile probe. Returned
                                           None under 0.41.0, so the Cards TILE
                                           VANISHED from the launcher while
                                           /apps/cards/ kept working — a
                                           user-visible regression with no
                                           error logged anywhere.

    tests/config/test_todo_mount.py        gated its whole suite on the alias.
                                           Under 0.41.0 three mount tests SKIP
                                           (green over an unrun suite) and the
                                           fourth INVERTS and asserts the mount
                                           is absent on a host where it exists.

The pattern that survives a rename is CANONICAL FIRST, alias tolerated: probe
``scitex_cards`` and accept ``scitex_todo`` only as an additional way to say
yes. ``config/urls.py`` and ``apps/workspace/todo_app/middleware.py`` already
did exactly that and were unaffected — they are the shape to copy.

WHAT THIS CHECKS, stated honestly: it is a TEXTUAL gate. It asserts that any
hub source file mentioning the deprecated name also mentions the canonical one,
which is a proxy for "does not decide from the alias alone". It cannot prove
the two are combined correctly — a file could name both and still branch
wrongly. It is here because the failure mode is a silent absence that no
behavioural test notices, and a cheap proxy that fires is worth more than an
exact check nobody writes.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

DEPRECATED = "scitex_todo"
CANONICAL = "scitex_cards"

#: Trees whose behaviour depends on whether the board package is installed.
_SEARCH_ROOTS = ("apps", "config", "tests", "scripts")

#: Env vars and app labels keep the historical spelling and are NOT the
#: package. todo_app is hub's local Django app, unrelated to the upstream
#: distribution.
#:
#: CORRECTED 2026-09-07: this said "SCITEX_TODO_LANE_GLOBS is upstream's own
#: documented env name". It is NOT, and had not been since the rename —
#: scitex_cards reads SCITEX_CARDS_LANE_GLOBS and nothing anywhere reads the
#: SCITEX_TODO_ one. hub was exporting the retired name, so its tenancy
#: opt-out did nothing (fixed in config/settings/_optional_apps.py).
#:
#: The SCITEX_TODO_ entry stays, but as plain defence rather than as a claim
#: about upstream: this scan greps the LOWERCASE package name case-sensitively,
#: so an uppercase env var never made a file a candidate here and this sweep
#: was never the gate that would have caught that drift. Do not read its
#: presence as evidence the prefix is still live upstream.
_NOT_THE_PACKAGE = ("SCITEX_TODO_", "todo_app", "scitex_todo_app")


def _files_mentioning(needle: str) -> set[str]:
    proc = subprocess.run(
        ["git", "-C", str(REPO), "grep", "-l", needle, "--", *_SEARCH_ROOTS],
        capture_output=True,
        text=True,
        timeout=120,
    )
    # git grep exits 1 on "no matches"; that is a valid answer, not a failure.
    assert proc.returncode in (0, 1), f"git grep failed: {proc.stderr.strip()}"
    return {ln for ln in proc.stdout.splitlines() if ln.strip()}


@pytest.fixture(name="alias_files", scope="module")
def _alias_files() -> set[str]:
    """Files that reference the deprecated package name in a load-bearing way."""
    candidates = _files_mentioning(DEPRECATED)
    keep: set[str] = set()
    for rel in candidates:
        text = (REPO / rel).read_text(encoding="utf-8", errors="replace")
        # Drop files whose only hits are env vars or hub's own app label.
        hits = [
            ln
            for ln in text.splitlines()
            if DEPRECATED in ln and not any(x in ln for x in _NOT_THE_PACKAGE)
        ]
        if hits:
            keep.add(rel)
    return keep


def test_no_file_decides_from_the_alias_alone(alias_files: set[str]) -> None:
    # Arrange
    canonical_files = _files_mentioning(CANONICAL)

    # Act
    alias_only = sorted(alias_files - canonical_files)

    # Assert
    assert alias_only == [], (
        f"these files reference {DEPRECATED!r} but never {CANONICAL!r}, so they "
        f"decide from a package name that no longer exists (deleted in "
        f"scitex-cards 0.41.0): {alias_only}. Probe {CANONICAL!r} first and "
        f"accept {DEPRECATED!r} only as an additional way to say yes — see "
        "config/urls.py for the shape."
    )


def test_the_scan_actually_looks_at_something(alias_files: set[str]) -> None:
    # Arrange — POSITIVE CONTROL. If git grep stopped matching (roots renamed,
    # the alias fully purged, a bad pathspec), the test above would compare two
    # empty sets and pass while checking nothing.
    #
    # If the alias genuinely disappears from hub one day this WILL fail, and
    # that is the correct moment to delete this file rather than relax it.
    # Act / Assert
    assert alias_files, (
        f"no file references {DEPRECATED!r} any more. If that is deliberate, "
        "delete this test file — its job is done. If it is not, the scan is "
        "broken and was silently checking nothing."
    )
