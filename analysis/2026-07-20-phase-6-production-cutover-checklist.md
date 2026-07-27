# Phase 6 Cutover Checklist — Moving to `datum-cloud/awesome-alt-clouds`

This document summarizes everything that needs to be prepared/changed when the Astro migration work on this fork (`ronggur/awesome-alt-clouds`, branch `feat/astro-migration`) moves into the upstream repo `datum-cloud/awesome-alt-clouds` for production. This is "Phase 6", already referenced in `CONTRIBUTING.md` and `analysis/2026-05-19-astro-migration-rfc.md`.

> A few items below need direct verification with the org/GitHub App owner (marked ⚠️) since they can't be confirmed from repo contents alone.

## Production domain architecture (locked decision)

`www.alt-cloud.org` is **not** served via GitHub Pages custom-domain settings. Upstream today (verified Jul 2026):

- **GitHub Pages** publishes at `https://datum-cloud.github.io/awesome-alt-clouds/` (branch `/docs`, Custom domain field **empty** in Settings → Pages).
- **No `CNAME` file** exists in upstream git — never has.
- **Datum proxy** terminates public traffic: `www.alt-cloud.org` → `*.datumproxy.net` → GitHub Pages origin.

```
User → www.alt-cloud.org (datumproxy) → datum-cloud.github.io/awesome-alt-clouds/ → site content
```

**Datum proxy will remain in use after cutover.** Do **not** add `public/CNAME` or fill the Custom domain field in GitHub Settings unless the team explicitly migrates off datumproxy to native GitHub custom domain (would also require DNS changes away from `datumproxy.net`).

Post-cutover verification target: same proxy chain, new Astro-built artifact at the same `github.io` URL.

---

## Quick checklist

### Code / repo (PR into upstream `main`)

- [x] `site.config.mjs`: `preview: false`
- [x] `site.config.mjs`: `blockSearchBots: false` (set explicitly — do not rely on default)
- [x] `.github/workflows/deploy-pages.yml`: triggers limited to `main` + `v*` tags (no `feat/astro-migration`)
- [x] `.github/workflows/lint.yml`: triggers limited to `main` + `v*` tags
- [x] `.github/workflows/update-blog-posts.yml` removed
- [ ] Delete remaining legacy `docs/` folder (upstream still has full `/docs` site; fork has partial leftovers)
- [ ] ~~Create `public/CNAME`~~ — **skip** (datumproxy handles `www.alt-cloud.org`; see architecture above)

### GitHub / ops (upstream repo)

- [ ] Configure all required secrets & variables in `datum-cloud/awesome-alt-clouds` (see section C)
- [ ] ⚠️ Confirm the GitHub App (used by admin workflows) is/gets installed on the `datum-cloud` org
- [ ] Switch GitHub Pages source: **Deploy from a branch** (`/docs`) → **GitHub Actions**
- [ ] Verify `https://datum-cloud.github.io/awesome-alt-clouds/` serves the Astro build after first Actions deploy
- [ ] Verify `https://www.alt-cloud.org/` still resolves via datumproxy (no DNS change expected)
- [ ] **Leave Custom domain field empty** in Settings → Pages (datumproxy stays authoritative)
- [ ] ⚠️ Carry over/replicate branch protection rules on upstream `main`
- [ ] Monitor for 48 hours after cutover (datumproxy → github.io chain, Fathom analytics, submission pipeline)

---

## A — Config file changes

### 1. `public/CNAME` — skip (datumproxy)

The fork briefly had `public/CNAME` during early Astro migration (`e950d3d`), then removed it for github.io preview (`b6be5dd`). Upstream has **never** committed a `CNAME` file.

With datumproxy remaining in front of GitHub Pages:

- **Do not** add `public/CNAME` to the Astro build artifact.
- **Do not** configure Custom domain in GitHub Settings unless deliberately moving off datumproxy.

The canonical public URL in SEO/metadata remains `https://www.alt-cloud.org` via `site.config.mjs` → `productionSite`; datumproxy forwards to the `github.io` origin.

### 2. `site.config.mjs`

Set (or confirm) production profile:

```js
preview: false,
blockSearchBots: false,
```

Effects (via `astro.config.mjs`):

- `site` → `productionSite` (`https://www.alt-cloud.org`) — used for sitemap, OG, canonical URLs
- `base` → `productionBase` (`undefined` — site root at origin, not `/awesome-alt-clouds/` path prefix in HTML)
- `robots.txt` + meta robots → allow indexing (`blockSearchBots: false`)

**Note:** GitHub project Pages still live at `datum-cloud.github.io/awesome-alt-clouds/`; datumproxy hides that path from end users. Astro `base: undefined` is correct for artifact content — the `/awesome-alt-clouds/` prefix is a GitHub Pages hosting quirk, not an Astro `base` setting.

### 3. `previewSite: "https://ronggur.github.io"` in `site.config.mjs`

Dead code while `preview: false`. Optional cleanup: point at `https://datum-cloud.github.io` if upstream wants fork-preview capability later.

### 4. `astro.config.mjs` and `package.json`

No changes needed.

### 5. Fathom Analytics (`src/layouts/Base.astro`)

Site ID `ZQEMDUAQ` is hardcoded and unconditional — already the production dashboard. Fork preview deploys have been sending traffic there throughout migration.

---

## B — GitHub Actions workflow changes

### 6–7. `deploy-pages.yml` and `lint.yml`

On `feat/astro-migration` branch these are already `main`-only. Confirm the merged PR into upstream does not reintroduce `feat/astro-migration` triggers.

### 8. Other workflows — no trigger changes needed

Submission/admin workflows trigger on `issues` / `issue_comment` / `pull_request: closed` / `workflow_dispatch` — no fork-specific branch logic.

### 9. `update-blog-posts.yml`

Already removed on the fork. Confirm absent in upstream after merge (upstream may still have it + live cron patching `docs/index.html`).

### 10. `auto-label-submission.yml`

Uses `context.repo.owner` / `context.repo.repo` generically — no change needed.

---

## C — Secrets & variables (upstream repo)

| Secret/Variable | Type | Used by |
| - | - | - |
| `APP_ID` | secret | `admin-approve-submission.yml`, `close-issue-on-pr-close.yml`, `watchlist.yml`, `revalidate-submission.yml` |
| `APP_PRIVATE_KEY` | secret | same |
| `ANTHROPIC_API_KEY` | secret | `admin-approve-submission.yml`, `backfill-profiles.yml`, `evaluate-submission.yml`, `split-submission.yml` |
| `QWEN_BASE_URL` | secret | same 4 workflows |
| `LLM_PROVIDER` | repo **variable** (optional) | defaults to `claude` |

`STRAPI_URL` / `STRAPI_TOKEN` were only for removed `update-blog-posts.yml` — not needed post-cutover.

`GITHUB_TOKEN` (built-in) covers `deploy-pages.yml` (`contents: read`, `pages: write`, `id-token: write`).

---

## D — GitHub repo settings / operational steps (not code)

### 11. Switch the GitHub Pages source

**Settings → Pages → Build and deployment → Source:** change from **Deploy from a branch** (`main` / `/docs`) to **GitHub Actions**. Do this after the migration PR (with `deploy-pages.yml`) is merged.

First Actions deploy publishes to the same `github.io` project URL; datumproxy should continue forwarding without DNS changes.

### 12. ⚠️ GitHub App installation

Admin/submission workflows need a GitHub App token (`APP_ID` + `APP_PRIVATE_KEY`). Confirm installed on `datum-cloud` org with access to `awesome-alt-clouds` before cutover.

### 13. Verify datumproxy + github.io after the switch

**Do not** expect Custom domain or `CNAME` in GitHub Settings — upstream keeps that field empty today.

Post-deploy checks:

```bash
# Proxy chain still resolves
dig +short www.alt-cloud.org CNAME   # → *.datumproxy.net

# GitHub origin serves new build
curl -sI https://datum-cloud.github.io/awesome-alt-clouds/

# Public URL serves same origin (via proxy)
curl -sI https://www.alt-cloud.org/
```

Compare `etag` / `last-modified` between github.io and www — should match when proxy is healthy.

Smoke-test key routes on **www.alt-cloud.org**: `/`, `/submit/`, `/watchlist/`, a cloud profile page, `/clouds.json`.

### 14. ⚠️ Branch protection

Replicate upstream `main` protection (required checks, review rules) if migrating from fork conventions.

---

## E — Files/directories to clean up

### 15. The `docs/` directory

Delete with the migration PR. Upstream still ships the legacy site from `/docs`; the Astro build replaces it entirely. Must coincide with removing/disabling `update-blog-posts.yml` on upstream if still present.

---

## F — RFC Phase 6 acceptance criteria (adapted for datumproxy)

From `analysis/2026-05-19-astro-migration-rfc.md`, with domain strategy clarified:

| RFC criterion | Datumproxy interpretation |
| - | - |
| Pages source → GitHub Actions | Required |
| `www.alt-cloud.org` still resolves | Verify via datumproxy (not GitHub Custom domain field) |
| Fathom still firing | Check dashboard after deploy |
| Monitor 48 h | github.io origin + www.alt-cloud.org + submission bots |

RFC risk *"Lose alt-cloud.org custom domain → Add public/CNAME"* applies to **native GitHub custom domain** setups only. With datumproxy, the risk is **proxy misconfiguration or stale origin URL** after switching deploy mechanism — coordinate with whoever administers datumproxy if the first Actions deploy doesn't propagate to www.

Decision #2 (locked): `clouds.json` / `llms*.txt` are artifact-only, regenerated in CI — no action needed.

---

## Suggested execution order

1. Open PR into upstream: Astro migration, `site.config.mjs` production profile, `deploy-pages.yml`, removal of `docs/` + `update-blog-posts.yml`. **No `public/CNAME`.**
2. ⚠️ Confirm GitHub App installed on `datum-cloud` org; copy secrets (section C).
3. Merge to upstream `main`.
4. **Settings → Pages → GitHub Actions** (leave Custom domain empty).
5. Wait for first `deploy-pages.yml` run; verify `datum-cloud.github.io/awesome-alt-clouds/`.
6. Verify `www.alt-cloud.org` via datumproxy (no DNS change).
7. Smoke-test submission pipeline (`/approve`, `/watchlist`, `/revalidate`).
8. Monitor 48 hours.
