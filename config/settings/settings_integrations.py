#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Timestamp: 2026-02-04
# File: config/settings/settings_integrations.py
"""Third-party integrations settings for SciTeX Hub."""

import os
from pathlib import Path

import scitex as stx

# Get BASE_DIR from parent
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------
# SciTeX Scholar Search Settings
# ---------------------------------------
# Enable/disable search pipeline caching
SCITEX_SCHOLAR_USE_CACHE = os.getenv("SCITEX_SCHOLAR_USE_CACHE", "True").lower() in [
    "true",
    "1",
    "yes",
]

# Maximum parallel workers for parallel search pipeline
SCITEX_SCHOLAR_MAX_WORKERS = int(os.getenv("SCITEX_SCHOLAR_MAX_WORKERS", "5"))

# Timeout per engine in seconds
SCITEX_SCHOLAR_TIMEOUT_PER_ENGINE = int(
    os.getenv("SCITEX_SCHOLAR_TIMEOUT_PER_ENGINE", "60")
)

# Preferred engines (comma-separated)
SCITEX_SCHOLAR_ENGINES = os.getenv(
    "SCITEX_SCHOLAR_ENGINES", "CrossRef,PubMed,Semantic_Scholar,arXiv,OpenAlex"
).split(",")

# Default search mode: "parallel" or "single"
SCITEX_SCHOLAR_DEFAULT_MODE = os.getenv("SCITEX_SCHOLAR_DEFAULT_MODE", "parallel")

# Crossref endpoint scitex-scholar's citation graph resolves.
#
# READ AS A DJANGO SETTING, NEVER AS AN ENVIRONMENT VARIABLE. Mounted inside a
# host project, scholar's _api_url() does
# getattr(settings, "SCITEX_SCHOLAR_CROSSREF_API_URL"), falls back to the
# deprecated CROSSREF_API_URL alias, and returns None -> 503 before the builder
# is constructed. Its own env-var fallback lives in scholar's STANDALONE
# settings module, which never executes in our process.
#
# So exporting the variable is not enough, and that is exactly how this hid:
# the value was set in the prod container and in both .env.example files, and
# defined in no .py file, so /apps/scholar/v2/ answered 503 "not configured"
# while every place a human would look showed it configured. This line is what
# makes the environment reach the code.
#
# NO DEFAULT, ON PURPOSE. Unconfigured must stay None so scholar's explicit 503
# still fires; a plausible-looking default would convert an honest "not
# configured" into requests aimed at the wrong host — a worse failure, because it
# fails while looking like it works.
#
# `or None` IS LOAD-BEARING, NOT STYLE — do not simplify it away. scholar's
# _api_url() returns this setting when it `is not None`, and only falls through
# to the deprecated bare CROSSREF_API_URL alias when it IS None. So an
# accidentally-empty export behaves differently in the two spellings:
#     ""   (without `or None`)  -> "" is not None -> returned -> 503, and the
#                                  alias is NEVER consulted
#     None (with `or None`)     -> falls through to the alias, as intended
# Both end in a 503 today, so nothing is visibly broken without it; the hazard is
# confined to the one-release window in which the alias still works. Confirmed
# against the resolver by scitex-scholar 2026-09-07.
SCITEX_SCHOLAR_CROSSREF_API_URL = os.getenv("SCITEX_SCHOLAR_CROSSREF_API_URL") or None

# ---------------------------------------
# SciTeX Scholar Library Settings
# ---------------------------------------
# User-level library storage mode: "user_level" (new) or "django_media" (legacy)
SCITEX_SCHOLAR_LIBRARY_MODE = os.getenv("SCITEX_SCHOLAR_LIBRARY_MODE", "django_media")

# User-level library root directory (per-user isolation)
# Default: ~/.scitex/scholar/library/
SCITEX_SCHOLAR_USER_LIBRARY_ROOT = Path(
    os.getenv(
        "SCITEX_SCHOLAR_USER_LIBRARY_ROOT",
        str(Path.home() / ".scitex" / "scholar" / "library"),
    )
)

# User data root for multi-user Django deployments
# If set, user libraries will be at: {USER_DATA_ROOT}/users/{username}/.scitex/scholar/library/
USER_DATA_ROOT = (
    Path(os.getenv("SCITEX_HUB_USER_DATA_ROOT", ""))
    if os.getenv("SCITEX_HUB_USER_DATA_ROOT")
    else None
)

# Public API campaign key (shared key for experiments/demos)
# Set via environment: SCITEX_HUB_CAMPAIGN_API_KEY=your-shared-key
SCITEX_HUB_CAMPAIGN_API_KEY = os.getenv("SCITEX_HUB_CAMPAIGN_API_KEY", None)

# ---------------------------------------
# SciTeX Writer Settings
# ---------------------------------------
# Check common locations for scitex-writer template
_WRITER_TEMPLATE_LOCATIONS = [
    Path(os.getenv("SCITEX_WRITER_TEMPLATE_PATH", "")),
    Path.home() / "proj" / "scitex-writer",
    Path("/tmp/scitex-writer"),
    BASE_DIR / "docs" / "scitex_writer_template",
]

SCITEX_WRITER_TEMPLATE_PATH = None
for location in _WRITER_TEMPLATE_LOCATIONS:
    if location and location.exists():
        SCITEX_WRITER_TEMPLATE_PATH = location
        break

# ---------------------------------------
# CrossRef Local API
# ---------------------------------------
CROSSREF_INTERNAL_URL = os.getenv(
    "SCITEX_HUB_CROSSREF_INTERNAL_URL", "http://crossref:31291"
)

# CrossRef database path for citation graph service
CROSSREF_DB_PATH = os.getenv(
    "SCITEX_HUB_CROSSREF_DB_PATH",
    str(Path.home() / "proj/crossref_local/data/crossref.db"),
)

# ---------------------------------------
# REST Framework
# ---------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        # APIKeyAuthentication adapts the existing `scitex_xxxx` UI-PAT
        # (apps.infra.accounts_app.models.api_key.APIKey) to DRF's
        # authentication contract so a UI-generated PAT works on every
        # DRF endpoint — /api/project/create/, /api/apps/submit/, and the
        # project-scoped <u>/<slug>/api/* family (which already accepts
        # Bearer-anything via the JWT middleware from PR #268). The class
        # ONLY recognises tokens that start with `Bearer scitex_` so the
        # JWT path below is unaffected.
        #
        # Order matters at TWO levels:
        #
        # 1. AUTHENTICATION CHAIN — APIKeyAuthentication runs before
        #    JWTAuthentication so a `Bearer scitex_xxxx` request lands
        #    here first. JWTAuthentication would otherwise raise
        #    AuthenticationFailed on a non-JWT-shaped token and short-
        #    circuit the chain (DRF doesn't fall through on raised auth
        #    failures — only on None returns).
        #
        # 2. STATUS-CODE LOOKUP — when ALL auth classes return None or
        #    one raises AuthenticationFailed, DRF reads the FIRST class's
        #    `authenticate_header()` to decide 401-vs-403. SessionAuth
        #    returns None (no WWW-Authenticate scheme makes sense for
        #    cookies), which makes DRF respond 403. Placing APIKeyAuth
        #    first puts its `Bearer realm="api"` header at the head of
        #    the list, so failed-auth responses are correctly 401 for
        #    the bad-credentials contract the tests in
        #    `tests/apps/accounts_app/test_apikey_authentication.py`
        #    pin (see lead 2026-06-13 msg 9c96b9d5 + PR #274 root-cause).
        "apps.infra.accounts_app.authentication.APIKeyAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        # Session last — still needed for browser-cookie auth on the UI
        # AJAX surface but contributes nothing for the API token path.
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}


# ---------------------------------------
# Main Guard
# ---------------------------------------
@stx.session
def main(CONFIG=stx.session.INJECTED):
    """Settings module - not meant to be executed directly."""
    print("This is a Django settings module. Import it, don't execute it.")
    return 0


if __name__ == "__main__":
    main()

# EOF
