# Turso Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Turso the source of truth for clouds, profiles, watchlist and submissions. The Astro site reads it at runtime (SSR), and `README.md`/`WATCHLIST.md` are regenerated from it.

**Architecture:** A Python data layer (`scripts/lib/db.py` + `*_repo.py`) is shared by an importer, the GitHub Actions pipeline and two renderers that write README/WATCHLIST back to the repo. A TS data layer (`src/lib/data/*`) with a 60 s cache feeds SSR pages and JSON/txt endpoints. The site is served by Bun + `@astrojs/node` (middleware mode) on Datum Compute.

**Tech Stack:** Turso/libSQL (Hrana HTTP API from Python via `requests`; `@libsql/client` in TS), Astro 7 + `@astrojs/node`, Bun, pytest, vitest, PyYAML, `marked`.

**Spec:** `docs/superpowers/specs/2026-11-25-turso-migration-design.md`

## Global Constraints

- Env vars: `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`, `DATA_ENV` (`production` | `preview` | `local`/unset), `TURSO_ORG`. Actions secrets: `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN_RW`, `TURSO_API_TOKEN` (platform token, preview DB create/destroy). A `file:` URL means local SQLite (dev/tests), with no token.
- DB names: prod `alt-clouds`. Each preview gets its own read-write DB `alt-clouds-pv-<slug>`, where `<slug>` is the preview slug from `preview.sh names`. It is copied from prod (`--from-db`) on the first deploy and destroyed with the preview.
- Env/DB guard (spec "No cross-wiring") is enforced in both `connect()` (Python) and `getDb()` (TS).
- Migrations live in `db/migrations/NNNN_<name>.sql` and are applied in filename order. `0001_init.sql` is the spec's schema verbatim.
- One category per cloud. It must be one of `scripts/lib/taxonomy.py:CATEGORIES`. Tags must pass `lib.entry_format.invalid_tags()`.
- Slug = `scripts/lib/slugify.py:slugify(name)`, identical to `src/lib/clouds.ts:slugify`. A slug may not be in `RESERVED_SLUGS`.
- Fail-open stays for pipeline scripts: on a DB error, log a warning, write a safe default, exit 0. The exceptions are `approve_submission.py` / graduation approval, which must exit non-zero on a failed write (a silent approval loss is worse than a red run).
- README entry format and ordering are unchanged (`format_entry()`, alphabetical case-insensitive within each `## Category`).
- Bot commits use the GitHub App token, with the message `data: <action> <name> (#<issue>)` or `data: sync from Turso`.
- Never write to prod from tests. Tests use `file:` DBs in `tmp_path`.

## Review Focus

1. **Round-trip fidelity:** import the current README, then render it, and the result must be byte-identical (emoji badges, tag comments, prose between sections, trailing newline). → Task 6 golden test.
2. **Turso unavailable at request time:** the site must keep serving the last good data instead of a 500. → Task 9 test `serves stale cache when query fails`.
3. **A duplicate or invalid submission reaching `/approve`:** same URL, a slug that collides or is reserved, an unknown tag. Expect a clear issue comment and a non-zero exit, with no partial rows. → Task 7 tests `test_approve_rejects_duplicate_url`, `test_approve_is_atomic`.
4. **Profile skip-if-exists:** a re-run of the profile generator must never overwrite a `reviewed` profile. → Task 3 test `test_upsert_profile_does_not_overwrite_by_default`.
5. **Multi-category / legacy-category rows on import** (Pingcap): the import aborts and names the entry. → Task 5 test `test_import_rejects_multi_category`.
6. **A preview wired to the prod DB, or prod wired to a preview DB** (copy-pasted env, a wrong secret): the connection is refused at startup, so a preview never writes to prod. → Task 1 test `test_connect_refuses_env_db_mismatch`, Task 9 test `getDb refuses env/db mismatch`.

---

### Task 1: DB client + migration runner (Python)

**Files:**
- Create: `scripts/lib/db.py`, `scripts/db_migrate.py`, `db/migrations/0001_init.sql`, `.env.example`
- Modify: `.gitignore` (add `local.db*`, `.env`)
- Test: `tests/test_db.py`

**Interfaces:**
- Produces:
  - `class Db(Protocol)`: `execute(sql: str, params: Sequence | Mapping = ()) -> list[dict]`, `batch(stmts: list[tuple[str, Sequence]]) -> None` (atomic, all or nothing).
  - `assert_db_matches_env(url: str, data_env: str | None, org: str | None) -> None` raises `DbError` per the spec's "No cross-wiring" rules. `connect()` calls it first.
  - `connect(url: str | None = None, token: str | None = None) -> Db`. It defaults to the env vars. `file:`/bare path → `SqliteDb` (stdlib, `PRAGMA foreign_keys=ON`, rows as dict). `libsql://` is rewritten to `https://`, and http(s) → `HttpDb` (POST `{url}/v2/pipeline`, Hrana `execute` requests; `batch` = Hrana `batch` wrapped in BEGIN/COMMIT with each step conditioned on the previous step being ok, ROLLBACK on failure). It raises `DbError(message)` on any SQL/HTTP error.
  - `apply_migrations(db: Db, migrations_dir: Path = Path("db/migrations")) -> list[str]`, which returns the versions applied now.

- [ ] **Step 1: Write failing tests** in `tests/test_db.py`:
  - `test_connect_file_executes_and_returns_dicts`: `db = connect(f"file:{tmp_path}/t.db")`; `db.execute("select 1 as x") == [{"x": 1}]`.
  - `test_batch_is_atomic`: create a table with a UNIQUE column; `batch([insert a, insert a])` raises `DbError`; `select count(*)` == 0.
  - `test_apply_migrations_idempotent`: first call returns `["0001_init"]`, second returns `[]`; tables `clouds, cloud_tags, profiles, profile_updates, watchlist, submissions` exist.
  - `test_connect_refuses_env_db_mismatch` (parametrized, org `datum`):
    - `production` + `libsql://alt-clouds-pv-x-datum.turso.io` → `DbError`
    - `preview` + `libsql://alt-clouds-datum.turso.io` → `DbError`
    - `production` + `file:x.db` → `DbError`
    - `preview` + `libsql://alt-clouds-pv-x-datum.turso.io` → ok
    - `production` + `libsql://alt-clouds-datum.turso.io` → ok
  - `test_http_db_encodes_hrana_args` (monkeypatch `requests.post`): `execute("select ?", [5, "a", None])` posts args `[{"type":"integer","value":"5"},{"type":"text","value":"a"},{"type":"null"}]` with header `Authorization: Bearer <token>`, and decodes the response rows to dicts.
- [ ] **Step 2: Run** `pytest tests/test_db.py -v`. Expected: FAIL (ImportError).
- [ ] **Step 3: Implement** `db.py`, `db_migrate.py` (CLI: `python scripts/db_migrate.py`, prints the applied versions) and `0001_init.sql` (the spec schema). `.env.example` lists the three env vars with `TURSO_DATABASE_URL=file:./local.db`.
- [ ] **Step 4: Run** `pytest tests/test_db.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(db): add libSQL client and migration runner`.

### Task 2: Clouds repository

**Files:**
- Create: `scripts/lib/clouds_repo.py`
- Modify: `scripts/lib/slugify.py` (add `RESERVED_SLUGS`, copied from `src/lib/clouds.ts`), `tests/test_taxonomy_sync.py` (assert both `RESERVED_SLUGS` sets are equal)
- Test: `tests/test_clouds_repo.py`

**Interfaces:**
- Consumes: `connect`, `apply_migrations` (Task 1).
- Produces:
  - `@dataclass CloudRow(name: str, url: str, description: str, score: int, category: str, unverified: bool = False, tags: tuple[str, ...] = (), date_added: str | None = None, id: int | None = None, slug: str | None = None)`
  - `list_clouds(db) -> list[CloudRow]`, ordered by taxonomy category order, then `lower(name)`, with tags in `position` order.
  - `get_cloud(db, *, url=None, slug=None, name=None) -> CloudRow | None` (exactly one kwarg; name match is case-insensitive).
  - `insert_cloud(db, row: CloudRow) -> int`. It validates the category, tags, slug (non-empty, not reserved, unique) and score ∈ {2,3}, then raises `ValueError(<reason>)`. Cloud + tags go in one `batch`.
  - `update_cloud(db, row: CloudRow) -> None` (by `row.id`; replaces tags; bumps `updated_at`).
  - `delete_cloud(db, cloud_id: int) -> None`.
  - `to_entry(row) -> lib.entry_format.Entry` and `from_entry(entry, category, date_added) -> CloudRow`.

- [ ] **Step 1: Write failing tests**: `test_insert_and_get_roundtrip` (tags keep order), `test_insert_rejects_reserved_slug` (name `"Compare"` → ValueError mentioning `compare`), `test_insert_rejects_unknown_category`, `test_insert_rejects_invalid_tag`, `test_insert_rejects_duplicate_url`, `test_list_orders_by_category_then_name_case_insensitive`, `test_update_replaces_tags`.
- [ ] **Step 2: Run** `pytest tests/test_clouds_repo.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `clouds_repo.py`.
- [ ] **Step 4: Run** `pytest tests/test_clouds_repo.py tests/test_taxonomy_sync.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(db): clouds repository`.

### Task 3: Profiles repository + `profile_admin.py`

**Files:**
- Create: `scripts/lib/profiles_repo.py`, `scripts/profile_admin.py`
- Modify: `requirements.txt` (add `pyyaml>=6.0`)
- Test: `tests/test_profiles_repo.py`

**Interfaces:**
- Consumes: `CloudRow`, `get_cloud` (Task 2).
- Produces:
  - `@dataclass ProfileRow(cloud_id: int, status: str = "draft", tagline=None, headquarters=None, founded_year: int | None = None, pricing_model=None, open_source: bool | None = None, logo=None, regions: list[str] = [], services: list[str] = [], socials: dict[str, str] = {}, body_md: str = "", updates: list[dict] = [])`. Each update dict has the keys `date, kind, title, body, url?`.
  - `get_profile(db, cloud_id) -> ProfileRow | None`
  - `upsert_profile(db, row, *, overwrite: bool = False) -> bool` returns False and writes nothing when a row exists and `overwrite` is False. Profile + `profile_updates` replace go in one batch.
  - `set_status(db, slug: str, status: Literal["draft","reviewed"]) -> None`
  - `parse_profile_md(text: str) -> tuple[dict, str]` (YAML frontmatter, body) and `format_profile_md(row: ProfileRow) -> str`, the inverse, in the same frontmatter key order as today's MDX (`status, tagline, headquarters, foundedYear, pricingModel, openSource, logo, regions, services, socials, updates`).
  - CLI: `profile_admin.py export <slug> [-o file]`, `profile_admin.py import <file> [--slug]`, `profile_admin.py set-status <slug> draft|reviewed`.

- [ ] **Step 1: Write failing tests**: `test_upsert_profile_does_not_overwrite_by_default` (insert reviewed; upsert draft without overwrite → returns False, status still `reviewed`), `test_upsert_overwrite_replaces_updates`, `test_set_status`, `test_profile_md_roundtrip` (for every file in `src/content/clouds/*.mdx`, `format_profile_md(row_from(parse_profile_md(text)))` re-parses to equal frontmatter + body).
- [ ] **Step 2: Run** `pytest tests/test_profiles_repo.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the repo + CLI.
- [ ] **Step 4: Run** `pytest tests/test_profiles_repo.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(db): profiles repository and profile_admin CLI`.

### Task 4: Watchlist + submissions repositories

**Files:**
- Create: `scripts/lib/watchlist_repo.py`, `scripts/lib/submissions_repo.py`
- Test: `tests/test_watchlist_repo.py`, `tests/test_submissions_repo.py`

**Interfaces:**
- Produces:
  - `@dataclass WatchlistRow(name, url, category, date_added, reason_not_qualifying, criteria_need, last_reviewed, id=None)`. Functions: `list_watchlist(db) -> list[WatchlistRow]` (insertion order = `id`), `upsert_watchlist(db, row) -> None` (keyed on url), `remove_watchlist(db, url) -> bool`.
  - `@dataclass SubmissionRow(issue_number: int, url: str, evaluated_at: str, name=None, score: int | None = None, criteria: dict = {}, category=None, tags: list[str] = [], decision="pending", report_md=None, decided_at=None, cloud_id=None, id=None)`. Functions: `record_evaluation(db, row) -> int` (upsert on `(issue_number, url)`; a re-evaluation overwrites score/criteria/report but keeps `decision` unless it is `pending`), `set_decision(db, issue_number, url, decision, *, cloud_id=None, decided_at: str) -> None`, `list_submissions(db, *, url=None) -> list[SubmissionRow]`.
  - `count_submissions_for_url(db, normalized_domain: str) -> int` (for the "submitted 2+ times" watchlist rule; domain normalization = `check_duplicates.normalize_domain`).

- [ ] **Step 1: Write failing tests**: `test_watchlist_upsert_keyed_on_url`, `test_watchlist_preserves_order`, `test_record_evaluation_reeval_keeps_decision`, `test_set_decision_links_cloud`, `test_count_submissions_for_url_normalizes_www_and_scheme`.
- [ ] **Step 2: Run** `pytest tests/test_watchlist_repo.py tests/test_submissions_repo.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Commit** `feat(db): watchlist and submissions repositories`.

### Task 5: One-shot importer

**Files:**
- Create: `scripts/import_to_turso.py`
- Test: `tests/test_import_to_turso.py`

**Interfaces:**
- Consumes: `parse_readme` + `_build_date_added_map` (`scripts/parse_readme_to_json.py`), `parse_watchlist` (`scripts/generate_watchlist_json.py`), `parse_evaluation` (`scripts/watchlist_add.py`), and all repos (Tasks 2–4).
- Produces:
  - `import_clouds(db, readme_path: Path) -> int`. It upserts by url, so a re-run is idempotent and updates changed rows. It raises `ValueError` listing every entry with `len(categories) != 1`.
  - `import_profiles(db, profiles_dir: Path) -> int` uses `upsert_profile(overwrite=True)`. It raises on an orphan slug (same rule as `loadProfiles()`).
  - `import_watchlist(db, path: Path) -> int`
  - `import_submissions(db, repo: str, token: str) -> int` reads all issues labelled `submission` via the GitHub REST API (paginated). For each URL it finds the latest bot evaluation comment → `record_evaluation`. Decision: `approved` if the URL is in `clouds`, `watchlisted` if in `watchlist`, `duplicate` if labelled `duplicate`, `rejected` if closed with `rejected`, else `pending`.
  - CLI: `python scripts/import_to_turso.py [--skip-submissions] [--dry-run]` (dry-run = import into `file::memory:` and print counts).

- [ ] **Step 1: Write failing tests** (fixtures under `tests/fixtures/turso/`): `test_import_rejects_multi_category`, `test_import_clouds_idempotent` (run twice → same count, no duplicates), `test_import_profiles_orphan_raises`, `test_import_watchlist_counts`, `test_import_submissions_maps_decisions` (monkeypatched GitHub responses).
- [ ] **Step 2: Run** `pytest tests/test_import_to_turso.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest tests/test_import_to_turso.py -v` and `python scripts/import_to_turso.py --dry-run --skip-submissions`. Expected: PASS. The dry-run prints `clouds=<README count> profiles=425 watchlist=<n>`, or fails naming Pingcap. If it fails, fix that README entry first in its own commit (`fix(readme): single category for Pingcap`).
- [ ] **Step 5: Commit** `feat(db): importer from README/MDX/WATCHLIST/issues`.

### Task 6: README + WATCHLIST renderers

**Files:**
- Create: `scripts/render_readme.py`, `scripts/render_watchlist.py`
- Test: `tests/test_render_readme.py`, `tests/test_render_watchlist.py`

**Interfaces:**
- Consumes: `list_clouds`, `to_entry`, `format_entry`, `list_watchlist`.
- Produces:
  - `render_readme(db, template: str) -> str`. Inside each `## <Category>` section that is in `CATEGORIES`, it replaces the contiguous block of entry bullets (`parse_entry(line) is not None`) with the DB's entries for that category, and keeps every other line as is. If a category has no bullets in the template, it inserts them after the section's prose.
  - `render_watchlist(db, template: str) -> str` replaces the table rows under the `| Name |` header row + separator.
  - CLI: `python scripts/render_readme.py [README.md]` and `python scripts/render_watchlist.py [WATCHLIST.md]` rewrite the file in place and print `changed` / `unchanged`.

- [ ] **Step 1: Write failing tests**: `test_readme_roundtrip_is_byte_identical` (import the repo's `README.md` into a tmp DB → `render_readme(db, original) == original`), `test_readme_new_entry_sorted_case_insensitive`, `test_readme_unverified_badge_and_tags`, `test_watchlist_roundtrip_is_byte_identical`.
- [ ] **Step 2: Run** `pytest tests/test_render_readme.py tests/test_render_watchlist.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** If the round-trip shows existing README drift (unsorted rows, stray whitespace), keep the renderer canonical. Fix the README in a separate commit (`chore(readme): canonical ordering`) so the golden test compares against the canonical file.
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Commit** `feat(db): render README and WATCHLIST from Turso`.

### Task 7: Submission pipeline writes to Turso

**Files:**
- Create: `scripts/approve_submission.py` (replaces the README/PR half of `create_submission_pr.py`)
- Modify: `scripts/check_duplicates.py` (load clouds via `list_clouds` instead of `public/clouds.json`, falling back to the JSON file on `DbError`, fail-open), `scripts/evaluate_submission.py` (call `record_evaluation` after scoring; fail-open), `scripts/generate_cloud_profile.py` (write via `upsert_profile(overwrite=False)` instead of an MDX file), `scripts/backfill_profiles.py` (same)
- Delete: `scripts/create_submission_pr.py`, `tests/test_create_submission_pr.py`
- Test: `tests/test_approve_submission.py`, update `tests/test_check_duplicates.py`, `tests/test_evaluate_submission.py`

**Interfaces:**
- Consumes: `insert_cloud`, `upsert_profile`, `set_decision`, `record_evaluation`.
- Produces: `approve(db, data: dict, *, issue_number: int, today: str) -> list[CloudRow]`. `data` is the existing `submission_data.json` shape. For each service it inserts the cloud (`date_added=today`), sets the decision `approved` with `cloud_id`, and generates a draft profile (profile failures are logged and don't block). On `ValueError`/`DbError` it raises `ApprovalError(service_name, reason)`. The CLI `python scripts/approve_submission.py` reads `submission_data.json` + env `ISSUE_NUMBER`, writes `approved_names=<comma list>` to `$GITHUB_OUTPUT`, and exits 1 on `ApprovalError` after writing `approval_error.md` for the workflow to comment.

- [ ] **Step 1: Write failing tests**: `test_approve_inserts_cloud_and_draft_profile`, `test_approve_rejects_duplicate_url` (raises `ApprovalError`, no new rows), `test_approve_is_atomic` (2 services, 2nd invalid → neither cloud row exists; validate all services before writing, then write in one batch), `test_check_duplicates_reads_db`, `test_check_duplicates_falls_back_to_json_on_db_error`, `test_evaluate_records_submission_fail_open` (DB raises → script still exits 0 and writes `evaluation_results.md`).
- [ ] **Step 2: Run** `pytest tests/test_approve_submission.py tests/test_check_duplicates.py tests/test_evaluate_submission.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** Because profiles are created in the same batch as the cloud, `generate_cloud_profile.py` exposes `build_profile(service) -> ProfileRow | None`, and `approve()` calls it before the batch.
- [ ] **Step 4: Run** `pytest tests/ -v`. Expected: all PASS.
- [ ] **Step 5: Commit** `feat(pipeline): approve submissions into Turso`.

### Task 8: Graduation, watchlist, audit writers + workflows

**Files:**
- Modify: `scripts/create_graduation_pr.py` → rename to `scripts/approve_graduation.py` (`update_cloud` with unverified=False, refreshed score/tags, target category), `scripts/evaluate_graduation.py` (locate entry via `get_cloud(name=…)`), `scripts/watchlist_add.py` (`upsert_watchlist` + `set_decision(..., "watchlisted")`), `scripts/audit_emerging_badges.py` (`update_cloud` score only)
- Modify workflows: `evaluate-submission.yml`, `admin-approve-submission.yml`, `approve-graduation.yml`, `watchlist.yml`, `backfill-profiles.yml`, `audit-emerging-badges.yml`. Add `env: TURSO_DATABASE_URL / TURSO_AUTH_TOKEN: ${{ secrets.TURSO_AUTH_TOKEN_RW }}`, replace the "create PR" steps with the new scripts, and on success send `repository_dispatch` `data-changed` with `client_payload: {message: "data: <action> <names> (#<issue>)"}`. The success comment links the regenerated README commit instead of a PR.
- **Human gate (do not auto-insert):** in `evaluate-submission.yml`, delete the "Create PR if score >= 2" step. A score ≥ 2 now adds the label `ready-to-approve` and comments "Comment `/approve` to publish". Only `admin-approve-submission.yml` (`/approve`) runs `approve_submission.py`. This keeps today's guarantee that a maintainer action is required before an entry goes live. (Issue-based intake is retired entirely in `2026-11-25-db-native-intake.md`.)
- Create: `.github/workflows/sync-readme.yml`. Triggers: `repository_dispatch: [data-changed]`, `workflow_dispatch`, `schedule: "17 3 * * *"`. It runs `render_readme.py` + `render_watchlist.py` and commits to `main` with the App token only if the files changed (message from the payload, default `data: sync from Turso`). `concurrency: sync-readme` (no cancel).
- Delete: `tests/test_create_graduation_pr.py` → replaced by `tests/test_approve_graduation.py`
- Test: `tests/test_approve_graduation.py`, update `tests/test_evaluate_graduation.py`, `tests/test_audit_emerging_badges.py`

**Interfaces:**
- Consumes: Tasks 2–4, 6.
- Produces: `approve_graduation(db, *, name: str, score: int, tags: list[str], category: str | None) -> CloudRow` (raises `ValueError` if the entry is missing or not unverified).

- [ ] **Step 1: Write failing tests**: `test_approve_graduation_clears_badge_and_moves_category`, `test_approve_graduation_missing_entry_raises`, `test_audit_updates_score_keeps_unverified`, `test_watchlist_add_writes_db`.
- [ ] **Step 2: Run** `pytest tests/test_approve_graduation.py tests/test_evaluate_graduation.py tests/test_audit_emerging_badges.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the scripts + workflow edits.
- [ ] **Step 4: Run** `pytest tests/ -v` and `actionlint .github/workflows/*.yml` (or `gh workflow view` for syntax). Expected: PASS / no errors.
- [ ] **Step 5: Commit** `feat(pipeline): graduation/watchlist/audit write to Turso; sync-readme workflow`.

### Task 9: TS data layer with cache

**Files:**
- Modify: `package.json` (deps `@libsql/client`, `marked`; devDeps `vitest`; script `"test": "vitest run"`), `src/lib/clouds.ts` (drop the `clouds.json` import; keep the pure helpers but make them take the list: `getCategories(clouds)`, `countByCategory(clouds, category)`, `getTagCounts(clouds)`, `newestClouds(clouds, limit)`; export `RESERVED_SLUGS`), `src/lib/watchlist.ts`
- Create: `src/lib/db.ts`, `src/lib/data/cache.ts`, `src/lib/data/clouds.ts`, `src/lib/data/watchlist.ts`, `src/lib/data/test-db.ts` (test helper that applies `db/migrations/*.sql` to a `file:` DB)
- Test: `src/lib/data/clouds.test.ts`, `src/lib/data/cache.test.ts`

**Interfaces:**
- Produces:
  - `getDb(): Promise<Client>` (singleton). http(s)/libsql URLs → `@libsql/client/web`; `file:` → dynamic `import("@libsql/client")`. It throws if `TURSO_DATABASE_URL` is unset. Env is read via `process.env` at runtime, never inlined by Vite. Before connecting it calls `assertDbMatchesEnv(url, process.env.DATA_ENV, process.env.TURSO_ORG)`, which has the same rules as the Python version.
  - `cached<T>(key: string, ttlMs: number, load: () => Promise<T>): Promise<T>` returns a fresh value within the TTL. After the TTL it reloads. If the reload throws and a stale value exists, it returns the stale value and `console.error`s. With no stale value it rethrows.
  - `CACHE_TTL_MS = 60_000`
  - `getClouds(): Promise<CloudWithSlug[]>` has the same `Cloud` shape as today (`categories: [category]`, `tags`, `unverified`, `dateAdded`) so components don't change. `getCloudBySlug(slug): Promise<CloudWithSlug | undefined>`.
  - `getWatchlist(): Promise<WatchlistEntry[]>` (same interface as today).

- [ ] **Step 1: Write failing tests**: `getDb refuses env/db mismatch` (same cases as the Python `test_connect_refuses_env_db_mismatch`), `getClouds maps rows to Cloud shape` (seed 2 clouds + tags; assert `categories`, tag order, `unverified` only when true, `dateAdded`), `serves stale cache when query fails` (prime the cache, advance fake timers past the TTL, make the loader throw → the old value is returned), `rethrows when no cached value`.
- [ ] **Step 2: Run** `npm test`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `npm test`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(site): Turso data layer with stale-on-error cache`.

### Task 10: Switch to SSR and move pages onto the data layer

**Files:**
- Modify: `astro.config.mjs` (`output: "server"`, `adapter: node({ mode: "middleware" })`; remove `sitemap()` integration), `package.json` (add `@astrojs/node`; drop `postbuild` if `rewrite_dist_relative_paths.py` is only needed for Pages subpath hosting; check preview-datum first), every consumer of `clouds`/`watchlist`/`profile` (`rg -l 'lib/(clouds|watchlist|profile)' src`: `index.astro`, `list/index.astro`, `compare.astro`, `categories/[slug].astro`, `watchlist/index.astro`, `[slug].astro`, `CloudDetail.astro`, `DetailSidebar.astro`, `lib/list-items.ts`, `lib/sitemap-chunks.ts`, `lib/categories.ts`, …). Pages call `await getClouds()` in frontmatter and pass the list to helpers.
- Modify: `src/lib/profile.ts` → reads from `profiles` via new `src/lib/data/profiles.ts`. `CloudProfile = { id: string /* slug */, data: <same fields as the old collection schema>, bodyHtml: string }`. `getPublishableProfiles()` / `isProfilePublished()` keep the same semantics (`sitePreview` gate). `bodyHtml = marked.parse(body_md)`.
- Modify: `src/pages/[slug].astro`: no `getStaticPaths`; `getCloudBySlug` + `getProfile`; return 404 when the cloud is missing or the profile is not publishable; render `<Fragment set:html={profile.bodyHtml} />` inside `.prose-content`.
- Modify: `src/content.config.ts` (remove the `clouds` collection). Blog pages, `definitions/`, `extension/`, `submit/`, `404`, `rss.xml.ts`: `export const prerender = true`.
- Modify: `categories/[slug].astro`: SSR with an unknown slug → 404 (keep `legacy-redirects`).
- Test: `src/lib/data/profiles.test.ts`

**Interfaces:**
- Consumes: Task 9.
- Produces: `getProfile(slug): Promise<CloudProfile | undefined>`, `getPublishableProfiles(): Promise<CloudProfile[]>`, `getFeaturedSlugs(): Promise<Set<string>>`.

- [ ] **Step 1: Write failing tests** in `profiles.test.ts`: `draft profile hidden in production`, `draft profile visible when preview`, `bodyHtml renders markdown headings`, `updates sorted newest first`.
- [ ] **Step 2: Run** `npm test`. Expected: FAIL.
- [ ] **Step 3: Implement** the page migration.
- [ ] **Step 4: Verify:** run `npm test && npm run check && npm run build`, and expect them all to pass. Then run `python scripts/import_to_turso.py --skip-submissions` with `TURSO_DATABASE_URL=file:./local.db`, then `npm run dev`. Spot-check `/`, `/list/?category=…`, `/compare`, one reviewed `/<slug>/`, a draft slug (404 in prod mode), `/watchlist/` and `/categories/<slug>/` against production. The counts and the newest list must match.
- [ ] **Step 5: Commit** `feat(site): SSR pages backed by Turso`.

### Task 11: Runtime endpoints: clouds.json, watchlist.json, llms*.txt, sitemap

**Files:**
- Create: `src/lib/llms.ts`, `src/pages/clouds.json.ts`, `src/pages/watchlist.json.ts`, `src/pages/llms.txt.ts`, `src/pages/llms-full.txt.ts`, `src/pages/sitemap-index.xml.ts`, `src/pages/sitemap-[chunk].xml.ts`
- Modify: `src/lib/sitemap-chunks.ts` (build the chunk URL lists from `getClouds()`/`getPublishableProfiles()`/blog instead of the integration callback)
- Delete: `public/clouds.json`, `public/watchlist.json`, `public/llms.txt`, `public/llms-full.txt` (add them to `.gitignore`), `scripts/generate_llms.py`, `scripts/parse_readme_to_json.py` (after moving `_build_date_added_map` into `import_to_turso.py`), `scripts/generate_watchlist_json.py` (after moving `parse_watchlist` into `import_to_turso.py`), `tests/test_parse_readme.py`
- Test: `src/lib/llms.test.ts`

**Interfaces:**
- Produces: `renderLlmsTxt(clouds: CloudWithSlug[]): string`, `renderLlmsFullTxt(clouds: CloudWithSlug[]): string`. The JSON endpoints return the same shape as today's files, with `Access-Control-Allow-Origin: *` and `Cache-Control: public, max-age=300`.

- [ ] **Step 1: Write failing tests** in `llms.test.ts`: golden. Before deleting anything, generate `tests/fixtures/turso/llms.txt` + `llms-full.txt` with `scripts/generate_llms.py` from a fixed `clouds.json` fixture. Assert that `renderLlmsTxt(fixture) === file` for both.
- [ ] **Step 2: Run** `npm test`. Expected: FAIL.
- [ ] **Step 3: Implement** the endpoints + port, then delete the generators.
- [ ] **Step 4: Verify:** run `npm test && npm run build`. Then with `npm run dev`, `curl -s localhost:4321/clouds.json | jq length` equals the DB count, `curl -sI localhost:4321/llms.txt` returns `200 text/plain`, and `/sitemap-index.xml` lists the chunks that `sitemap-chunks.ts` defined before.
- [ ] **Step 5: Commit** `feat(site): runtime clouds.json, llms.txt, watchlist.json and sitemap`.

### Task 12: Server, image and deploy workflows

**Files:**
- Modify: `compute/server.js`. Keep the static-file + brotli/gzip + cache logic, but serve from `dist/client`. Requests that aren't static files go to `handler` from `./dist/server/entry.mjs` (Node `http` via Bun's `node:http`). Compress dynamic HTML/JSON/txt as a stream when the client accepts it. Keep the `HOST=::` default and the CORS header.
- Modify: `Dockerfile.datum` (`COPY dist ./dist`, also `COPY node_modules` needed by the server bundle if any are external, `CMD ["bun", "./server.js"]`; document `TURSO_DATABASE_URL`/`TURSO_AUTH_TOKEN` as runtime env), `deploy-datum.yml` (remove the clouds.json/llms/watchlist regeneration steps; drop `fetch-depth: 0`; pass `TURSO_DATABASE_URL`, the read-only `TURSO_AUTH_TOKEN`, `DATA_ENV=production` and `TURSO_ORG` to the workload), `ci.yaml` (add `pytest tests/` and `npm test`)
- Modify: `preview-datum.yml`. Remove the regeneration steps and add a "Preview database" step before deploy:
  - install the Turso CLI and authenticate with `TURSO_API_TOKEN`
  - `DB=alt-clouds-pv-<slug>` (same `<slug>` as the workload name)
  - if `inputs.reset_db` is true, run `turso db destroy "$DB" --yes || true`
  - `turso db show "$DB" || turso db create "$DB" --from-db alt-clouds`
  - `TURSO_DATABASE_URL=$(turso db show "$DB" --url) python scripts/db_migrate.py` with a short-lived token (the branch's migrations)
  - mint the workload token: `turso db tokens create "$DB" --expiration 30d`, masked with `::add-mask::`
  - pass `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`, `DATA_ENV=preview`, `TURSO_ORG` to the workload
  
  Add the `workflow_dispatch` input `reset_db` (boolean, default false).
- Modify: `preview-cleanup.yml`, `preview-autoclean.yml`. After destroying the workload, run `turso db destroy alt-clouds-pv-<slug> --yes || true`. The DB name is built by the same `preview.sh names` helper, so the three workflows can't drift.
- Modify: `docs/datum-compute-previews.md` (preview DB lifecycle, `reset_db`).
- Delete: `.github/workflows/deploy-pages.yml`, `public/CNAME` (only after the DNS cutover in Task 13)

- [ ] **Step 1: Verify the local image:** run `npm ci && npm run build && datumctl compute build --analyze .`, then run the image with `TURSO_DATABASE_URL=<read-only prod or local sqld>`. `curl -H 'Accept-Encoding: br' -sI localhost:3000/` gives `200` + `content-encoding: br`; `/_astro/*` gives an immutable cache header; `/<reviewed-slug>/` gives 200; `/no-such-slug/` gives 404.
- [ ] **Step 2: Kill Turso access** (bad token) after warming `/`. `/` still returns 200 from the stale cache.
- [ ] **Step 3: Verify the preview DB lifecycle:** run `preview-datum.yml` for a test branch whose commit adds a dummy migration `9999_preview_probe.sql`.
  - `turso db list` shows `alt-clouds-pv-<slug>`, and that DB has the probe table. Prod (`alt-clouds`) does **not** have it.
  - The preview site loads with the same cloud count as prod.
  - `python scripts/profile_admin.py set-status <slug> reviewed` against the preview DB changes only the preview.
  - Re-running with `reset_db: true` gives a fresh copy.
  - Deleting the branch leaves no `alt-clouds-pv-<slug>` in `turso db list`.
- [ ] **Step 4: Commit** `feat(deploy): SSR server on Datum Compute with Turso env and per-preview DBs`.

### Task 13: Production cutover + docs

**Files:**
- Modify: `CLAUDE.md` (the "README is the source of truth" section → Turso; the commands section: `db_migrate.py`, `import_to_turso.py`, `profile_admin.py`, `npm test`; remove the "never hand-edit clouds.json" note), `.github/CONTRIBUTING`/README Contributing section (README is generated, so don't edit entries by hand)
- Delete: `src/content/clouds/` (after the import is verified), `analysis/` references are left as historical

- [ ] **Step 1: Provision:** `turso db create alt-clouds`. Create tokens: `turso db tokens create alt-clouds --read-only` (runtime) and a full-access token (Actions). Create a platform API token (`turso auth api-tokens mint alt-clouds-ci`) for preview DBs. Set the repo secrets `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN_RW`, `TURSO_API_TOKEN`, the repo variable `TURSO_ORG`, and the Datum workload env.
- [ ] **Step 2: Freeze writes:** temporarily disable the submission/graduation/watchlist workflows (`gh workflow disable …`).
- [ ] **Step 3: Migrate + import into prod:** `python scripts/db_migrate.py && python scripts/import_to_turso.py` with the RW env. Then run `python scripts/render_readme.py && git diff --exit-code README.md WATCHLIST.md`. Expected: no diff.
- [ ] **Step 4: Deploy** via `deploy-datum.yml`. Compare against the old site: the clouds count, `/clouds.json` (`jq -S` diff against the last Pages `clouds.json` is empty except key order), 5 random profile pages and `/llms.txt`.
- [ ] **Step 5: DNS cutover:** point `www.alt-cloud.org` at the Datum load balancer and wait for TLS. Then delete `deploy-pages.yml` + `public/CNAME` and disable Pages in repo settings.
- [ ] **Step 6: Re-enable workflows.** End-to-end check: open a test submission issue → evaluation → `/approve` → the cloud is in the DB → `sync-readme` commits README → the site shows it within 60 s. Delete the test entry afterwards via `delete_cloud` + a sync.
- [ ] **Step 7: Remove MDX + docs:** `git rm -r src/content/clouds`, update `CLAUDE.md`. Commit `chore: retire file-based cloud data; Turso is source of truth`.

---

## Rollback

Until Step 7 of Task 13, the old Pages deploy (`deploy-pages.yml` at the pre-cutover tag) plus the MDX files still exist. To roll back, point DNS back to Pages and re-enable the old workflows. After Step 7, recovery means `git revert` of the cutover commit plus regenerating `clouds.json` from the last bot-rendered README, which keeps the README a usable backup.
