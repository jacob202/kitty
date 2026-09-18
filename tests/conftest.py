import atexit
import itertools
import os
import shutil
import site
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_TEST_DATA_ROOT = Path(tempfile.mkdtemp(prefix="kitty-pytest-data-"))
os.environ["KITTY_ENV"] = "test"
os.environ["KITTY_TEST_GUARD"] = "1"
os.environ["KITTY_DATA_ROOT"] = str(_TEST_DATA_ROOT)
os.environ.pop("KITTY_BUILDER_DATA_DIR", None)
os.environ["GATEWAY_SECRET"] = ""
os.environ["KITTY_IMAGE_PAID_ENABLED"] = "0"
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

# Make the checkout's sitecustomize importable by every Python child process.
_existing_pythonpath = os.environ.get("PYTHONPATH", "")
_startup = ROOT / "tests" / "python_startup"
_existing_pythonpath_parts = [
    part for part in _existing_pythonpath.split(os.pathsep) if part
]
_child_pythonpath = [
    str(_startup),
    str(ROOT),
    *site.getsitepackages(),
    *_existing_pythonpath_parts,
]
os.environ["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(_child_pythonpath))

_PAID_PROVIDER_KEYS = (
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY",
    "GEMINI_API_KEY", "GOOGLE_API_KEY", "NVIDIA_API_KEY", "BFL_API_KEY",
    "RUNWARE_API_KEY", "FAL_KEY", "AIRFORCE_API_KEY", "RUNPOD_API_KEY",
    "REPLICATE_API_TOKEN", "MEM0_API_KEY", "LLAMA_CLOUD_API_KEY",
    "TAVILY_API_KEY",
)
for _key in _PAID_PROVIDER_KEYS:
    os.environ.pop(_key, None)

# Credentials are not the only ambient state that leaks. A developer shell that exports
# provider *configuration* also changes routing and readiness decisions, so assertions
# about which model a role resolves to pass in CI and fail locally. That made the local
# pre-push gate permanently red on a correctly configured machine, which trains everyone
# to bypass it with --no-verify and leaves no cheap check ahead of CI. Scrub configuration
# alongside credentials so the suite depends only on what a test sets for itself.
_AMBIENT_PROVIDER_CONFIG_KEYS = (
    "KITTY_OPENROUTER_DIRECT_MODEL",
    "AIRFORCE_MODEL",
    "FAL_MODEL",
    "KITTY_IMAGE_AIRFORCE_ENABLED",
    "KITTY_IMAGE_FAL_ENABLED",
    "KITTY_IMAGE_FLUX_ENABLED",
    "KITTY_IMAGE_FLUX2_ENABLED",
)
for _key in _AMBIENT_PROVIDER_CONFIG_KEYS:
    os.environ.pop(_key, None)

import kitty_test_guard as _test_guard  # noqa: E402

_test_guard.install_test_guards()
atexit.register(shutil.rmtree, _TEST_DATA_ROOT, True)


@pytest.fixture(autouse=True)
def enforce_controlled_live_contract(request, monkeypatch):
    marker = request.node.get_closest_marker("controlled_live")
    if marker is None:
        monkeypatch.delenv("KITTY_TEST_CONTROLLED_LIVE_ACTIVE", raising=False)
        for key in (*_PAID_PROVIDER_KEYS, *_AMBIENT_PROVIDER_CONFIG_KEYS):
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("KITTY_IMAGE_PAID_ENABLED", "0")
        return

    if os.environ.get("KITTY_TEST_ALLOW_LIVE") != "1":
        pytest.skip("controlled_live requires KITTY_TEST_ALLOW_LIVE=1")
    if os.environ.get("KITTY_TEST_CHARGE_OK") != "1":
        pytest.skip("controlled_live requires KITTY_TEST_CHARGE_OK=1")
    max_requests = int(os.environ.get("KITTY_TEST_LIVE_MAX_REQUESTS", "0"))
    max_cost = float(os.environ.get("KITTY_TEST_MAX_COST_USD", "0"))
    if max_requests < 1 or max_requests > 1:
        pytest.fail("controlled_live requires KITTY_TEST_LIVE_MAX_REQUESTS=1")
    if max_cost <= 0 or max_cost > 0.10:
        pytest.fail("controlled_live requires 0 < KITTY_TEST_MAX_COST_USD <= 0.10")
    monkeypatch.setenv("KITTY_TEST_CONTROLLED_LIVE_ACTIVE", "1")
    _test_guard.reset_live_counter()


@pytest.fixture(autouse=True)
def isolate_gateway_auth_env(monkeypatch):
    """Keep real local .env secrets from leaking into TestClient tests."""
    monkeypatch.setenv("KITTY_ENV", "test")
    monkeypatch.setenv("GATEWAY_SECRET", "")


@pytest.fixture(scope="session", autouse=True)
def _migrated_store_templates(tmp_path_factory):
    """Apply each migration chain once per worker; seed fresh stores by copy.

    Nearly every module-level database fixture in this suite builds its store by
    calling `gateway.db.migrate()` against a fresh file: `_fresh_db`,
    `override_db`, `room_db`, `workspace_db`, `automation_db`, `_tmp_db` and
    friends. That is pure schema work with a fixed input — the same SQL files,
    the same resulting schema — yet it was the single largest setup cost in the
    run (~26 ms per store on an idle machine and several times that under eight
    workers, because SQLite DDL serialises and the filesystem is the bottleneck).

    So run the real chain once per worker into a template, then satisfy later
    requests for a *fresh* store by copying that template. The copy is the exact
    bytes the chain produces, including the `schema_migrations` ledger, so
    schema/code divergence still fails tests exactly as before (the reason
    `override_db` insists on real migrations).

    Nothing about store ownership changes: each caller still receives its own
    file, so no test can observe another test's rows. Anything that is not a
    fresh store still goes through the real implementation — an existing file,
    an unknown or changed migrations directory, a missing directory — and the
    returned list of applied migrations is the one the real chain produced.
    """
    import shutil
    import sqlite3
    from pathlib import Path

    import gateway.db as kitty_db

    real_migrate = kitty_db.migrate
    templates: dict[object, tuple[Path, list[str]]] = {}
    root = tmp_path_factory.mktemp("migrated-store-templates")

    def _fingerprint(migration_path: Path) -> tuple:
        # Include the directory's contents so a test that adds, edits or removes
        # a migration file never reuses a stale template.
        return (
            str(migration_path),
            tuple(
                sorted(
                    (path.name, path.stat().st_size, path.stat().st_mtime_ns)
                    for path in migration_path.glob("*.sql")
                )
            ),
        )

    def migrate(db_file=kitty_db.KITTY_DB_FILE, migrations_dir=kitty_db.DB_MIGRATIONS_DIR):
        target = Path(db_file)
        migration_path = Path(migrations_dir)
        if not migration_path.exists():
            return real_migrate(db_file=target, migrations_dir=migration_path)
        if target.exists() and target.stat().st_size:
            # Not a fresh store: the real chain decides what is still pending.
            return real_migrate(db_file=target, migrations_dir=migration_path)
        key = _fingerprint(migration_path)
        entry = templates.get(key)
        if entry is None:
            template = root / f"template-{len(templates)}.db"
            try:
                applied = real_migrate(db_file=template, migrations_dir=migration_path)
            except Exception:
                # A chain that cannot run must fail the caller with its own
                # database named in the message, exactly as before.
                return real_migrate(db_file=target, migrations_dir=migration_path)
            # Fold the chain into the main file so a single-file copy carries it.
            connection = sqlite3.connect(template, isolation_level=None)
            try:
                connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            finally:
                connection.close()
            entry = templates[key] = (template, list(applied))
        target.parent.mkdir(parents=True, exist_ok=True)
        # A copy must be as fresh as a new file: a test that deletes its store
        # leaves the -wal/-shm behind, and writing a new main file beside them
        # lets SQLite replay the dead journal and resurrect deleted rows. The
        # real path never sees this because opening a missing file starts over.
        for suffix in ("-wal", "-shm", "-journal"):
            stale = target.with_name(target.name + suffix)
            if stale.exists():
                stale.unlink()
        shutil.copyfile(entry[0], target)
        return list(entry[1])

    with pytest.MonkeyPatch.context() as patched:
        patched.setattr(kitty_db, "migrate", migrate)
        yield


@pytest.fixture(autouse=True)
def isolated_governor_db(tmp_path, monkeypatch):
    """Never let a test write compute-governor receipts into the real store.

    The Builder CLI governs by default, and the allowance is keyed on
    initiative/packet/base SHA — identifiers the Builder tests reuse. Without
    this, the second governed CLI test in a run is correctly refused as a
    duplicate, and a test run would leave receipts in data/compute_governor/.
    """
    monkeypatch.setenv(
        "KITTY_COMPUTE_GOVERNOR_DB", str(tmp_path / "governor" / "receipts.db")
    )


_STORE_SEQUENCE = itertools.count()


@pytest.fixture(scope="session")
def _autonomy_state_template(tmp_path_factory):
    """One schema-only autonomy store per worker, copied once per test.

    Building the store from scratch per test costs a directory, two CREATE
    TABLE statements and a WAL handshake; under eight-way load that measured
    ~4.3 ms of wall per test and was almost entirely SQLite/IO contention. A
    prepared file copied per test does the same job in one filesystem call
    while keeping the per-test property the isolation depends on.
    """
    import gateway.autonomy_state as autonomy_state
    from gateway.db import connect as db_connect

    template = tmp_path_factory.mktemp("autonomy-template") / "template.db"
    previous = autonomy_state.STATE_DB
    autonomy_state.STATE_DB = template
    try:
        autonomy_state.init_db()
    finally:
        autonomy_state.STATE_DB = previous
    # Fold the schema back into the main file so a single-file copy carries it.
    with db_connect(template) as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    return template


@pytest.fixture(autouse=True)
def isolated_autonomy_state_db(_autonomy_state_template, monkeypatch):
    """Give every test its own autonomy session store, schema included.

    `agent_runner._run_agent_loop` returns before its first model call unless
    autonomy_state.STATE_DB reports that session as active, so any test that
    drives the loop depends on a persisted session row. One store per process
    made that row a leftover from whichever test ran earlier: the assertions
    held in a serial run and failed in a fresh process, or in whichever
    parallel worker did not happen to run the test that created it. Tests that
    need a session must persist one themselves.

    A gateway process initializes the store before the first session exists, so
    the fresh store carries the schema rather than being absent — several
    callers (`start_new`) read the table without creating it. Each test still
    gets a file of its own: nothing a test writes is visible to any other.

    The store lives outside `tmp_path`: tests that assert their own directory
    holds nothing but what they wrote must not see this file either.
    """
    import shutil

    import gateway.autonomy_state as autonomy_state

    destination = (
        _autonomy_state_template.parent / f"autonomy-{next(_STORE_SEQUENCE)}.db"
    )
    shutil.copyfile(_autonomy_state_template, destination)
    monkeypatch.setattr(autonomy_state, "STATE_DB", destination)


@pytest.fixture(autouse=True)
def isolate_provider_prefs(tmp_path, monkeypatch):
    """Keep the saved provider order out of tests — and tests out of it.

    resolve_order() reads config/providers.json, so without this a local
    preference would silently reorder the fallback chain under the suite.
    """
    import gateway.provider_prefs as provider_prefs

    monkeypatch.setattr(provider_prefs, "PROVIDER_PREFS_FILE", tmp_path / "providers.json")


@pytest.fixture
def all_provider_keys(monkeypatch):
    """Give every cloud provider a key so ordering is what's under test.

    The chain now skips unkeyed providers outright, so a test that means to
    exercise fallback *order* has to opt in to being configured.
    """
    for name in (
        "OPENAI_API_KEY",
        "NVIDIA_API_KEY",
        "AGENTROUTER_API_KEY",
        "OPENROUTER_API_KEY",
        "GEMINI_API_KEY",
    ):
        monkeypatch.setenv(name, "sk-test-key")


@pytest.fixture
def hermetic_builder_base(monkeypatch):
    """Pin Builder's base-SHA resolution so unit tests never reach origin.

    apply_manifest() resolves a base SHA by fetching the remote whenever one
    exists, so every manifest applied by an un-pinned test pays a live
    `git fetch origin main` (30s timeout, network-dependent). Tests that do
    not exercise resolution opt in to a fixed SHA instead.
    """
    from gateway import builder_initiative

    monkeypatch.setattr(
        builder_initiative, "resolve_base_sha", lambda _repo_root=None: "a" * 40
    )
