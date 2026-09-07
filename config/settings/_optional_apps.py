#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# File: config/settings/_optional_apps.py
"""Which upstream SciTeX apps are installed, and what their AppConfig paths are.

Extracted from ``settings_shared.py`` on 2026-08-16. Four blocks shared one
shape — import the package, append an AppConfig path, skip on ImportError — and
one responsibility: reason about third-party packaging. It is also where every
upstream-rename incident lands, which is the better argument for its own file.

WHY THE AppConfig PATH IS EXPLICIT AND NEVER A BARE MODULE ENTRY. figrecipe,
writer and cards each ship an ``apps.py`` holding two AppConfig candidates (the
imported ``ScitexAppConfig`` base plus their own) with no ``default=True``. A
bare ``"<pkg>._django"`` entry falls back to the label ``_django``, and those
fallbacks collide with each other. storage is the exception — ``StorageConfig``
sets ``default=True`` and a unique label — and is spelled out anyway so all four
read the same.
"""

from __future__ import annotations

import logging
import os
from importlib import import_module
from types import ModuleType

logger = logging.getLogger(__name__)

#: scitex-cards AppConfig class names to accept, NEWEST FIRST.
#:
#: A RENAME MIGRATION WINDOW WE DID NOT OPEN. On 2026-08-16 scitex-cards'
#: ``develop`` renamed ``ScitexTodoConfig`` -> ``ScitexCardsConfig`` with NO
#: alias. An AppConfig path in ``INSTALLED_APPS`` is a published contract, so
#: that is a migration, not a rename — alias first, then remove. Upstream did
#: the second half only.
#:
#: Hub cannot wait, because hub consumes the branch: ``.scitex-apps.json`` pins
#: this sibling to ``git_ref: "develop"`` and ``scripts/apps/install_apps.sh``
#: pip-installs it — in CI, and in ``root-init.sh`` at prod container start.
#: Meanwhile every published wheel through 0.40.0 still defines the OLD name
#: (verified by reading the 0.40.0 wheel off PyPI, which disagrees with its own
#: git tag). The two install paths hub uses disagree, so hardcoding either name
#: breaks the other.
#:
#: Order matters only where a build defines both — the expected shape if
#: upstream does add the alias — and preferring the new name means hub stops
#: depending on the deprecated one the moment it can.
#:
#: DELETE THIS SHIM once upstream ships an alias, or once a release carries the
#: new name and hub's floor requires it.
#: Tracked: cards-appconfig-renamed-without-an-alias-20260816
CARDS_APPCONFIG_NAMES = ("ScitexCardsConfig", "ScitexTodoConfig")


def cards_appconfig_path(apps_module: ModuleType) -> str:
    """Return the dotted ``INSTALLED_APPS`` path for scitex-cards' AppConfig.

    :raises RuntimeError: when the module defines none of
        :data:`CARDS_APPCONFIG_NAMES`.

    Deliberately NOT an ``ImportError``: :func:`optional_upstream_apps` treats
    that type as "this app is not installed, skip it", so raising it here would
    be swallowed and would drop the board mount silently — an app vanishing
    from a running site with nothing in the log. This must reach the operator
    at ``django.setup()``.
    """
    for name in CARDS_APPCONFIG_NAMES:
        if hasattr(apps_module, name):
            return f"scitex_cards._django.apps.{name}"

    found = [n for n in dir(apps_module) if n.endswith("Config")]
    raise RuntimeError(
        "scitex_cards is installed but its _django app defines none of "
        f"{list(CARDS_APPCONFIG_NAMES)}; it defines {found}. Upstream has "
        "renamed the AppConfig again. Add the new name to the FRONT of "
        "CARDS_APPCONFIG_NAMES in config/settings/_optional_apps.py."
    )


def cards_lane_globs_env() -> str:
    """Return the env var name scitex-cards reads for per-project lane discovery.

    :raises RuntimeError: when that name cannot be imported from the installed
        package.

    IMPORTED, NEVER SPELLED HERE. The hub does not get to choose this name —
    the same rule :data:`CARDS_STORE_UPSTREAM_ENV` states — and spelling it as
    a literal is precisely what broke: the call site set
    ``SCITEX_TODO_LANE_GLOBS``, the pre-rename spelling, for the whole life of
    the guard, while scitex_cards read ``SCITEX_CARDS_LANE_GLOBS`` and nothing
    anywhere read the old one. A wrong literal here disables a tenancy control
    and changes nothing observable, so there is no symptom to notice.

    Deliberately NOT an ``ImportError``, for the reason
    :func:`cards_appconfig_path` documents: :func:`optional_upstream_apps`
    treats that type as "this app is not installed, skip it", so an ImportError
    raised here would be SWALLOWED and the opt-out would vanish silently —
    exactly the failure this function exists to prevent.
    """
    try:
        from scitex_cards._django.services import ENV_LANE_GLOBS
    except ImportError as exc:  # pragma: no cover - upstream layout change
        raise RuntimeError(
            "scitex_cards is installed but "
            "scitex_cards._django.services.ENV_LANE_GLOBS could not be "
            "imported, so the hub cannot learn which env var disables "
            "per-project lane discovery. Without it the board unions every "
            "per-project lane on the host into every hub user's view. "
            "Find the new location of that constant and update "
            "cards_lane_globs_env() in config/settings/_optional_apps.py."
        ) from exc
    return ENV_LANE_GLOBS


#: OPERATOR-FACING name for the cards store, in the hub's own
#: ``SCITEX_HUB_<X>`` namespace (ADR-0001, ``config/_env.py``). Exactly the
#: shape ``SCITEX_HUB_CROSSREF_DB_PATH`` -> ``CROSSREF_DB_PATH`` already has
#: for the citation-graph service: the deployment states the value once, in
#: ``deployment/docker/envs/.env.<env>``, under the prefix every other hub
#: setting uses, and the hub hands it to the package under the name that
#: package reads. A hub deployment should not have to know a sibling's
#: private variable spelling to be configured.
CARDS_STORE_HUB_ENV = "SCITEX_HUB_CARDS_STORE"

#: The name scitex-cards ITSELF reads (``scitex_cards._db.ENV_DB``). The hub
#: does not get to choose it, which is exactly why the hub-prefixed name above
#: exists — and why this one is still honoured first below.
CARDS_STORE_UPSTREAM_ENV = "SCITEX_CARDS_DB"

#: The package name handed to ``scitex_dev.store.host_store`` for the fleet
#: default. It selects WHICH store on the fleet cluster, so it must stay
#: "cards" — the board scitex-cards reads — and not, say, "hub".
CARDS_STORE_PKG = "cards"

#: How a deployment names its environment. The SAME variable and the SAME
#: production spellings ``config/settings/__init__.py`` switches on, so the
#: two cannot disagree about which deployment is production.
HUB_ENV_VAR = "SCITEX_HUB_ENV"
PRODUCTION_ENV_NAMES = ("prod", "production")


def _is_production(env) -> bool:
    return str(env.get(HUB_ENV_VAR, "development")).lower() in PRODUCTION_ENV_NAMES


def publish_cards_store_target(environ: dict | None = None) -> str | None:
    """Hand scitex-cards the store target THIS DEPLOYMENT chose, or the fleet's.

    THE HUB NEVER CONFIGURED ONE AND THAT IS THE WHOLE DEFECT. The board's card
    DATA comes from the store ``scitex_cards`` resolves with no argument, and
    since the 2026-08-13 zero-config abolition that resolver REFUSES to invent a
    filename — it raises ``StoreTargetNotConfigured``. Measured on this branch
    against the real URLconf with a signed-in user: ``/apps/cards/graph`` 500s,
    which is what the operator saw as 「cards が読み込めていない。」 Nothing in
    ``config/``, ``deployment/`` or ``scripts/`` set ``$SCITEX_CARDS_DB`` or the
    ``store.target`` config key, on any environment, so every hub deployment was
    in that state.

    Precedence, and each tier is deliberate:

    1. ``$SCITEX_CARDS_DB`` already set -> LEFT ALONE. A developer or a test
       that exports the package's own variable has said something more specific
       than the deployment did, and a settings module that overwrites it would
       silently move them to a different store. Returned so the caller can log
       what won.
    2. ``$SCITEX_HUB_CARDS_STORE`` set -> published as ``$SCITEX_CARDS_DB``.
       This is the tier that fixes the defect: it gives a deployment a
       conventional place to state the target.
    3. NEITHER -> the FLEET DEFAULT, resolved by ``scitex_dev.store.host_store``
       and published as ``$SCITEX_CARDS_DB``. A hub that has been told nothing
       lands on the fleet's PostgreSQL on port 55432, which is where every other
       package in the ecosystem already keeps its store.

       EXCEPT IN PRODUCTION. Tier 3 is a development convenience: on a laptop
       or the dev preview, "the fleet's shared board" is what a developer
       wants to see. On scitex.ai it is an exposure: the board's middleware
       gates on ``is_authenticated`` only (apps/workspace/todo_app/
       middleware.py), so a production hub that fell through to tier 3 would
       hand the fleet's live task board — every agent's cards, DMs and
       operator notes — to any signed-in customer. That is the exact config
       change the parent card forbade (hub-cards-store-contract-and-multihost-
       20260730, comment c_1971278e38ee), and #705 introduced it by accident;
       measured 2026-09-03 on scitex-nas-03, only the container's inability to
       resolve ``scitex-primary`` stood between the two. So when
       ``$SCITEX_HUB_ENV`` names production — the same spellings
       ``config/settings/__init__.py`` switches on — tier 3 publishes NOTHING,
       logs why, and the board answers its typed 404 until a deployment states
       a store it owns through tier 2.

    WHY TIER 3 IS A DEFAULT HERE AND A HARD FAILURE FOR ``DATABASES``.
    These two look contradictory in the same settings package and they are not,
    so the difference is written down rather than left to be re-derived.

    ``DATABASES`` (settings_prod.py) refuses to start without a password: hub's
    OWN relational data lives in a database only this deployment knows, there is
    no correct guess, and every candidate default is a different empty database
    that would accept writes and reach nobody.

    The CARDS STORE is the opposite shape. It is not hub's data — it is the
    fleet's shared board, and the fleet has exactly ONE right answer for where
    it lives. Requiring an env var to reach the normal path made the CORRECT
    configuration the exceptional one: measured 2026-08-30, neither variable was
    set in any hub deployment, so the resolver raised ``StoreTargetNotConfigured``
    and ``/apps/cards/graph`` served HTTP 500 — the operator's
    「cards が読み込めていない。」 Configuration should exist to OVERRIDE a
    default, never to enable one.

    THIS IS NOT THE FALLBACK UPSTREAM ABOLISHED, and the distinction is the
    whole reason it is safe. What was abolished was *inventing a local
    filename nobody chose* — a private file, per-process, silently divergent
    (ADR-0004). What tier 3 does instead is ASK THE PRIMITIVE: ``host_store``
    is the fleet's single source of truth for DSN resolution
    (``scitex_dev/store/_host.py:288``), it honours ``$SCITEX_STORE_DSN``
    first, it has no file-backed tier of its own,
    and it calls ``require_durable_pgdata`` so a host whose PostgreSQL is not
    durable RAISES here rather than being quietly written to. No DSN is spelled
    out in this file; hardcoding ``…:55432/…`` locally is exactly the thing
    still refused, because it would drift from the primitive the moment the
    fleet moved.

    IF ``host_store`` CANNOT RESOLVE, NOTHING IS PUBLISHED — and nothing is
    invented in its place. This is the one case that returns ``None``.

    It is NOT a fallback: no second store is chosen, no write goes anywhere
    unintended, and the state is reported twice over — an ERROR in the log
    naming the resolver's own sentence, and the existing typed 404 from
    ``apps.workspace.todo_app.cards_store_provisioning`` on the board's data
    endpoints. What it deliberately does NOT do is abort settings import.
    ``publish_cards_store_target`` runs at settings load, so an exception here
    takes down the whole site — landing page, auth, every unrelated app —
    because one leaf's database is unreachable. That is the failure PR #689
    ruled against by name ("a broken leaf must not take down every URL hub
    serves"), and trading a 404 on /apps/cards/* for a total outage is not a
    trade this makes. The cards board degrades; the hub stays up and says why.

    An EMPTY value counts as unset at every tier, matching the resolver's own
    ``if value:`` test; otherwise ``SCITEX_HUB_CARDS_STORE=`` in a ``.env`` file
    would publish an empty ``$SCITEX_CARDS_DB`` and mean something different
    here than it does one call downstream.

    :param environ: mapping to read and write; defaults to ``os.environ``.
        Present so a test can prove the precedence without mutating the
        process, not as a general seam.
    :returns: the target now in effect. ``None`` ONLY when nobody configured
        one AND the fleet default could not be resolved — never as the normal
        answer to "nothing was configured", which is what it used to mean.
    """
    env = os.environ if environ is None else environ

    already = env.get(CARDS_STORE_UPSTREAM_ENV)
    if already:
        return already

    chosen = env.get(CARDS_STORE_HUB_ENV)
    if chosen:
        env[CARDS_STORE_UPSTREAM_ENV] = chosen
        return chosen

    if _is_production(env):
        logger.error(
            "[cards-store] no store configured (%s / %s unset) and this is "
            "PRODUCTION (%s=%s): the fleet default is NOT applied here, because "
            "scitex.ai must not serve the fleet's task board to every signed-in "
            "user. The board's data endpoints will answer 404 naming %s; set it "
            "to a store this deployment owns. The rest of the site is unaffected.",
            CARDS_STORE_HUB_ENV,
            CARDS_STORE_UPSTREAM_ENV,
            HUB_ENV_VAR,
            env.get(HUB_ENV_VAR),
            CARDS_STORE_HUB_ENV,
        )
        return None

    # Imported here, not at module scope: this module is imported during
    # settings load and `scitex_dev.store` is only needed on the tier that
    # actually reaches it.
    from scitex_dev.store import host_store

    try:
        fleet_default = host_store(pkg=CARDS_STORE_PKG).dsn
    except Exception as exc:  # noqa: BLE001 - see the docstring
        # BROAD ON PURPOSE. The set of ways a store target fails to resolve is
        # the PRIMITIVE's to define and it has grown before (StoreTargetError,
        # the durability refusal, a psycopg import failure). Naming a subset
        # here would let the unnamed ones abort settings import and take the
        # whole site down -- the exact outcome this except exists to prevent.
        logger.error(
            "[cards-store] no store configured (%s / %s unset) and the fleet "
            "default could not be resolved via scitex_dev.store.host_store: "
            "%s. The board's data endpoints will answer 404 naming %s; the "
            "rest of the site is unaffected.",
            CARDS_STORE_HUB_ENV,
            CARDS_STORE_UPSTREAM_ENV,
            exc,
            CARDS_STORE_HUB_ENV,
        )
        return None

    env[CARDS_STORE_UPSTREAM_ENV] = fleet_default
    return fleet_default


def _installed(module_path: str) -> ModuleType | None:
    """Import ``module_path``, or None when the package is not installed.

    Gates on the SUBMODULE the AppConfig lives in, not just the distribution:
    a package installed WITHOUT its ``_django`` app (an older wheel, or a
    checkout from before that app merged) must skip cleanly here rather than
    crash Django app-loading with ``ModuleNotFoundError``.
    """
    try:
        return import_module(module_path)
    except ImportError:
        return None


def optional_upstream_apps() -> list[str]:
    """Return ``INSTALLED_APPS`` entries for whichever upstream apps are present.

    Order is stable and matches the historical ``settings_shared`` sequence, so
    app-loading order does not change with this extraction.

    NOTE — one deliberate side effect, kept HERE rather than in the caller
    because separating it from the mount is how it would get lost: mounting the
    cards board also disables its host-side lane discovery. The board's service
    layer unions per-project lanes (default glob
    ``~/proj/*/.scitex/todo/tasks.yaml``) into every load; on the hub each
    request must see ONLY the requesting user's workspace store (injected by
    ``apps.workspace.todo_app.middleware``), so an empty glob list — the
    documented opt-out seam in that module — is set alongside the mount.

    SECOND SIDE EFFECT, SAME REASON: mounting the board also publishes the
    deployment's chosen card store (:func:`publish_cards_store_target`). It
    belongs next to the mount because a mounted board with no store is the
    defect this fixes — the two are one decision, and splitting them is how
    the second half gets forgotten on the next environment.
    """
    entries: list[str] = []

    if _installed("figrecipe"):
        entries.append("figrecipe._django")

    if _installed("scitex_writer"):
        entries.append("scitex_writer._django.apps.WriterEditorConfig")

    if _installed("scitex_storage._django"):
        entries.append("scitex_storage._django.apps.StorageConfig")

    # scitex-scholar's Django app. Its VIEWS were already mounted at
    # /apps/scholar/v2/ (apps/workspace/scholar_app/urls/scholar_django.py)
    # without the APP being installed, and a mounted view whose app is not in
    # INSTALLED_APPS cannot find its own templates: app_directories.Loader
    # walks INSTALLED_APPS and nothing else. Measured on production 2026-09-05
    # after the rebuild — scitex_scholar/_django/templates/scholar/scholar.html
    # was on disk in the installed 1.10.0 wheel, and every visitor request to
    # /apps/scholar/v2/ answered 500 with TemplateDoesNotExist('scholar/
    # scholar.html'); anonymous requests never reached the view (login
    # redirect), which is why curl looked healthy. The leaf's label is
    # "scholar_editor", chosen upstream precisely not to collide with hub's own
    # apps.workspace.scholar_app. Its AppConfig imports scitex_app hard; hub
    # floors scitex-app, so a missing scitex_app is a broken install and must
    # fail at startup rather than be papered over here.
    if _installed("scitex_scholar._django"):
        entries.append("scitex_scholar._django.apps.ScholarEditorConfig")

    # CANONICAL name. `scitex_todo` is a deprecated alias of this package
    # (renamed 2026-07-16) that warns it "ships for one transition window
    # only" — importing the alias would make the whole board mount depend on a
    # module upstream has announced it will delete, and the failure is SILENT.
    cards_apps = _installed("scitex_cards._django.apps")
    if cards_apps is not None:
        entries.append(cards_appconfig_path(cards_apps))
        # Opt the board out of host-side per-project lane discovery: the union
        # would leak host lanes to every hub user.
        #
        # THE NAME IS IMPORTED, NOT WRITTEN. This line set
        # "SCITEX_TODO_LANE_GLOBS" — the pre-rename name — for as long as the
        # guard has existed, and scitex_cards has only ever read
        # SCITEX_CARDS_LANE_GLOBS, so the opt-out did nothing. Nothing anywhere
        # consumes the old name (checked across the installed tree), so the
        # export was inert while looking deliberate, and the test that guarded
        # it asserted the same wrong literal and passed.
        #
        # Unset and empty are OPPOSITE here, which is why the miss mattered:
        # _discover_lanes() falls back to DEFAULT_LANE_GLOBS
        # ("~/proj/*/.scitex/cards/tasks.yaml") when the variable is absent,
        # and treats an explicitly-empty value as the documented opt-out.
        #
        # Latent rather than live today: both the prod and dev django
        # containers run with HOME=/root, so the fallback glob
        # /root/proj/*/.scitex/cards/tasks.yaml matched 0 files when measured
        # 2026-09-07. It becomes real the moment HOME changes or a home
        # carrying project lanes is mounted.
        os.environ[cards_lane_globs_env()] = ""
        publish_cards_store_target()

    return entries


# EOF
