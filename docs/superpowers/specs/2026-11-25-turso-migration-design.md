# Turso Migration — Design

**Status:** Draft · **Date:** 2026-11-25 · **Branch:** `move-to-turso`

## Goal

Move all cloud/provider data out of files in the repo and into a Turso (libSQL) database, which becomes the **single source of truth**. The site reads Turso **at runtime (SSR)**. `README.md` and `WATCHLIST.md` stay in the repo, but they are **generated** from Turso.

## Decisions (agreed 2026-11-25)

| Question | Decision |
| --- | --- |
| Source of truth | Turso. `README.md` / `WATCHLIST.md` are rendered from the DB and committed by a bot. |
| Site data access | Runtime SSR. Astro gets the `@astrojs/node` adapter and is served from Datum Compute. GitHub Pages deploy is retired. |
| Scope | Cloud entries, MDX profiles (frontmatter + body), watchlist, submission history. |

## Current state (what we migrate away from)

- `README.md` → `scripts/parse_readme_to_json.py` → `public/clouds.json` (471 entries) → `import cloudsData` in `src/lib/clouds.ts` at build time.
- `dateAdded` is rebuilt every deploy by walking `git log -p README.md`.
- 425 profiles in `src/content/clouds/<slug>.mdx` (Astro content collection). The bodies are plain Markdown with no imports or components.
- `WATCHLIST.md` → `public/watchlist.json` → `src/lib/watchlist.ts`.
- Submission history lives only in GitHub issue comments.
- Writers: `create_submission_pr.py`, `create_graduation_pr.py`, `watchlist_add.py`, `audit_emerging_badges.py`, `generate_cloud_profile.py`, `backfill_profiles.py`. Each one edits files and opens a PR.

## Target architecture

```
GitHub issue ─▶ evaluate_submission.py ─▶ submissions (Turso)
                                         │
maintainer /approve ─▶ approve_submission.py ─▶ clouds + cloud_tags + profiles(draft) (Turso)
                                         │
                       repository_dispatch "data-changed"
                                         ▼
                 sync-readme.yml: render_readme.py + render_watchlist.py ─▶ commit to main (App token)

Browser ─▶ Datum Compute (Bun + Astro SSR, @astrojs/node middleware) ─▶ Turso (HTTP, read-only token)
```

- **Review gate moves:** writes to the README no longer go through a merged PR. The gate is the maintainer's `/approve` (or `/approve-graduation`, `/watchlist`) comment. That comment writes to the DB directly. The README commit that follows is just a mirror.
- **Profile editing:** maintainers stop editing MDX. They use `scripts/profile_admin.py`: `export` writes `<slug>.md` (frontmatter + body), `import` writes it back, and `set-status` handles the draft → reviewed flip.

## Schema (libSQL / SQLite)

```sql
CREATE TABLE schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL);

CREATE TABLE clouds (
  id           INTEGER PRIMARY KEY,
  slug         TEXT NOT NULL UNIQUE,
  name         TEXT NOT NULL,
  url          TEXT NOT NULL UNIQUE,
  description  TEXT NOT NULL,
  score        INTEGER NOT NULL CHECK (score IN (2, 3)),
  unverified   INTEGER NOT NULL DEFAULT 0 CHECK (unverified IN (0, 1)),
  category     TEXT NOT NULL,            -- one of scripts/lib/taxonomy.py CATEGORIES
  date_added   TEXT,                     -- YYYY-MM-DD
  created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  updated_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TABLE cloud_tags (
  cloud_id INTEGER NOT NULL REFERENCES clouds(id) ON DELETE CASCADE,
  tag      TEXT NOT NULL,
  position INTEGER NOT NULL,
  PRIMARY KEY (cloud_id, tag)
);
CREATE TABLE profiles (
  cloud_id      INTEGER PRIMARY KEY REFERENCES clouds(id) ON DELETE CASCADE,
  status        TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','reviewed')),
  tagline       TEXT, headquarters TEXT, founded_year INTEGER,
  pricing_model TEXT CHECK (pricing_model IN ('hourly','monthly','usage-based','subscription','mixed')),
  open_source   INTEGER, logo TEXT,
  regions       TEXT NOT NULL DEFAULT '[]',  -- JSON array
  services      TEXT NOT NULL DEFAULT '[]',  -- JSON array
  socials       TEXT NOT NULL DEFAULT '{}',  -- JSON object {x, linkedin, github, website}
  body_md       TEXT NOT NULL DEFAULT '',
  updated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TABLE profile_updates (
  id INTEGER PRIMARY KEY, cloud_id INTEGER NOT NULL REFERENCES clouds(id) ON DELETE CASCADE,
  date TEXT NOT NULL, kind TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL, url TEXT
);
CREATE TABLE watchlist (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, url TEXT NOT NULL UNIQUE, category TEXT NOT NULL,
  date_added TEXT NOT NULL, reason_not_qualifying TEXT NOT NULL, criteria_need TEXT NOT NULL,
  last_reviewed TEXT NOT NULL
);
CREATE TABLE submissions (
  id INTEGER PRIMARY KEY,
  issue_number INTEGER,                 -- NULL for form submissions (phase 2, db-native intake)
  url          TEXT NOT NULL,
  name         TEXT,
  score        INTEGER,                 -- 0..3, NULL if evaluation failed
  criteria     TEXT NOT NULL DEFAULT '{}', -- JSON {pricing, self_service, sla}: bool
  category     TEXT, tags TEXT NOT NULL DEFAULT '[]',
  decision     TEXT NOT NULL DEFAULT 'pending'
               CHECK (decision IN ('pending','approved','rejected','duplicate','watchlisted')),
  report_md    TEXT,
  evaluated_at TEXT NOT NULL,
  decided_at   TEXT,
  cloud_id     INTEGER REFERENCES clouds(id) ON DELETE SET NULL,
  UNIQUE (issue_number, url)
);
CREATE INDEX idx_clouds_category ON clouds(category);
CREATE INDEX idx_submissions_url ON submissions(url);
```

One category per cloud, as `CLAUDE.md` says. The current `clouds.json` has one leftover two-category row (Pingcap → `Databases & Storage`, a legacy section). The importer **fails loudly** on any entry with more than one category, so it has to be fixed before import.

## Access & credentials

| Consumer | Env | Token |
| --- | --- | --- |
| Datum Compute (prod + previews) | `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN` | read-only |
| GitHub Actions pipeline | secrets `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN_RW` | read-write |
| Local dev / tests | `TURSO_DATABASE_URL=file:./local.db` | none |

- Python talks to Turso over the Hrana HTTP API (`POST {url}/v2/pipeline`) with `requests`, so there is no new native dependency. `file:` URLs use stdlib `sqlite3` (dev/tests).
- TS uses `@libsql/client/web` for http(s)/libsql URLs, which has no native module and so is safe inside the unikernel. It dynamic-imports `@libsql/client` only for `file:` URLs.

## Phase 2

Replacing GitHub issues as the intake channel (submit, approve, graduation, watchlist evidence → forms + admin console) is designed in `2026-11-25-db-native-intake-design.md`. Phase 1 keeps issue-based intake so the pipeline can be verified on the new DB first. The one forward-compatible choice made here for it is that `submissions.issue_number` is nullable.

## Non-goals

- Admin web UI (maintainers use the CLI + issue commands).
- Blog posts stay in `src/content/blog` (prerendered).
- Per-PR preview databases (previews read prod with the read-only token; schema-changing PRs must ship the migration first).

## Risks

- **Latency/cost per request**: every SSR page that lists clouds queries Turso. Mitigation: a 60 s in-process cache in the TS data layer, plus `Cache-Control: public, max-age=300, stale-while-revalidate=3600`.
- **Turso outage = site outage**: on a query error the cache serves stale data (no TTL eviction on failure).
- **Lost PR-review trail**: the `submissions` table + the bot README commit (`data: <action> <name> (#<issue>)`) replace it.
