#!/usr/bin/env bash
# .github/scripts/preview.sh
# Names, basic auth, checks, and cleanup for per-branch Datum Compute previews.
# Ported from datum.net (.github/scripts/preview.sh). See docs/datum-compute-previews.md.
set -euo pipefail

DATUM_PROJECT="${DATUM_PROJECT:-datum-cloud}"
LOCATION="${LOCATION:-us-central-1}"
# Only previews use this prefix, so a preview command can never reach another
# workload in the shared project.
PREFIX="alt-cloud-pv-"
# Workloads that previews must never create, change, or destroy.
PROTECTED="awesome-alt-clouds-uk"

log() {
  printf '%s\n' "$*" >&2
}

die() {
  printf '::error::%s\n' "$*" >&2
  exit 1
}

# Instance names are <workload>-default-<location>-0 and must fit a 63
# character DNS label. datum.net found that workloads of 38 characters run but
# answer 503 (NoMatchingInterfaces) while 17 to 32 characters serve, so stop at 32.
max_workload() {
  local by_instance="$((63 - ${#LOCATION} - 11))"
  if [ "$by_instance" -lt 32 ]; then
    printf '%s\n' "$by_instance"
  else
    printf '%s\n' 32
  fi
}

# <readable part of the branch>-<6 hex of sha256(branch)>, sized so the
# workload name fits max_workload.
slug_for() {
  python3 -I -c '
import hashlib, re, sys
branch = sys.argv[1].removeprefix("refs/heads/")
if not branch:
    raise SystemExit("branch is empty")
room = int(sys.argv[2])
if room < 1:
    raise SystemExit("location name leaves no room for a slug")
norm = re.sub(r"[^a-z0-9]+", "-", branch.lower())
norm = re.sub(r"-+", "-", norm).strip("-")
readable = norm[:room].rstrip("-") or "branch"
digest = hashlib.sha256(branch.encode()).hexdigest()[:6]
print(f"{readable}-{digest}")
' "$1" "$(($(max_workload) - ${#PREFIX} - 7))"
}

assert_safe() {
  local name="$1" protected
  for protected in $PROTECTED; do
    if [ "$name" = "$protected" ]; then
      log "refusing to touch ${name}"
      return 1
    fi
  done
  case "$name" in
    "$PREFIX"*) ;;
    *)
      log "${name} is outside the preview prefix ${PREFIX}"
      return 1
      ;;
  esac
  if ! printf '%s' "$name" | grep -qE '^[a-z][a-z0-9-]*[a-z0-9]$'; then
    log "${name} is not a valid resource name"
    return 1
  fi
  if [ "${#name}" -gt "$(max_workload)" ]; then
    log "${name} is longer than $(max_workload) characters"
    return 1
  fi
}

workload_for() {
  local workload
  workload="${PREFIX}$(slug_for "$1")"
  assert_safe "$workload" || die "unsafe preview name: ${workload}"
  printf '%s\n' "$workload"
}

# The current workload, from PREVIEW_WORKLOAD or derived from PREVIEW_BRANCH.
current_workload() {
  local workload="${PREVIEW_WORKLOAD:-}"
  if [ -z "$workload" ]; then
    [ -n "${PREVIEW_BRANCH:-}" ] || die "PREVIEW_BRANCH is empty"
    workload="$(workload_for "$PREVIEW_BRANCH")"
  fi
  assert_safe "$workload" || die "unsafe preview name: ${workload}"
  printf '%s\n' "$workload"
}

# PREVIEW_BASIC_AUTH is user:password. There is no default: a preview without
# a credential would be public.
credentials() {
  local creds="${PREVIEW_BASIC_AUTH:-}"
  local user="${creds%%:*}"
  local pass="${creds#*:}"
  if [ -z "$creds" ] || [ "$user" = "$creds" ] || [ -z "$user" ] || [ -z "$pass" ]; then
    die "PREVIEW_BASIC_AUTH must be set to user:password"
  fi
  if [ -n "${GITHUB_ACTIONS:-}" ]; then
    printf '::add-mask::%s\n' "$pass" >&2
  fi
  printf '%s\n' "$creds"
}

cmd_self_test() {
  local a long
  a="$(slug_for "feat/foo")"
  [ "$a" = "$(slug_for "feat/foo")" ] || die "slug is not stable"
  [ "$a" = "$(slug_for "refs/heads/feat/foo")" ] || die "refs/heads/ was not stripped"
  [ "$a" != "$(slug_for "feat-foo")" ] || die "two branches mapped to one slug"
  case "$a" in
    feat-foo-??????) ;;
    *) die "unexpected slug ${a}" ;;
  esac
  case "$(slug_for "???")" in
    branch-??????) ;;
    *) die "a branch of symbols did not fall back to branch-<hash>" ;;
  esac
  long="$(workload_for "feature/this-is-a-very-long-branch-name-that-must-be-truncated")"
  [ "${#long}" -le "$(max_workload)" ] || die "${long} is too long"
  ! assert_safe "awesome-alt-clouds-uk" 2> /dev/null || die "guard allowed awesome-alt-clouds-uk"
  ! assert_safe "other-app" 2> /dev/null || die "guard allowed a name outside the prefix"
  log "preview name checks passed"
}

# Writes step outputs for the selected branch. The run number keeps a re-run of
# the same commit on a new tag: Datum does not replace an instance whose image
# tag is unchanged.
cmd_names() {
  local branch="${PREVIEW_BRANCH:-}" slug workload sha tag
  [ -n "$branch" ] || die "PREVIEW_BRANCH is empty"
  slug="$(slug_for "$branch")"
  workload="${PREFIX}${slug}"
  assert_safe "$workload" || die "unsafe preview name: ${workload}"
  sha="${PREVIEW_SHA:-$(git rev-parse HEAD)}"
  tag="preview-${slug}-${sha::7}-${PREVIEW_RUN:-0}"
  printf 'slug=%s\n' "$slug"
  printf 'workload=%s\n' "$workload"
  printf 'tag=%s\n' "$tag"
  printf 'image=%s:%s\n' "${IMAGE_REPO:-ghcr.io/datum-cloud/awesome-alt-clouds-compute}" "$tag"
}

# Returns 0 if the resource exists, 1 if it does not, and fails on any other error.
resource_exists() {
  local kind="$1" name="$2" err
  err="$(mktemp)"
  if datumctl get "$kind" "$name" -n default --project "$DATUM_PROJECT" -o name > /dev/null 2> "$err"; then
    rm -f "$err"
    return 0
  fi
  if grep -q 'NotFound' "$err"; then
    rm -f "$err"
    return 1
  fi
  cat "$err" >&2
  rm -f "$err"
  die "could not read ${kind}/${name}"
}

# Creates or updates <workload>-basic-auth and the Envoy SecurityPolicy on the
# workload's Gateway (the same two resources the console creates). The Gateway
# exists only after the first deploy.
cmd_auth() {
  local workload creds manifest status=0
  workload="$(current_workload)"
  creds="$(credentials)"
  manifest="$(mktemp)"
  chmod 600 "$manifest"
  PREVIEW_CREDS="$creds" PREVIEW_WORKLOAD="$workload" python3 -I -c '
import base64, hashlib, json, os, sys
user, password = os.environ["PREVIEW_CREDS"].split(":", 1)
workload = os.environ["PREVIEW_WORKLOAD"]
digest = hashlib.sha1(password.encode(), usedforsecurity=False).digest()
secret = {
    "apiVersion": "v1",
    "kind": "Secret",
    "metadata": {"name": workload + "-basic-auth", "namespace": "default"},
    "type": "Opaque",
    "stringData": {".htpasswd": user + ":{SHA}" + base64.b64encode(digest).decode()},
}
policy = {
    "apiVersion": "gateway.envoyproxy.io/v1alpha1",
    "kind": "SecurityPolicy",
    "metadata": {"name": workload, "namespace": "default"},
    "spec": {
        "targetRefs": [{"group": "gateway.networking.k8s.io", "kind": "Gateway", "name": workload}],
        "basicAuth": {"users": {"group": "", "kind": "Secret", "name": workload + "-basic-auth"}},
    },
}
sys.stdout.write(json.dumps(secret) + "\n---\n" + json.dumps(policy) + "\n")
' > "$manifest"
  datumctl apply -f "$manifest" --project "$DATUM_PROJECT" || status=$?
  rm -f "$manifest"
  [ "$status" -eq 0 ] || die "could not apply basic auth for ${workload}"
  log "basic auth applied for ${workload}"
}

# No credentials must give 401, the credentials must give 200. DNS and the edge
# lag a new instance, a new SecurityPolicy takes a few seconds to reach the
# edge, and unikernel instances have answered 503 for a few minutes after a
# rollout (docs/datum-compute.md), so both checks retry.
cmd_verify() {
  local url="${PREVIEW_URL:-}" creds code="000" i
  [ -n "$url" ] || die "PREVIEW_URL is empty"
  creds="$(credentials)"
  for i in $(seq 1 24); do
    code="$(curl -s -o /dev/null -m 15 -w '%{http_code}' "${url}/" || true)"
    log "attempt ${i}: GET / without credentials -> ${code:-000}"
    [ "$code" = 401 ] && break
    if [ "$code" = 200 ]; then
      log "::warning::${url} answered 200 without credentials; waiting for the auth policy"
    fi
    sleep 5
  done
  [ "$code" = 401 ] || die "expected 401 without credentials within 2 minutes, got ${code:-000}"
  for i in $(seq 1 24); do
    code="$(curl -s -o /dev/null -m 15 -u "$creds" -w '%{http_code}' "${url}/" || true)"
    log "attempt ${i}: GET / with credentials -> ${code:-000}"
    [ "$code" = 200 ] && return 0
    sleep 15
  done
  die "expected 200 with credentials within 6 minutes, got ${code:-000}"
}

delete_if_present() {
  local kind="$1" name="$2"
  if resource_exists "$kind" "$name"; then
    datumctl delete "$kind" "$name" -n default --project "$DATUM_PROJECT"
    log "deleted ${kind}/${name}"
  else
    log "${kind}/${name} is already gone"
  fi
}

# compute destroy leaves the basic-auth Secret and the SecurityPolicy, so
# delete them explicitly. Safe to run more than once.
cmd_cleanup() {
  local workload
  workload="$(current_workload)"
  if resource_exists workload "$workload"; then
    datumctl compute destroy "$workload" --project "$DATUM_PROJECT" --yes
    log "destroyed workload ${workload}"
  else
    log "workload ${workload} is already gone"
  fi
  delete_if_present secret "${workload}-basic-auth"
  delete_if_present securitypolicy "$workload"
}

# Prints the previews in the project as a Markdown table.
cmd_list() {
  datumctl get workloads -n default --project "$DATUM_PROJECT" -o json |
    PREFIX="$PREFIX" PROTECTED="$PROTECTED" python3 -I -c '
import json, os, sys
prefix = os.environ["PREFIX"]
protected = set(os.environ["PROTECTED"].split())
rows = []
for item in json.load(sys.stdin).get("items") or []:
    meta = item.get("metadata") or {}
    name = meta.get("name", "")
    if not name.startswith(prefix) or name in protected:
        continue
    images = []
    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "image" and isinstance(value, str):
                    images.append(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(item.get("spec") or {})
    rows.append((meta.get("creationTimestamp", ""), name, images[0] if images else ""))
if not rows:
    print("No previews.")
    raise SystemExit
print("| Workload | Created | Image |")
print("| --- | --- | --- |")
for created, name, image in sorted(rows):
    print(f"| `{name}` | {created} | `{image}` |")
'
}

main() {
  case "${1:-}" in
    self-test) cmd_self_test ;;
    names) cmd_names ;;
    credentials-check) credentials > /dev/null ;;
    auth) cmd_auth ;;
    verify) cmd_verify ;;
    cleanup) cmd_cleanup ;;
    list) cmd_list ;;
    *) die "usage: preview.sh self-test|names|credentials-check|auth|verify|cleanup|list" ;;
  esac
}

main "$@"
