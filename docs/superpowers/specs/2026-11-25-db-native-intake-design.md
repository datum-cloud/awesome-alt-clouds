# DB-Native Intake (no GitHub issues) — Design

**Status:** Draft · **Date:** 2026-11-25 · **Depends on:** `2026-11-25-turso-migration-design.md` (phase 1 must be live first)

## Goal

Replace every GitHub-issue-driven feature with DB-backed forms, a status page and an admin console. GitHub keeps two jobs: running the Python evaluation/approval jobs in Actions, and holding the bot-rendered `README.md`/`WATCHLIST.md`.

## Inventory: issue features → replacement

| Today (issue-based) | After |
| --- | --- |
| `/submit` form opens a prefilled issue (`labels=submission`) | `POST /api/submissions` → `submissions` rows → `/submit/status/<token>` |
| `auto-label-submission.yml` | gone (no labels) |
| `split-submission.yml` (multi-URL issue → child issues) | one form post = one `submission_batches` row + one `submissions` row per URL |
| `check_duplicates.py` on issue open | quick check in the API (instant answer) + full check (redirects) in evaluation |
| `evaluate-submission.yml` on `issues.labeled` | `repository_dispatch: evaluate-submission` + 15-min sweep cron |
| Comment `/approve [url] [score]` | Admin console **Approve** (score override, edit name/description/category/tags) |
| Comment `/revalidate` | Admin **Re-evaluate** |
| Comment `/watchlist` | Admin **Add to watchlist** |
| `rejected` label + close | Admin **Reject** (with a reason that shows on the status page) |
| `close-issue-on-pr-close.yml` | gone |
| `[Graduation] <Name>` issue (site `EmergingBanner` + browser extension) | `/graduate/<slug>` form + `POST /api/graduation-requests` (extension calls the same API) |
| Comment `/approve-graduation [Category]` | Admin graduation **Approve** (category select) |
| "Comment on the original issue with evidence" (WATCHLIST.md) | `/watchlist/` → **Submit evidence** form → `watchlist_evidence` → admin queue |
| Issue thread as the audit trail | `audit_log` table + `/admin/audit` |

Kept on GitHub: the footer's "Report an issue" (site bugs, not data) and the `sync-readme.yml` bot commit.

## Flows

```
Submitter ─▶ /submit ─▶ POST /api/submissions
               Turnstile · honeypot · rate limit · URL safety · quick duplicate check
               INSERT submission_batches + submissions(status=queued)
               dispatch evaluate-submission {batch_id}     (failure ignored: sweep retries)
          ◀─ 201 {token} → /submit/status/<token>

Actions evaluate_submission.py --batch <id>
  status queued→evaluating→evaluated (or duplicate / failed), score, criteria, report_md, suggestions

Maintainer ─▶ /admin/submissions/<id>  (GitHub OAuth + allowlist)
  Approve  → status=approving + dispatch approve-submission {id, overrides}
             → approve_submission.py --id → clouds + draft profile → status=approved → dispatch data-changed
  Reject   → status=rejected, reject_reason          (direct DB write, audit_log)
  Watchlist→ upsert watchlist, status=watchlisted, dispatch data-changed
  Re-evaluate → status=queued + dispatch evaluate-submission

Graduation: /graduate/<slug> or extension → POST /api/graduation-requests → same queued→evaluated→approved pipeline
            (evaluate_graduation.py --id, approve_graduation.py --id)
```

Rules:

- **LLM/fetch work and README-affecting validation stay in Python in Actions** (evaluate, approve submission, approve graduation). That keeps one implementation of the fetch cascade, slugify/tag/category validation and profile generation.
- **Plain status writes happen in TS on the server** (reject, add to watchlist, evidence triage, profile status toggle). Each one writes an `audit_log` row in the same batch.
- **Dispatch is best-effort.** The server calls `POST /repos/{owner}/{repo}/dispatches`. If that fails, the row stays `queued`/`approving` and `sweep.yml` (cron `*/15`) picks up rows that have sat in those states for more than 10 min. Nothing is lost when GitHub is down (fail-open).
- **Every state change goes through one table of allowed transitions**, mirrored in TS and Python and checked by a sync test:

| From | Allowed to |
| --- | --- |
| `queued` | `evaluating`, `failed` |
| `evaluating` | `evaluated`, `duplicate`, `failed`, `queued` |
| `evaluated` | `approving`, `rejected`, `watchlisted`, `queued` |
| `approving` | `approved`, `evaluated` (on failure, with `last_error`) |
| `failed` | `queued` |
| `approved`, `rejected`, `duplicate`, `watchlisted` | (terminal) |

## Schema (migration `0002_intake.sql`)

Phase 1's `submissions.issue_number` becomes nullable (change `0001_init.sql` before phase 1 ships: `issue_number INTEGER`).

```sql
CREATE TABLE submission_batches (
  id INTEGER PRIMARY KEY,
  token TEXT NOT NULL UNIQUE,            -- 32-byte random, base64url; public status-page key
  notes TEXT,
  source TEXT NOT NULL CHECK (source IN ('form','issue-import')),
  ip_hash TEXT,                          -- sha256(ip + IP_HASH_SALT), for rate limiting/abuse only
  created_at TEXT NOT NULL
);
ALTER TABLE submissions ADD COLUMN batch_id INTEGER REFERENCES submission_batches(id);
ALTER TABLE submissions ADD COLUMN status TEXT NOT NULL DEFAULT 'evaluated';
  -- queued|evaluating|evaluated|approving|approved|rejected|duplicate|watchlisted|failed
  -- (replaces `decision`; 0002 copies decision→status, `pending`→`evaluated`)
ALTER TABLE submissions ADD COLUMN reject_reason TEXT;
ALTER TABLE submissions ADD COLUMN suggested TEXT NOT NULL DEFAULT '{}'; -- JSON {name,description,category,tags}
ALTER TABLE submissions ADD COLUMN overrides TEXT NOT NULL DEFAULT '{}'; -- JSON, set by admin approve
ALTER TABLE submissions ADD COLUMN last_error TEXT;
ALTER TABLE submissions ADD COLUMN status_changed_at TEXT;
CREATE INDEX idx_submissions_status ON submissions(status, status_changed_at);

CREATE TABLE graduation_requests (
  id INTEGER PRIMARY KEY,
  cloud_id INTEGER NOT NULL REFERENCES clouds(id) ON DELETE CASCADE,
  token TEXT NOT NULL UNIQUE,
  reason TEXT, evidence TEXT,
  source TEXT NOT NULL CHECK (source IN ('form','extension','issue-import')),
  status TEXT NOT NULL DEFAULT 'queued',       -- same state machine as submissions
  score INTEGER, criteria TEXT NOT NULL DEFAULT '{}', report_md TEXT,
  target_category TEXT, reject_reason TEXT, last_error TEXT,
  ip_hash TEXT, created_at TEXT NOT NULL, status_changed_at TEXT
);

CREATE TABLE watchlist_evidence (
  id INTEGER PRIMARY KEY,
  watchlist_id INTEGER NOT NULL REFERENCES watchlist(id) ON DELETE CASCADE,
  evidence_url TEXT, note TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new','accepted','dismissed')),
  ip_hash TEXT, created_at TEXT NOT NULL
);

CREATE TABLE audit_log (
  id INTEGER PRIMARY KEY,
  actor TEXT NOT NULL,                  -- github login, or 'bot:<workflow>'
  action TEXT NOT NULL,                 -- e.g. submission.approve, graduation.reject
  target_type TEXT NOT NULL, target_id INTEGER NOT NULL,
  payload TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);

CREATE TABLE rate_limits (
  key TEXT NOT NULL, window_start TEXT NOT NULL, count INTEGER NOT NULL,
  PRIMARY KEY (key, window_start)
);
```

## Abuse & safety

- **Bot filter:** Cloudflare Turnstile (`TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET`) on every public form, plus a hidden honeypot field.
- **Rate limits:** submissions 5 batches/IP/hour, max 10 URLs per batch; graduation requests 5/IP/hour; evidence 10/IP/hour; 3 open graduation requests per cloud. All are enforced via `rate_limits`, keyed on `ip_hash`.
- **URL safety (SSRF, because the evaluator fetches the URL):** `https?` only, no userinfo, no IP literals, no `localhost`/`.local`/`.internal`, port 80/443 or none, max 2048 chars. The Python fetcher re-checks that the resolved IP isn't private.
- **Admin:** GitHub OAuth (`GITHUB_OAUTH_CLIENT_ID/SECRET`, scope `read:user`). Login is allowed when the user's login is in `ADMIN_GITHUB_LOGINS` (comma list). The session is an HMAC-signed cookie (`SESSION_SECRET`), `HttpOnly; Secure; SameSite=Lax`, 7 days. Every `POST /api/admin/*` checks that `Origin` equals the site origin.
- **Server privileges change:** the runtime now needs a **read-write** Turso token (Turso tokens are per-database). Production must use the RW token. Previews keep the read-only token, and their write endpoints return `503 read-only preview`.
- **The server holds `GITHUB_DISPATCH_TOKEN`:** a fine-grained PAT or App token, limited to this repo, with `contents: write` (required by `repository_dispatch`).
- **Privacy:** no submitter email is collected. Raw IPs are never stored, only `ip_hash`.

## Browser extension

The extension lives outside this repo. It gets `POST /api/graduation-requests` (CORS allows the extension origin `chrome-extension://<id>` from env `EXTENSION_ORIGINS`), with Turnstile skipped for that origin. Rate limits still apply. Until the new extension version reaches most users, `graduation-request.yml` stays as a **bridge**: it turns a `[Graduation]` issue into a `graduation_requests` row (`source=issue-import`) and closes the issue with a link to the status page.

## Non-goals

- Email notifications (the status-page link is the receipt).
- A public log of all submissions.
- A profile body editor in the admin UI (CLI `profile_admin.py` stays; the admin UI only toggles draft/reviewed).

## Risks

- **Turnstile + rate limits are weaker than "must have a GitHub account".** Watch the `queued` volume, and add `ADMIN_REVIEW_ALL=true` if spam slips through.
- **No public discussion thread.** The status page shows the evaluation report and reject reason, so the reasoning stays visible to the submitter.
- **Hand-written OAuth/session code.** Keep it small and covered by tests (see plan).
