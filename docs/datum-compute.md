# Deploy alt-cloud.org to Datum Compute (unikernel test)

Status: **test deployment**. The site is built as a static Astro site and served from a
unikernel workload on Datum Compute. GitHub Pages (`deploy-pages.yml`) stays the
production deploy. **No DNS is changed**: the workload answers only on its
generated `*.datumproxy.net` URL.

| Item     | Value                                                              |
| -------- | ------------------------------------------------------------------ |
| Project  | `datum-cloud`                                                      |
| Workload | `awesome-alt-clouds-uk` (namespace `default`)                      |
| Runtime  | `unikernel`, instance type `datumcloud-d1-standard-2` (the default) |
| Location | `us-central-1` and `us-east-1`, 1 instance each (2 in total)       |
| Image    | `ghcr.io/datum-cloud/awesome-alt-clouds-compute:sha-<sha>-<run>`   |
| Port     | `3000` (HTTP; the edge terminates TLS)                             |
| URL      | generated `https://<name>.datumproxy.net` (printed by the deploy)  |
| Workflow | `.github/workflows/deploy-datum.yml`                               |

## How it fits together

```text
Actions -> Deploy Datum Compute
  regenerate clouds.json / llms*.txt / watchlist.json, npm run build   (-> dist/)
  datumctl compute build  Dockerfile.datum  (dist/ + compute/server.js on bun-slim)
  push ghcr.io/datum-cloud/awesome-alt-clouds-compute:sha-<sha>-<run>
  datumctl compute deploy --runtime-class unikernel
  check the workload is Available, then smoke-test the URL
```

- The site is built **outside** Docker, so the unikernel image only holds the
  finished `dist/` and `compute/server.js`. The build needs Python, Node 26 and the
  full git history (`dateAdded` comes from `git log -p`), none of which belong in a
  unikernel root filesystem. `.dockerignore` keeps everything else out of the build
  context.
- Datum does not replace an instance when the image tag is unchanged, so every run
  uses a new tag (`sha-<short sha>-<run number>`).
- A workload keeps its runtime class. To try general-purpose instead, deploy under
  a new name.

### Triggers

The workflow runs next to `deploy-pages.yml` and does not change it. Both fire on the
same events and run in parallel as independent workflows, so one failing never blocks
the other:

- a push to `main` (this includes every merged submission PR),
- a `v*` tag,
- `workflow_dispatch` by hand (inputs: `project`, `location`).

Pull requests build only on Pages and never deploy here.

- Runs are serialised by the `datum-compute` concurrency group with
  `cancel-in-progress: false`. A run that is waiting is replaced by a newer one, so a
  burst of merges ends with a deploy of the latest commit.
- Each run builds the site again (about 2.5 minutes end to end). Reusing the Pages
  artifact would save that, but it would couple the two workflows, which is what this
  setup avoids.
- Neither workflow manages DNS. The Datum workload is reachable only on its generated
  `*.datumproxy.net` URL. It has no access control of its own; to lock it, set
  basic auth on the load balancer (`datumctl alb auth set`).

## The static server (`compute/server.js`)

A small Bun server, because the unikernel root filesystem has no shell and no Node.

- Listens on `::` port `3000`. Datum networks are IPv6 only, and an IPv4-only socket
  starts but never answers.
- Astro builds with `format: "directory"`, so `/foo` and `/foo/` both map to
  `dist/foo/index.html`. Path traversal is rejected. `/healthz` answers `ok`.
- **Compression.** Text responses (HTML, CSS, JS, JSON, XML, SVG, plain text) of at
  least 1 KiB are compressed with brotli or gzip, whichever `Accept-Encoding` allows
  (`q=0` is respected), with `Vary: Accept-Encoding`. Compressed bodies are cached in
  memory (capped at 64 MiB), because `dist/` never changes while an instance runs.
  The home page is 1.49 MB of HTML; measured locally it becomes **66.6 KB with
  brotli and 86.8 KB with gzip**. Without this the page took 2-4 s to download.
- **CORS.** Every response carries `Access-Control-Allow-Origin: *`, as GitHub Pages
  does, so `clouds.json` and `llms.txt` can be fetched from other origins.
- **No access control.** The server does not check credentials. Basic auth is a load
  balancer setting (`datumctl alb auth set`), checked by Envoy at the edge.

## One-time setup

1. **Service account** with edit access to the `datum-cloud` project; save its
   credentials JSON as the repository secret `DATUM_SA_CREDENTIALS` (Settings ->
   Secrets and variables -> Actions). No GitHub environment is used.
2. **GHCR package** `awesome-alt-clouds-compute` must be **public** (the workload
   pulls anonymously) and this repository needs the **Write** role under "Manage
   Actions access". GHCR creates new packages as private and visibility cannot be
   changed through the API. Set both in
   https://github.com/orgs/datum-cloud/packages/container/awesome-alt-clouds-compute/settings.
3. Optional: the `DATUM_PROJECT` repository variable.

Check that Compute is enabled: `datumctl compute access --project datum-cloud`.

## Smoke test

After the rollout the workflow requires, in this order:

1. `GET /` returns `200` at least 3 times within 20 attempts, 15 s apart. The edge
   can answer `503` for a few minutes after an instance is replaced.
2. `/llms.txt`, `/clouds.json`, `/robots.txt` and a category page return `200`.
3. `GET /` with `Accept-Encoding: br, gzip` returns a `Content-Encoding`.
4. `GET /clouds.json` returns `Access-Control-Allow-Origin: *`.

## Build and test the image locally

The compute plugin must be new enough for `--buildkit-host`
(`datumctl plugin install compute@v0.12.10`). The default Docker driver cannot
export an OCI image, so use a `docker-container` BuildKit:

```bash
python3 scripts/parse_readme_to_json.py README.md public/clouds.json
python3 scripts/generate_llms.py public/clouds.json public/
python3 scripts/generate_watchlist_json.py
npm ci && npm run build

docker buildx create --name dc --driver docker-container --bootstrap
datumctl compute build --analyze \
  --buildkit-host docker-container://buildx_buildkit_dc0 \
  --output ./uk-image.tar .          # or --push --output ghcr.io/...:<tag>
```

Regenerating `public/clouds.json` changes a tracked file; run `git checkout
public/clouds.json` afterwards. To try the server without Docker, copy
`compute/server.js` next to a `dist/` folder and run
`PORT=3000 bun server.js`.

## Check the workload

```bash
datumctl get workload awesome-alt-clouds-uk -n default --project datum-cloud
datumctl get httpproxy awesome-alt-clouds-uk -n default --project datum-cloud
datumctl get networkservice awesome-alt-clouds-uk -n default --project datum-cloud
datumctl compute logs awesome-alt-clouds-uk --project datum-cloud
```

## Test log

**Run 1** (`sha-cf1a38b-1`, unikernel, no auth, no compression): every step passed,
including the smoke test. Control plane was healthy: workload `Available`
(`AvailablePlacementFound`), HTTPProxy `Accepted`/`Programmed`, certificates ready
(shared wildcard), network service `Ready` with 1 interface in 1 location. The
instance log showed `Started server: http://:::3000`.

**Reliability.** Sampling the URL by hand gave mixed results:

| When (after the rollout) | Result                                                      |
| ------------------------ | ----------------------------------------------------------- |
| first minutes            | 12 requests to `/`: 2 x `200`, 10 x `503`                  |
| ~5-10 minutes            | mostly timeouts at 8 s (`/` took 2-4 s when it did answer)  |
| later                    | 6/6 `200` on `/`; 25/25 `200` on `/robots.txt`, interleaved with 25/25 on a general-purpose control workload |

So the early `503`s did clear, and the later failures overlap with the slow,
uncompressed 1.49 MB home page and a short client timeout, which makes them
inconclusive. Other Datum sites (agents.datum.net, datum.net) reported the unikernel
runtime unstable behind `*.datumproxy.net`; this run neither confirms nor rules that
out. It needs a longer observation.

Latency baseline: time to first byte is about 0.9 s even for a 77-byte file, on both
the unikernel and the general-purpose control, so that part is the edge, not the app.

## Open questions and next steps

- Sample the URL for longer (for example 100+ requests over 30 minutes) to decide
  whether the early `503`s are only a post-rollout warm-up.
- Compare against a general-purpose workload under a new name (for example
  `awesome-alt-clouds-gp`) built from the regular `Dockerfile`.
- The workflow only runs from `main` now: it must be merged before the push trigger
  fires, and a manual run needs the file on the default branch too.
- Only after the deployment is judged stable: DNS (not part of this work).

## Cleanup

```bash
datumctl compute destroy awesome-alt-clouds-uk --project datum-cloud --yes
```

This removes the instances and the generated URL and frees the HTTPProxy quota.
