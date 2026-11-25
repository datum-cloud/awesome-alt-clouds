# DB-Native Intake Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace every GitHub-issue-driven data feature (submit, split, approve, revalidate, watchlist, graduation, evidence) with DB-backed public forms, a status page and an admin console.

**Architecture:** Public SSR forms post to `/api/*` endpoints that validate, rate-limit and write to Turso, then fire `repository_dispatch`. Python jobs in Actions do the evaluation and approval work, keyed by DB id, with a cron sweep as the fallback. A GitHub-OAuth admin console drives state transitions. Every transition is written to `audit_log`.

**Tech Stack:** Astro SSR API routes, `@libsql/client`, Cloudflare Turnstile, GitHub OAuth + REST (`repository_dispatch`), Python 3.15, pytest, vitest.

**Spec:** `docs/superpowers/specs/2026-11-25-db-native-intake-design.md` (prerequisite: `docs/superpowers/plans/2026-11-25-turso-migration.md` fully shipped)

## Global Constraints

- New runtime env: `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET`, `IP_HASH_SALT`, `GITHUB_OAUTH_CLIENT_ID`, `GITHUB_OAUTH_CLIENT_SECRET`, `SESSION_SECRET`, `ADMIN_GITHUB_LOGINS`, `GITHUB_DISPATCH_TOKEN`, `EXTENSION_ORIGINS`. Production uses the **read-write** Turso token for `alt-clouds`. Previews write to their own DB `alt-clouds-pv-<slug>` (phase 1). Preview-only env: `ADMIN_AUTH_MODE=preview`, Turnstile test keys. See the spec's "Previews" table.
- Every dispatch payload carries `target: "production" | "preview"` (+ `db` for preview). Python jobs get their DB only via `scripts/lib/db_target.py:resolve_target(payload)`. Preview runs never send `data-changed`.
- Limits (spec): 5 submission batches/IP/hour, ≤10 URLs/batch, 5 graduation requests/IP/hour, 10 evidence/IP/hour, ≤3 open graduation requests per cloud.
- Status values and transitions are exactly the spec's state machine. TS `src/lib/intake/status.ts` and Python `scripts/lib/intake_status.py` must match (sync test).
- Every admin or bot transition writes one `audit_log` row in the same `batch` as the state change.
- Dispatch is best-effort: a failed dispatch never fails the user request.
- Event types: `evaluate-submission`, `approve-submission`, `evaluate-graduation`, `approve-graduation`, `data-changed`.
- Python jobs keep fail-open for evaluation (`failed` status + `last_error`, exit 0). Approval jobs set the status back to `evaluated` with `last_error` and exit 1.

## Review Focus

1. **Dispatch lost / GitHub down:** the row stays `queued`/`approving`, and the sweep picks it up within 15 min. → Task 4 test `test_sweep_picks_stale_rows`.
2. **Double-click / concurrent approve:** a second approve on the same row must not insert twice. Transitions are compare-and-set (`UPDATE … WHERE id=? AND status=?`, rowcount 1). → Task 2 test `transition is compare-and-set`, Task 6 test `test_approve_twice_inserts_once`.
3. **SSRF via submitted URL** (`http://169.254.169.254`, `http://localhost:3000`, IDN/decimal-IP tricks): rejected at the API, and the resolved IP is re-checked in the fetcher. → Task 3 tests, Task 4 test `test_fetcher_rejects_private_resolved_ip`.
4. **Non-admin hitting admin APIs** (no cookie, tampered cookie, login not on the allowlist, cross-origin POST): all 401/403. → Task 5 tests.
5. **Preview job touching prod:** a dispatch from a preview (or a forged payload) must never resolve to the prod DB, and must never trigger `sync-readme`. → Task 4 tests `test_resolve_target_preview_never_prod`, `test_preview_run_skips_data_changed`.

---

### Task 1: Schema 0002 + Python repos for intake

**Files:**
- Modify: `db/migrations/0001_init.sql` (`submissions.issue_number` nullable; do this before phase 1 cutover, otherwise move it into 0002 as a table rebuild)
- Create: `db/migrations/0002_intake.sql` (spec schema; copies `decision`→`status` with `pending`→`evaluated`), `scripts/lib/intake_status.py`, `scripts/lib/intake_repo.py`
- Test: `tests/test_intake_repo.py`, `tests/test_intake_status_sync.py`

**Interfaces:**
- Produces (Python):
  - `TRANSITIONS: dict[str, frozenset[str]]` and `can_transition(src: str, dst: str) -> bool`
  - `transition(db, table: Literal["submissions","graduation_requests"], id: int, src: str, dst: str, *, actor: str, action: str, fields: dict | None = None) -> bool`. One batch runs the CAS `UPDATE ... WHERE id=? AND status=?` (setting `status_changed_at` and `fields`) and the `audit_log` insert. It returns False when the row is not in `src`. It raises `ValueError` on an illegal transition.
  - `get_submission(db, id) -> SubmissionRow`, `get_batch_submissions(db, batch_id) -> list[SubmissionRow]`, `get_graduation(db, id) -> GraduationRow`, `stale_rows(db, table, statuses: tuple[str, ...], older_than_minutes: int) -> list[int]`
  - `SubmissionRow` (phase 1) gains `batch_id, status, reject_reason, suggested: dict, overrides: dict, last_error, status_changed_at`. New `@dataclass GraduationRow` mirrors the table.

- [ ] **Step 1: Write failing tests:** `test_migration_0002_maps_decision_to_status`, `test_transition_cas_returns_false_when_status_moved`, `test_transition_illegal_raises`, `test_transition_writes_audit_row`, `test_stale_rows_filters_by_age`. In `test_intake_status_sync.py`, parse `TRANSITIONS` out of `src/lib/intake/status.ts` (it is created in Task 2; skip with a reason until the file exists) and assert equality.
- [ ] **Step 2: Run** `pytest tests/test_intake_repo.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest tests/ -v`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(intake): schema 0002 and intake repository`.

### Task 2: TS intake core (status, repo, audit, dispatch)

**Files:**
- Create: `src/lib/intake/status.ts`, `src/lib/intake/repo.ts`, `src/lib/intake/dispatch.ts`, `src/lib/intake/tokens.ts`
- Test: `src/lib/intake/repo.test.ts`, `src/lib/intake/dispatch.test.ts`

**Interfaces:**
- Produces:
  - `TRANSITIONS: Record<Status, readonly Status[]>`, `canTransition(src, dst): boolean`
  - `transition(table, id, src, dst, { actor, action, fields? }): Promise<boolean>`, with the same CAS + audit semantics as Python.
  - `createBatch({ urls, notes, source, ipHash }): Promise<{ batchId: number; token: string; submissionIds: number[] }>` (one `batch`; URLs are de-duplicated after normalization).
  - `getBatchByToken(token)`, `getGraduationByToken(token)`, `createGraduationRequest({ cloudId, reason, evidence, source, ipHash }): Promise<{ id; token }>`, `addEvidence({ watchlistId, evidenceUrl, note, ipHash })`
  - `newToken(): string` (32 random bytes, base64url), `hashIp(ip: string): string` (sha256 with `IP_HASH_SALT`)
  - `dispatchTarget(): { target: "production" } | { target: "preview"; db: string }` is derived from `DATA_ENV` and the DB host (`alt-clouds-pv-<slug>`). `dispatch()` merges it into every payload, so callers never set it.
  - `dispatch(eventType: EventType, payload: Record<string, unknown>): Promise<boolean>`. On preview it drops `data-changed` events (returns true without calling GitHub). It POSTs `https://api.github.com/repos/datum-cloud/awesome-alt-clouds/dispatches` with `GITHUB_DISPATCH_TOKEN`, returns false on any error or non-204 (logged), and never throws.

- [ ] **Step 1: Write failing tests:** `transition is compare-and-set` (two concurrent `transition(…,'evaluated','approving')` → exactly one true), `createBatch dedupes normalized urls`, `dispatch returns false and does not throw on 500` (mocked `fetch`), `dispatch sends event_type and client_payload`, `dispatch adds preview target and db on preview`, `dispatch drops data-changed on preview`.
- [ ] **Step 2: Run** `npm test`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `npm test && pytest tests/test_intake_status_sync.py`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(intake): TS status machine, repo and dispatch`.

### Task 3: Public submission API, form and status page

**Files:**
- Create: `src/lib/intake/guard.ts`, `src/lib/intake/duplicates.ts`, `src/pages/api/submissions.ts`, `src/pages/submit/status/[token].astro`
- Modify: `src/pages/submit/index.astro` (remove the issue-URL builder and the mobile copy-paste step; POST JSON to `/api/submissions` with the Turnstile token; on 201 redirect to the status page; on 409 show "already listed → link to `/<slug>/` or the provider"), `.github/workflows` none
- Test: `src/lib/intake/guard.test.ts`, `src/lib/intake/duplicates.test.ts`, `src/pages/api/submissions.test.ts`

**Interfaces:**
- Produces:
  - `verifyTurnstile(token: string, ip: string): Promise<boolean>`
  - `rateLimit(key: string, limit: number, windowMinutes: number): Promise<boolean>` (atomic `INSERT … ON CONFLICT DO UPDATE SET count = count + 1 RETURNING count`)
  - `checkPublicUrl(raw: string): { ok: true; url: string } | { ok: false; reason: string }` (spec URL-safety rules)
  - `normalizeDomain(url: string): string` and `normalizeName(name: string): string`, ported from `scripts/check_duplicates.py`. `findListedDuplicate(url): Promise<CloudWithSlug | undefined>` checks `clouds` and non-terminal `submissions`.
  - `POST /api/submissions` body `{ urls: string[], notes?: string, turnstileToken: string, website?: string /* honeypot */ }` returns:
    - `201 { token, statusUrl }`
    - `400 { error, field? }`
    - `409 { error: "duplicate", url, cloud }`
    - `429`
    
    After the insert it calls `dispatch("evaluate-submission", { batch_id })`.
  - `/submit/status/[token]`: SSR, `noindex`. Per URL it shows status, score, the 3 criteria, the rendered `report_md`, and the reject reason. It auto-refreshes every 30 s while any row is `queued`/`evaluating`. An unknown token gives a 404.

- [ ] **Step 1: Write failing tests:** `checkPublicUrl rejects` each of `http://localhost`, `http://127.0.0.1`, `http://[::1]`, `http://2130706433`, `http://169.254.169.254`, `ftp://x.com`, `https://user@x.com`, `https://x.internal`, `https://x.com:8443`, and accepts `https://www.example.com/path`. `normalizeDomain parity`: a shared fixture `tests/fixtures/intake/domains.json` (input → expected), also asserted from Python in `tests/test_check_duplicates.py`. `rateLimit allows 5 then blocks`. API: `honeypot filled → 201 but nothing stored`, `11 urls → 400`, `listed url → 409`, `happy path stores queued rows and dispatches`.
- [ ] **Step 2: Run** `npm test`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `npm test && npm run check`. Then on `npm run dev` with `file:./local.db` and Turnstile test keys (`1x00000000000000000000AA` / `1x0000000000000000000000000000000AA`), submit 2 URLs. Expected: the status page shows 2 `queued` rows.
- [ ] **Step 5: Commit** `feat(intake): public submission API, form and status page`.

### Task 4: Evaluation job keyed by DB id + sweep

**Files:**
- Modify: `scripts/evaluate_submission.py` (new `main()`: `--batch <id>` or `--id <id>`. For each row it does CAS `queued→evaluating`, runs the full `check_duplicates` (→ `duplicate`) then `evaluate_service()` + `generate_metadata()`, and writes score/criteria/report/suggested → `evaluated`. Any exception → `failed` + `last_error`, exit 0. Drop the `ISSUE_BODY` parsing.), `scripts/check_duplicates.py` (no GitHub comment/label/close; returns a match), `scripts/lib/fetcher.py` (resolve the host and refuse private/loopback/link-local IPs before fetching)
- Rewrite: `.github/workflows/evaluate-submission.yml` (`on: repository_dispatch: types: [evaluate-submission]` + `workflow_dispatch: inputs.batch_id`)
- Create: `scripts/sweep.py`, `.github/workflows/sweep.yml` (`schedule: "*/15 * * * *"` + `workflow_dispatch`; prod only)
- Create: `scripts/lib/db_target.py`. Every dispatched workflow (`evaluate-*`, `approve-*`) starts with one shared step that calls it and exports `TURSO_DATABASE_URL`/`TURSO_AUTH_TOKEN`/`DATA_ENV` for the job. For preview it mints a 1h token with the Turso CLI.
- Delete: `split-submission.yml`, `auto-label-submission.yml`, `revalidate-submission.yml`, `scripts/split_submission.py`, `tests/test_split_submission*.py` (if any)
- Test: update `tests/test_evaluate_submission.py`, `tests/test_check_duplicates.py`; create `tests/test_sweep.py`

**Interfaces:**
- Consumes: `transition`, `stale_rows` (Task 1).
- Produces: `resolve_target(payload: dict) -> Target`, where `@dataclass Target(env: Literal["production","preview"], db_name: str)`.
  - `target: "production"` → `alt-clouds`; any `db` field is ignored.
  - `target: "preview"` → `db` must match `^alt-clouds-pv-[a-z0-9-]{1,40}$`.
  - Anything else → `ValueError`.

  Also `emits_data_changed(target) -> bool` (True only for production).
- Produces: `sweep(db, *, dispatch_fn) -> dict[str, int]`. It re-dispatches `queued` and `approving` submissions/graduations older than 10 min, and `evaluating` rows older than 30 min go back to `queued` (crashed job). It returns counts per event.

- [ ] **Step 1: Write failing tests:** `test_evaluate_batch_sets_evaluated_with_suggestions` (mocked `evaluate_service`), `test_evaluate_marks_duplicate`, `test_evaluate_exception_marks_failed_exit_0`, `test_evaluate_skips_row_not_queued` (CAS false → no work), `test_sweep_picks_stale_rows`, `test_sweep_requeues_stuck_evaluating`, `test_resolve_target_preview_never_prod` (`{target:"preview", db:"alt-clouds"}`, `{target:"preview"}`, `{target:"preview", db:"alt-clouds-pv-x; rm"}` → ValueError), `test_resolve_target_production_ignores_db`, `test_preview_run_skips_data_changed`, `test_fetcher_rejects_private_resolved_ip` (monkeypatched `socket.getaddrinfo` → `10.0.0.5`).
- [ ] **Step 2: Run** `pytest tests/test_evaluate_submission.py tests/test_sweep.py tests/test_check_duplicates.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest tests/ -v`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(intake): DB-keyed evaluation job and sweep`.

### Task 5: Admin auth (GitHub OAuth, session, allowlist)

**Files:**
- Create: `src/lib/admin/session.ts`, `src/lib/admin/guard.ts`, `src/pages/admin/login.ts`, `src/pages/admin/callback.ts`, `src/pages/admin/logout.ts`, `src/middleware.ts` (protects `/admin/*` and `/api/admin/*`)
- Test: `src/lib/admin/session.test.ts`, `src/lib/admin/guard.test.ts`

**Interfaces:**
- Produces:
  - `signSession({ login, exp }): string` and `readSession(cookie: string | undefined): { login: string } | null` (HMAC-SHA256 with `SESSION_SECRET`, constant-time compare, expiry checked)
  - `requireAdmin(context): { login: string } | Response` returns 302 to `/admin/login` for pages, 401 for `/api/admin/*`, and 403 when the login is not in `ADMIN_GITHUB_LOGINS` or when `Origin` ≠ site origin on POST.
  - `ADMIN_AUTH_MODE=preview` (allowed only when `DATA_ENV=preview`; otherwise startup throws) skips OAuth. The actor is `preview:<user>` from the `Authorization: Basic` header that the load balancer already verified. No header → 401. The Origin check still applies.
  - OAuth: `login` sets a `state` cookie (random) → GitHub authorize (`read:user`). `callback` verifies `state`, exchanges the code, fetches `/user`, checks the allowlist, sets the `admin_session` cookie, and redirects to `/admin/`.

- [ ] **Step 1: Write failing tests:** `readSession rejects tampered signature`, `readSession rejects expired`, `requireAdmin 401 without cookie on api`, `requireAdmin 403 for non-allowlisted login`, `requireAdmin 403 on cross-origin POST`, `callback rejects state mismatch` (mocked GitHub fetch), `preview mode uses basic-auth user as actor`, `preview mode refused when DATA_ENV=production`.
- [ ] **Step 2: Run** `npm test`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `npm test`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(admin): GitHub OAuth login with allowlist`.

### Task 6: Admin submissions console + approve job

**Files:**
- Create: `src/pages/admin/index.astro` (queue counts per status), `src/pages/admin/submissions/index.astro` (filter by status, newest first), `src/pages/admin/submissions/[id].astro` (report, criteria, suggested fields as an editable form, action buttons), `src/pages/api/admin/submissions/[id].ts` (`POST {action: "approve"|"reject"|"watchlist"|"reevaluate", overrides?, reason?, score?}`), `src/pages/admin/audit.astro`, `.github/workflows/approve-submission.yml` (`repository_dispatch: [approve-submission]`)
- Modify: `scripts/approve_submission.py` (phase 1). The CLI becomes `--id <submission_id>`. It reads `suggested` merged with `overrides` and then does `approving → approved` with `cloud_id`, plus `dispatch data-changed`. On `ApprovalError` → `evaluated` + `last_error`, exit 1.
- Delete: `admin-approve-submission.yml`, `watchlist.yml`, `close-issue-on-pr-close.yml`, `scripts/watchlist_add.py` (logic moves to the TS `watchlist` action)
- Test: `src/pages/api/admin/submissions.test.ts`, update `tests/test_approve_submission.py`

**Interfaces:**
- Consumes: `transition`, `dispatch`, `requireAdmin`; `approve()` (phase 1 Task 7).
- Produces: action semantics.
  - `approve`: `evaluated→approving` + store `overrides` (validated: category ∈ CATEGORIES, tags valid, score ∈ {2,3}) + `dispatch("approve-submission",{id})`.
  - `reject`: `evaluated→rejected` with a required `reason`.
  - `watchlist`: `evaluated→watchlisted` + `upsertWatchlist` (TS) in the same batch, only when `score === 1`, + `dispatch("data-changed")`.
  - `reevaluate`: `evaluated|failed→queued` + dispatch evaluate.

- [ ] **Step 1: Write failing tests:** API: `approve validates overrides`, `watchlist refused unless score 1`, `reject requires reason`, `each action writes audit_log with actor login`. Python: `test_approve_twice_inserts_once` (second run sees status `approved` → no-op exit 0), `test_approve_uses_overrides_over_suggested`, `test_approve_failure_returns_to_evaluated_with_error`.
- [ ] **Step 2: Run** `npm test && pytest tests/test_approve_submission.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `npm test && pytest tests/ -v && npm run check`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(admin): submissions console and DB-keyed approval`.

### Task 7: Graduation requests (site, extension API, jobs, admin)

**Files:**
- Create: `src/pages/graduate/[slug].astro` (form: reason, evidence, Turnstile; only for 🔵 clouds, else 404), `src/pages/graduate/status/[token].astro`, `src/pages/api/graduation-requests.ts`, `src/pages/admin/graduations/index.astro`, `src/pages/admin/graduations/[id].astro`, `src/pages/api/admin/graduations/[id].ts`, `.github/workflows/evaluate-graduation.yml`
- Modify: `src/components/EmergingBanner.astro` (link to `/graduate/<slug>/`), `src/lib/github.ts` (delete `graduationIssueUrl`), `scripts/evaluate_graduation.py` (`--id`, CAS like Task 4), `scripts/approve_graduation.py` (`--id`, `target_category` from the row), `.github/workflows/approve-graduation.yml` (`repository_dispatch: [approve-graduation]`), `.github/workflows/graduation-request.yml` (→ **bridge**: parse the `[Graduation]` issue, insert `graduation_requests` with `source=issue-import`, comment the status URL, close the issue)
- Test: `src/pages/api/graduation-requests.test.ts`, update `tests/test_evaluate_graduation.py`, `tests/test_approve_graduation.py`; create `tests/test_graduation_bridge.py`

**Interfaces:**
- Produces: `POST /api/graduation-requests` body `{ slug, reason?, evidence?, turnstileToken? }`. Turnstile is required unless `Origin` ∈ `EXTENSION_ORIGINS` (then CORS allows that origin). Responses: `201 {token, statusUrl}`, `404` when the slug is unknown or not unverified, `409` when there are already 3 open requests, `429`. Admin actions: `approve {category}`, `reject {reason}`, `reevaluate`.

- [ ] **Step 1: Write failing tests:** `rejects verified cloud with 404`, `extension origin skips turnstile and gets CORS header`, `4th open request → 409`, `test_bridge_creates_row_and_closes_issue` (mocked GitHub API), `test_evaluate_graduation_by_id`, `test_approve_graduation_by_id_uses_target_category`.
- [ ] **Step 2: Run** `npm test && pytest tests/test_evaluate_graduation.py tests/test_approve_graduation.py tests/test_graduation_bridge.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `npm test && pytest tests/ -v`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(intake): graduation requests without issues`.

### Task 8: Watchlist evidence + profile status toggle

**Files:**
- Create: `src/pages/api/watchlist/[id]/evidence.ts`, `src/components/WatchlistEvidenceForm.astro`, `src/pages/admin/watchlist.astro` (evidence queue: accept / dismiss; "promote" = open a prefilled submission for that URL and remove it from the watchlist on approval), `src/pages/api/admin/profiles/[slug].ts` (`POST {status}`), `src/pages/admin/profiles.astro` (list drafts, toggle reviewed)
- Modify: `src/pages/watchlist/index.astro` (per-row "Submit evidence"), `WATCHLIST.md` header prose ("comment on the original issue" → "use Submit evidence on alt-cloud.org/watchlist"), `scripts/render_watchlist.py` (prose is template-preserved; edit it in the template only)
- Test: `src/pages/api/watchlist/evidence.test.ts`, `src/pages/api/admin/profiles.test.ts`

**Interfaces:**
- Produces: `POST /api/watchlist/[id]/evidence` `{ note, evidenceUrl?, turnstileToken }` → `201 | 400 | 404 | 429`. Admin evidence actions write `audit_log`. `POST /api/admin/profiles/[slug] {status}` writes the profile status + audit. The cache for that slug is invalidated (`cached` key `profile:<slug>` deleted).

- [ ] **Step 1: Write failing tests:** `evidence requires note`, `evidence unknown watchlist id 404`, `evidence rate-limited after 10`, `profile toggle writes audit and invalidates cache`.
- [ ] **Step 2: Run** `npm test`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `npm test && npm run check`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(intake): watchlist evidence and profile status in admin`.

### Task 9: Cutover

**Files:**
- Modify: `CLAUDE.md` (pipeline section rewritten: form → API → dispatch → Actions → admin console; list the env vars), `README.md` Contributing section template ("Submit at alt-cloud.org/submit"), `src/pages/submit/index.astro` copy
- Delete: issue-only helpers left over (`rg -n "ISSUE_BODY|ISSUE_NUMBER|issues/new" scripts src .github` must only hit `graduation-request.yml` (bridge) and the footer `REPO_ISSUES_URL`)

- [ ] **Step 1: Provision secrets:** create the GitHub OAuth app (callback `https://www.alt-cloud.org/admin/callback`), the Turnstile site, the fine-grained dispatch token and the salts. Set them on the Datum workload. Switch the prod Turso token to RW.
- [ ] **Step 2: Import open issues:** a one-off `python scripts/import_to_turso.py --open-issues-only`. Each open `submission` issue becomes a batch with `source=issue-import` and status `queued` (or `evaluated` if a bot evaluation exists). The bot comments the status-page link and closes the issue with the label `migrated-to-db`.
- [ ] **Step 3: Deploy.** End-to-end on prod:
  - a test submission reaches `evaluated` within 5 min
  - admin approve → the cloud is visible on `/list/` within 60 s and the README commit lands
  - a graduation request from `/graduate/<slug>/` completes the same way
  - a dispatch with a deliberately broken token is recovered by the sweep within 15 min

  Clean up the test rows (`delete_cloud`, audit kept).
- [ ] **Step 4: Remove the issue-template submission path** in repo settings (if configured), and verify the `rg` check from Files is clean.
- [ ] **Step 5: Commit** `chore(intake): retire issue-based intake`.
- [ ] **Step 6 (later):** once the extension release that calls the API has ≥90% of installs, delete `graduation-request.yml` (the bridge).
