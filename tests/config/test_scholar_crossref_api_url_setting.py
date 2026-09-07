#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Guard the Django SETTING scitex-scholar reads for its crossref endpoint.

/apps/scholar/v2/ answers 503 "not configured" on production while the
environment variable it appears to need is plainly set. Both halves are true at
once, and that is the whole trap:

    prod container   SCITEX_SCHOLAR_CROSSREF_API_URL   SET
    hub source       SCITEX_SCHOLAR_CROSSREF_API_URL   defined in NO .py file

scitex-scholar reads a DJANGO SETTING, never the environment, when it is mounted
inside a host project. Traced in the shipped code by scitex-scholar 2026-09-07:

    graph route -> _get_builder() -> _api_url()
        -> getattr(settings, "SCITEX_SCHOLAR_CROSSREF_API_URL")
        -> else getattr(settings, "CROSSREF_API_URL")   # deprecated alias
        -> if still None: return None -> 503 BEFORE the builder is constructed

The builder's own env-var fallback lives in scholar's STANDALONE settings module,
which never executes in hub's process. So the value is present everywhere a human
would look and absent from the only place the code reads, and the page fails with
a message that sounds like the endpoint is missing rather than the wiring.

The env var is read HERE, in hub's settings, or it is not read at all.

Two-sided on purpose. Asserting only "the setting exists" would pass on a
hardcoded constant, which would silently pin every deployment to one endpoint;
asserting only the wiring would pass on a setting that defaults to a plausible
URL, which would replace an honest 503 with requests to the wrong host. So:
configured -> the environment's value reaches the setting; unconfigured -> None,
and scholar's explicit 503 still fires.

Uses the real os.environ and a real module reload; no mocks (STX-NM003) and no
monkeypatch (STX-NM002).
"""

import importlib
import os

import pytest

SETTING = "SCITEX_SCHOLAR_CROSSREF_API_URL"
_MODULE = "config.settings.settings_integrations"


def _reload_with_env(value):
    """Reload the settings module with SETTING set to ``value`` (None = unset).

    Restores the caller's environment whatever happens, so ordering between
    these tests — and against the rest of the suite — cannot matter.
    """
    had = SETTING in os.environ
    previous = os.environ.get(SETTING)
    try:
        if value is None:
            os.environ.pop(SETTING, None)
        else:
            os.environ[SETTING] = value
        module = importlib.import_module(_MODULE)
        return importlib.reload(module)
    finally:
        if had:
            os.environ[SETTING] = previous
        else:
            os.environ.pop(SETTING, None)


def test_crossref_api_url_reaches_the_setting_from_the_environment():
    # Arrange — a value nothing could plausibly hardcode.
    sentinel = "http://crossref-endpoint.invalid:8123/probe"

    # Act
    module = _reload_with_env(sentinel)

    # Assert — the name must EXIST and carry the environment's value.
    assert hasattr(module, SETTING), (
        f"{_MODULE} does not define {SETTING}. scitex-scholar reads this as a "
        "Django setting and 503s when it is absent, no matter what the "
        "environment variable says."
    )
    assert getattr(module, SETTING) == sentinel, (
        f"{SETTING} did not take its value from the environment "
        f"(got {getattr(module, SETTING)!r}). A hardcoded endpoint would pin "
        "every deployment to one host."
    )


def test_crossref_api_url_is_none_when_unconfigured():
    # Arrange / Act — the negative control: genuinely unconfigured.
    module = _reload_with_env(None)

    # Assert — None, NOT a default. An unconfigured host must keep scholar's
    # explicit 503 rather than quietly issuing requests to somewhere wrong.
    assert hasattr(module, SETTING), f"{_MODULE} does not define {SETTING}"
    assert getattr(module, SETTING) is None, (
        f"{SETTING} defaulted to {getattr(module, SETTING)!r} with nothing "
        "configured. A default here converts an honest 'not configured' 503 "
        "into requests aimed at the wrong endpoint."
    )


def test_django_settings_namespace_exposes_the_setting():
    """The attribute scholar's ``getattr(settings, ...)`` actually resolves.

    settings_shared star-imports settings_integrations, and every environment
    module star-imports settings_shared, so defining it in that module is what
    puts it on ``django.conf.settings``. This asserts the end of that chain
    rather than trusting it.
    """
    # Arrange
    from django.conf import settings

    # Assert — presence only. The VALUE depends on the environment the suite
    # runs in, and asserting one here would make this test a statement about
    # the CI host rather than about hub's wiring.
    assert hasattr(settings, SETTING), (
        f"django.conf.settings has no {SETTING}; scholar falls through to the "
        "deprecated CROSSREF_API_URL alias and then to a 503."
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
