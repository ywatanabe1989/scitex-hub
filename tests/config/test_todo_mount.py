#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Guards for the upstream scitex-todo board mount (phase 1: read-only).

Mirrors tests/config/test_writer_mount.py: when the ``scitex_todo``
package is importable, its contract-compliant ``_django`` app must be
installed under the explicit ``ScitexTodoConfig`` path (a bare module
entry falls back to app label ``_django`` and collides with
``figrecipe._django``'s identical fallback) and URL-mounted at
``/apps/cards/`` (the Cards rebrand; /apps/todo/ 301-redirects there).
When the package is absent, neither must appear.

Tenancy (the hub-specific piece) is covered separately in
tests/apps/todo_app/test_tenancy_middleware.py.
"""

from importlib.util import find_spec

import pytest

# Gate on the CANONICAL name, with the deprecated alias still accepted.
#
# This read `find_spec("scitex_todo")` alone. That package was renamed to
# scitex-cards on 2026-07-16 and scitex-cards 0.41.0 (2026-08-16) DELETED the
# alias, so on a current install the probe returns None — and this file then
# does the worst possible thing: the three tests that gate the mount SKIP
# (green over an unrun suite, protecting nothing), while
# `test_cards_url_absent_when_package_missing` INVERTS, runs, and asserts the
# mount is absent on a host where the board is installed and mounted. One
# rename turned this file from a guard into a false alarm plus three no-ops.
_TODO_INSTALLED = (
    find_spec("scitex_cards") is not None or find_spec("scitex_todo") is not None
)


@pytest.mark.skipif(not _TODO_INSTALLED, reason="scitex-todo not installed")
def test_todo_app_installed_via_explicit_appconfig_path():
    # Arrange
    from django.conf import settings

    # Act — the CLASS name is no longer fixed. Upstream renamed it
    # (ScitexTodoConfig -> ScitexCardsConfig) on develop with no alias while
    # every published wheel through 0.40.0 kept the old one, and hub installs
    # both sources, so config/settings/_optional_apps.py resolves whichever is
    # present. This asserts against the SAME candidate list rather than a
    # literal, so the mount is still pinned but the test does not have to be
    # edited every time upstream moves.
    #
    # What stays load-bearing is the EXPLICIT AppConfig path: a bare
    # "scitex_cards._django" entry falls back to label "_django" and collides
    # with figrecipe._django's identical fallback.
    from config.settings._optional_apps import CARDS_APPCONFIG_NAMES

    expected = {f"scitex_cards._django.apps.{n}" for n in CARDS_APPCONFIG_NAMES}
    matched = expected & set(settings.INSTALLED_APPS)

    # Assert
    assert len(matched) == 1, (
        f"expected exactly one of {sorted(expected)} in INSTALLED_APPS, "
        f"found {sorted(matched)}"
    )


@pytest.mark.skipif(not _TODO_INSTALLED, reason="scitex-todo not installed")
def test_cards_root_url_resolves_to_board_namespace():
    # Arrange — upstream is mid-rebrand: older scitex-todo releases
    # namespace their URLs "scitex_todo", newer ones "scitex_cards".
    # The module path (scitex_todo._django.urls) is unchanged either
    # way; accept both so the guard tracks the mount, not the version.
    from django.urls import resolve

    # Act
    match = resolve("/apps/cards/")

    # Assert
    assert match.view_name.startswith(("scitex_todo:", "scitex_cards:"))


@pytest.mark.skipif(not _TODO_INSTALLED, reason="scitex-todo not installed")
def test_legacy_todo_path_redirects_to_cards():
    # Arrange — old links and pinned tiles must keep working after the
    # Cards rebrand, subpath and query string included.
    from django.test import Client

    # Act
    resp = Client().get("/apps/todo/board/?lane=open", follow=False)

    # Assert
    assert (resp.status_code, resp["Location"]) == (
        301,
        "/apps/cards/board/?lane=open",
    )


@pytest.mark.skipif(not _TODO_INSTALLED, reason="scitex-todo not installed")
def test_lane_globs_disabled_for_tenancy_under_the_name_the_package_READS():
    """The opt-out must be set under the env name the CONSUMER reads.

    This asserted ``SCITEX_TODO_LANE_GLOBS`` — the pre-rename name — and
    passed for it while the guard did nothing, because scitex_cards reads
    ``SCITEX_CARDS_LANE_GLOBS`` and nothing anywhere reads the old one.
    A test naming the variable independently of its consumer can only ever
    prove that SOMETHING was exported; it cannot prove the export lands
    where the code looks. So the name is imported from the package.

    Why it matters (the original comment, still true): the union would leak
    host lanes to every hub user. `_discover_lanes` falls back to
    ``DEFAULT_LANE_GLOBS`` (``~/proj/*/.scitex/cards/tasks.yaml``) when the
    variable is UNSET, and an explicitly-empty value is the documented
    opt-out — so "unset" and "set to empty" are opposite behaviours here,
    and hub was effectively in the first.
    """
    # Arrange — the consumer's own constant, never a literal.
    import os

    from scitex_cards._django.services import ENV_LANE_GLOBS

    # Act
    value = os.environ.get(ENV_LANE_GLOBS)

    # Assert
    assert value == "", (
        f"{ENV_LANE_GLOBS} is {value!r}; it must be the empty string. Unset "
        "means _discover_lanes falls back to DEFAULT_LANE_GLOBS and unions "
        "every per-project lane on the host into the board."
    )


@pytest.mark.skipif(not _TODO_INSTALLED, reason="scitex-todo not installed")
def test_the_retired_lane_globs_name_is_not_what_we_rely_on():
    """Negative control: the old name must not be the ONLY thing exported.

    Without this, restoring the bug (setting only the retired name) would
    leave the suite green as soon as someone re-pins the test above to a
    literal. Pairing them means the suite fails if the export ever drifts
    back off the consumer's name.
    """
    # Arrange
    import os

    from scitex_cards._django.services import ENV_LANE_GLOBS

    # CAPTURE FIRST, then assert on the local. Asserting directly on
    # `os.environ.get(...)` makes pytest expand os.environ in the failure
    # report — the whole environment, tokens included, into the CI log.
    # Observed while writing this test: the first run printed GH_TOKEN and
    # SAC_LISTEN_BEARER before a hook redacted them.
    value = os.environ.get(ENV_LANE_GLOBS)

    # Assert — whatever the retired name holds, the canonical one decides.
    assert ENV_LANE_GLOBS != "SCITEX_TODO_LANE_GLOBS", (
        "upstream now reads the retired name; this guard is obsolete"
    )
    assert value == "", (
        f"the opt-out is not set under {ENV_LANE_GLOBS}, the name the package "
        f"reads (got {value!r})"
    )


@pytest.mark.skipif(_TODO_INSTALLED, reason="scitex-todo is installed")
def test_cards_url_absent_when_package_missing():
    # Arrange — with the package absent the /apps/cards/ mount must not
    # exist. NOTE: resolve() may still MATCH something (catch-all routes
    # swallow unmounted paths — same as /writer/), so the contract here
    # is "does not resolve into the scitex_todo namespace", never a bare
    # Resolver404.
    from django.urls import Resolver404, resolve

    # Act
    try:
        view_name = resolve("/apps/cards/").view_name
    except Resolver404:
        view_name = ""

    # Assert
    assert not view_name.startswith(("scitex_todo:", "scitex_cards:"))
