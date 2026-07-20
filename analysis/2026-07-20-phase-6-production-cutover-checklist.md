# Phase 6 Cutover Checklist — Moving to `datum-cloud/awesome-alt-clouds`

This document summarizes everything that needs to be prepared/changed when the Astro migration work on this fork (`ronggur/awesome-alt-clouds`, branch `feat/astro-migration`) moves into the upstream repo `datum-cloud/awesome-alt-clouds` for production. This is "Phase 6", already referenced in `CONTRIBUTING.md` and `analysis/2026-05-19-astro-migration-rfc.md`.

> A few items below need direct verification with the org/GitHub App owner (marked ⚠️) since they can't be confirmed from repo contents alone.

## Quick checklist

- [ ] Create `public/CNAME` containing `www.alt-cloud.org` (this file **doesn't currently exist** in the working tree)
- [ ] `site.config.mjs`: `preview: true` → `false`
- [ ] `site.config.mjs`: `blockSearchBots: true` → `false` (don't let it fall back to following `preview` — set it explicitly)
- [ ] `.github/workflows/deploy-pages.yml`: remove `feat/astro-migration` from the branch triggers + deploy condition
- [ ] `.github/workflows/lint.yml`: remove `feat/astro-migration` from the branch triggers
- [ ] Disable/remove `.github/workflows/update-blog-posts.yml` at the same time `docs/` is deleted
- [ ] Delete the `docs/` folder (legacy pre-Astro site)
- [ ] Configure all required secrets & variables in the `datum-cloud/awesome-alt-clouds` repo (see table in section C)
- [ ] ⚠️ Confirm the GitHub App (used by 5 admin workflows) is/gets installed on the `datum-cloud` org
- [ ] Switch the GitHub Pages source in Settings from "branch `/docs`" → "GitHub Actions"
- [ ] Verify the custom domain `www.alt-cloud.org` + "Enforce HTTPS" in Settings → Pages after the switch
- [ ] ⚠️ Carry over/replicate branch protection rules from the fork's `main` to the upstream repo's `main`
- [ ] Monitor for 48 hours after cutover (custom domain resolves, Fathom analytics still firing)

---

## A — Config file changes

### 1. `public/CNAME` (needs to be recreated)

This file **does not currently exist** — it was created in the initial Astro migration commit (`e950d3d`) containing `www.alt-cloud.org`, then changed to the fork's personal domain (`alt-cloud.ronggur.com`), then deleted entirely in commit `b6be5dd` ("feat(site): add preview config..."). `actions/deploy-pages@v4` reads a `CNAME` file at the artifact root to set the GitHub Pages custom domain — without it, the site will only be reachable at `datum-cloud.github.io/awesome-alt-clouds/`.

**Action:** create `public/CNAME` containing exactly:

```text
www.alt-cloud.org
```

### 2. `site.config.mjs`

Flip `preview: true` → `false`. Effects (verified in `astro.config.mjs`):

- `site` switches to `productionSite` (`https://www.alt-cloud.org`)
- `base` switches to `productionBase` (`undefined` — root path, not `/awesome-alt-clouds/`)
- `blockSearchBots` **defaults to whatever `preview` is** when not set explicitly — it's currently set explicitly to `true`, so it **must also be explicitly flipped to `false`**, otherwise search engines stay blocked in production. This is wired into both the `<meta name="robots">` tag in `src/layouts/Base.astro` and the build-time `src/pages/robots.txt.ts` endpoint, which emits `Disallow: /` while `blockSearchBots` is true.

### 3. `previewSite: "https://ronggur.github.io"` in `site.config.mjs`

The only hardcoded personal-fork string found anywhere in the codebase (grepped across all workflows, `package.json`, `astro.config.mjs`, `README.md`, `CONTRIBUTING.md`, `src/`). It becomes dead code once `preview: false`, so it isn't strictly required to change — but if datum-cloud wants its own fork-preview capability later, point it at `datum-cloud.github.io` instead.

### 4. `astro.config.mjs` and `package.json`

No changes needed — `astro.config.mjs` already derives everything from `site.config.mjs` correctly, and `package.json` has no `repository`/`homepage`/`bugs` fields hardcoded to the fork.

### 5. Fathom Analytics (`src/layouts/Base.astro`)

The site ID `ZQEMDUAQ` is hardcoded and unconditional (not gated by `preview`) — this appears to already be the real production Fathom site ID, so no change needed. **Side-effect worth noting:** this means the fork's preview deploys have presumably been sending real traffic into the production Fathom dashboard all along.

---

## B — GitHub Actions workflow changes

### 6. `.github/workflows/deploy-pages.yml`

Has an explicit inline TODO: `# DEV: feat/astro-migration + version tags — revert to main-only after Phase 6`. Three spots need updating:

- `on.push.branches: [main, feat/astro-migration]` → `[main]`
- `on.pull_request.branches: [main, feat/astro-migration]` → `[main]`
- The `deploy` job's `if:` condition checks `github.ref == 'refs/heads/feat/astro-migration'` as one of three OR'd conditions — remove that clause.

### 7. `.github/workflows/lint.yml`

Same pattern, same comment style (`# DEV: feat/astro-migration + version tags — align with deploy-pages.yml`): both `on.push.branches` and `on.pull_request.branches` are `[main, feat/astro-migration]` → `[main]`.

### 8. Other workflows — no trigger changes needed

`evaluate-submission.yml`, `split-submission.yml`, `admin-approve-submission.yml`, `revalidate-submission.yml`, `watchlist.yml`, `close-issue-on-pr-close.yml`, `auto-label-submission.yml`, `backfill-profiles.yml` — all trigger on `issues`/`issue_comment`/`pull_request: closed`/`workflow_dispatch` events, not branch pushes, and none contain fork-specific logic (no `github.repository_owner` or fork conditionals anywhere).

### 9. `update-blog-posts.yml` — must be disabled alongside deleting `docs/`

This workflow patches the Resources modal in `docs/index.html`, and **runs on a live daily cron** (`0 6 * * *`, active — not disabled, contradicting an older RFC note that claimed this cron was off "until Phase 3"; it's since been re-enabled). `CONTRIBUTING.md` itself says: *"both can run in parallel until Phase 6 cutover retires `docs/`."* **This workflow must be disabled/removed in the same cutover step that deletes `docs/`**, otherwise it will fail every day trying to patch a file that no longer exists.

### 10. `auto-label-submission.yml`

Already uses `context.repo.owner`/`context.repo.repo` generically — no hardcoded owner, works correctly in any repo unchanged.

---

## C — Secrets & variables that must be (re)configured in the destination repo

None of these can be assumed to already exist in `datum-cloud/awesome-alt-clouds` unless previously configured for other purposes:

| Secret/Variable | Type | Used by |
| - | - | - |
| `APP_ID` | secret | `admin-approve-submission.yml`, `close-issue-on-pr-close.yml`, `update-blog-posts.yml`, `watchlist.yml`, `revalidate-submission.yml` (5 workflows) |
| `APP_PRIVATE_KEY` | secret | same 5 workflows |
| `ANTHROPIC_API_KEY` | secret | `admin-approve-submission.yml`, `backfill-profiles.yml`, `evaluate-submission.yml`, `split-submission.yml` |
| `QWEN_BASE_URL` | secret | same 4 workflows |
| `LLM_PROVIDER` | repo **variable** (not a secret) | same 4 workflows — optional, defaults to `claude` (falls back to `vars.LLM_PROVIDER`) if unset |
| `STRAPI_URL` | secret | `update-blog-posts.yml` only |
| `STRAPI_TOKEN` | secret | `update-blog-posts.yml` only |

`GITHUB_TOKEN` (built-in, no setup needed) is used elsewhere as usual.

---

## D — GitHub repo settings / operational steps (not code)

### 11. Switch the GitHub Pages source

Per the RFC's own migration-progress table: *"Pages source needs flipping from 'branch /docs' → 'GitHub Actions'"*. A manual step in `datum-cloud/awesome-alt-clouds` → **Settings → Pages**, done once the workflow + CNAME changes above are merged.

### 12. ⚠️ GitHub App installation

The 5 workflows above (section C) assume a GitHub App (via `actions/create-github-app-token@v1`) is installed with write access on whichever repo runs them. **Can't be confirmed from this fork's code alone**: whether this App is already installed org-wide on `datum-cloud` (in which case only the secrets need adding), or only scoped to the personal fork (in which case it needs a fresh installation grant on `datum-cloud/awesome-alt-clouds` plus copying the secrets over). **Confirm directly with whoever administers the GitHub App before cutover.**

### 13. Verify custom domain + HTTPS after the switch

From the RFC's own risk table: *"Add `public/CNAME` with the exact domain string; verify in Pages settings + `dig` post-deploy."* After switching the Pages source, re-verify the custom domain and the "Enforce HTTPS" checkbox in Settings → Pages (GitHub sometimes needs a manual domain re-verification when the deploy mechanism changes).

### 14. ⚠️ Branch protection

No evidence in the workflow files of specific required-status-check names that would need re-adding — this lives in GitHub Settings, not in code, so it's outside what can be determined from repo contents alone. **Make sure whoever runs this merge carries over the `main` branch protection rules from the fork to whatever becomes the primary branch in the destination repo.**

---

## E — Files/directories to clean up

### 15. The `docs/` directory

The RFC explicitly marks it: *"⚠ RETIRED after cutover"*. Its current contents are only 3 files (`index.html`, `og-image.png`, `clouds.json`, 456K total) — already much smaller than a full legacy site, mostly hollowed out. Safe to delete **as long as it's done together with** disabling `update-blog-posts.yml` (section B.9), which patches `docs/index.html`.

---

## F — The RFC's own Phase 6 checklist (verbatim)

From `analysis/2026-05-19-astro-migration-rfc.md`:

- Migration table: *"6 — Production cutover | ⏳ pending | Pages source needs flipping from 'branch /docs' → 'GitHub Actions'"*
- Acceptance criteria: *"Phase 6 — Cutover. Pages source switched from 'branch main /docs' to 'GitHub Actions'. Custom domain `www.alt-cloud.org` still resolves. Fathom analytics still firing. Monitor for 48 h."*
- Roadmap: *"**6** | Production cutover: verify CNAME, switch Pages source, monitor | ½ day"*
- Risk table: *"Lose `alt-cloud.org` custom domain on cutover → Add `public/CNAME` with the exact domain string; verify in Pages settings + `dig` post-deploy"*
- Decision #2 (locked): *"Commit `clouds.json`/`llms*.txt` back to git? No — artifact-only. They're regenerated by every CI build."* — this is already correctly implemented, no action needed, just worth noting it's intentional/final rather than something "left behind" to fix.

---

## Suggested execution order

1. Open a PR containing: `public/CNAME`, the `site.config.mjs` flips (preview + blockSearchBots), the `deploy-pages.yml` + `lint.yml` trigger updates (removing `feat/astro-migration`), and the removal of `docs/` + `update-blog-posts.yml` together.
2. ⚠️ Confirm with the GitHub App admin: already installed on the `datum-cloud` org, or needs a fresh install.
3. Set all secrets/variables from the table in section C in `datum-cloud/awesome-alt-clouds` (Settings → Secrets and variables → Actions).
4. Merge the PR into `main` on the destination repo.
5. Switch the Pages source to "GitHub Actions" in Settings → Pages.
6. Verify: custom domain resolves (`dig www.alt-cloud.org`), HTTPS enforced, Fathom is still receiving traffic, the submission pipeline (`/approve`, `/watchlist`, `/revalidate`) still works with the new App token.
7. Monitor for 48 hours per the RFC's acceptance criteria.
