# Per-branch previews on Datum Compute

Status: **not run yet**. Ported from datum.net (`preview-datum.yml`,
`preview-cleanup.yml`, `preview-autoclean.yml`, `.github/scripts/preview.sh` and
its `docs/datum-compute-previews.md`), where the design, basic auth, name limits
and cleanup were verified on 2026-10-21. This repo differs in the image and the
runtime; see [Differences from datum.net](#differences-from-datumnet).

Each branch can get its own URL behind Basic Authentication, to review a design
or content change before it is merged. `deploy-datum.yml` (one workload,
`awesome-alt-clouds-uk`, deployed from `main`) and GitHub Pages are not touched.

## Use it

**For now (until `redesign` is merged):** previews run only for the `redesign`
branch, automatically on every push to it. The URL is in the run summary and on
the `datum-compute-preview` environment. The manual workflows (Run workflow,
cleanup) need the files on `main`, so until then remove the preview by hand if
needed:

```bash
datumctl compute destroy alt-cloud-pv-redesign-62ed61 --project datum-cloud --yes
datumctl delete secret alt-cloud-pv-redesign-62ed61-basic-auth -n default --project datum-cloud
datumctl delete securitypolicy alt-cloud-pv-redesign-62ed61 -n default --project datum-cloud
```

Once `redesign` is merged, deleting the branch removes its preview (autoclean),
and the push trigger in `preview-datum.yml` should be dropped. From then on:

1. Actions -> **Preview Datum Compute** -> Run workflow. Pick the branch in
   "Use workflow from" (or type it in `branch`). Leave `project` empty.
2. The run summary (and the `datum-compute-preview` environment) shows the
   `*.datumproxy.net` URL. Open it with the shared preview credentials.
3. Push more commits and run it again: the same workload and URL are updated.
4. When done, run **Preview Datum Compute cleanup** with `action: destroy` and
   the branch, or just delete the branch (autoclean). `action: list` shows every
   running preview.

Each preview holds one HTTPProxy of the project's quota (25, shared with
datum.net, agents and every other workload), so remove previews you no longer
need.

## How it works

```text
Preview Datum Compute (branch, project, location)
  build job (contents: read, packages: write; no Datum credentials)
    1. Check the naming rules; derive <slug>, the workload and the image tag
    2. Check out the branch (full history), regenerate clouds.json / llms*.txt /
       watchlist.json, npm ci, npm run build
    3. datumctl compute build (Dockerfile.datum) and push
       ghcr.io/datum-cloud/awesome-alt-clouds-compute:preview-<slug>-<sha7>-<run>
  deploy job (environment datum-compute-preview)
    4. Check PREVIEW_BASIC_AUTH is set and the image is publicly pullable
    5. Deploy alt-cloud-pv-<slug> (unikernel, 1 instance), then apply the
       basic-auth Secret + SecurityPolicy in the same step
    6. Check the workload runs the new image
    7. Verify: no credentials -> 401, with credentials -> 200
       (if 5-7 fail or the run is cancelled, destroy the workload: fail closed)
```

| Item              | Name                                      |
| ----------------- | ----------------------------------------- |
| Workload          | `alt-cloud-pv-<slug>`                     |
| Image tag         | `preview-<slug>-<sha7>-<run number>`      |
| Basic-auth Secret | `alt-cloud-pv-<slug>-basic-auth`          |
| SecurityPolicy    | `alt-cloud-pv-<slug>`                     |
| Concurrency group | `alt-cloud-preview-<branch>`              |

`<slug>` is the branch name lowercased with runs of other characters turned
into `-`, cut to fit, plus `-` and 6 hex characters of the SHA-256 of the full
branch name. Workload names are capped at 32 characters (datum.net measured that
38 characters run but answer `503`). Every command that changes or deletes a
resource refuses `awesome-alt-clouds-uk` and any name outside `alt-cloud-pv-`;
`preview.sh self-test` checks this at the start of every job.

Basic auth is the same pair of resources the console creates: a Secret
`<workload>-basic-auth` with one `.htpasswd` line (`user:{SHA}<base64 sha1>`)
and an Envoy Gateway `SecurityPolicy` on `Gateway/<workload>`. `datumctl` 0.23
has no auth flag on `compute deploy`, so `preview.sh auth` applies them with
`datumctl apply` right after the deploy. A brand-new workload is public for the
short time between the rollout and the policy reaching the edge.

## Differences from datum.net

- **Image.** datum.net builds its Node server with `docker build`. Here the site
  is built on the runner (it needs Python, Node 26 and the full git history) and
  packaged with `datumctl compute build` from `Dockerfile.datum`, exactly as in
  `deploy-datum.yml`. `compute build` runs locally, so the build job needs no
  Datum login and the branch's code never runs next to the Datum credentials.
- **Runtime.** Unikernel, port 3000, one instance, to preview what production
  runs. Unikernel instances have answered `503` for a few minutes after a
  rollout (docs/datum-compute.md), so the authenticated check retries for 6
  minutes instead of 5.
- **No app Secret.** The static server needs no environment values, so there is
  no `--env-from-secret` and no Secret check.
- **Prefix.** `alt-cloud-pv-` instead of `datum-net-`, so no existing workload
  in the shared `datum-cloud` project can ever match it.
- **Autoclean** also skips `submission-*` and `graduation-*` branches: the
  submission pipeline creates and deletes one per merged entry, and they never
  have a preview.
- **Build mode.** Previews build like production (`site.config.mjs`
  `preview: false`), so draft MDX profiles are not shown and canonical URLs point
  at www.alt-cloud.org. The `preview: true` mode is for the GitHub Pages fork,
  whose base path (`/awesome-alt-clouds/`) would break on a root URL. Basic auth
  keeps crawlers out.

## One-time setup

1. Create the GitHub environment **`datum-compute-preview`** (Settings ->
   Environments). Allow all branches, since previews run from feature branches.
   Add required reviewers if previews should be approved.
2. Add the environment secret **`PREVIEW_BASIC_AUTH`** = `user:password`. There
   is no default: without it the deploy job stops before anything is deployed.
3. `DATUM_SA_CREDENTIALS` is already a repository secret (used by
   `deploy-datum.yml`); environment jobs can read it. Set it on the environment
   instead to use a separate service account.
4. The GHCR package `awesome-alt-clouds-compute` is already public with this
   repository on the Write role (see docs/datum-compute.md). Preview tags go to
   the same package, so **anyone can pull a preview image**, including unmerged
   code. Don't preview a branch whose content must stay private.
5. Merge the three workflows and `.github/scripts/preview.sh` to `main` first.
   GitHub only offers (and accepts) a `workflow_dispatch` run for a workflow
   that exists on the default branch, and the `delete` event of autoclean also
   runs the default branch's workflow. After that, a preview can be started for
   any branch.
6. Run a preview on a test branch, open the URL, then delete the branch and check
   that autoclean removed it.

## Security

- **Fail closed.** If auth cannot be confirmed (`401` without credentials and
  `200` with them), the run destroys the workload.
- **Shared project credentials.** The service account can change any workload in
  `datum-cloud`; the workflows protect the others only with name checks. A
  separate preview project with its own service account removes that risk (set
  the `project` input or the `DATUM_PROJECT` variable).
- **Forks.** Every job has `if: github.repository == 'datum-cloud/awesome-alt-clouds'`.
- `workflow_dispatch` runs the workflow from the selected ref, so a branch can
  change the workflow itself. Only people with write access can run it, and the
  deploy credentials sit behind the environment.
- Never register a preview URL as a webhook target; basic auth covers the whole
  load balancer.
