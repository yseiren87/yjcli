#!/usr/bin/env bash
# Release yjcli: version bump -> tests -> build + PyPI dry-run -> git commit/tag/push -> PyPI publish.
#
#   ./release.sh                  full release: checks run at once, then every input is asked
#                                 (bump level, commit message), then one "y" runs all steps
#   ./release.sh --publish-only   re-run build + publish for an already tagged HEAD
#
# Prompts take "y" (continue) or "exit" (quit), case-insensitive.
# Tokens are read from .env.release (git-ignored) or the environment:
#   UV_PUBLISH_TOKEN=pypi-...        required for the PyPI dry-run and publish
#   GITHUB_TOKEN=github_pat_...      optional; used only for git push when set
set -euo pipefail

cd "$(dirname "$0")"
ROOT="$(pwd)"
PACKAGE="yjcli"
BRANCH="main"
TAG_PREFIX="release/"

# ----------------------------------------------------------------------------- output

if [ -t 1 ] || [ -t 2 ]; then
  BOLD=$'\033[1m'; DIM=$'\033[2m'; RESET=$'\033[0m'
  RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; CYAN=$'\033[36m'
  PROMPT=$'\033[1;30;43m'   # bold black on yellow
else
  BOLD=""; DIM=""; RESET=""; RED=""; GREEN=""; YELLOW=""; CYAN=""; PROMPT=""
fi

info()  { printf '  %s\n' "$*"; }
ok()    { printf '  %s✔ %s%s\n' "$GREEN" "$*" "$RESET"; }
warn()  { printf '  %s! %s%s\n' "$YELLOW" "$*" "$RESET"; }
fail()  { printf '\n  %s✘ %s%s\n\n' "$RED" "$*" "$RESET" >&2; cleanup_and_exit 1; }

STEP_TOTAL=5
step() {
  printf '\n%s━━━ Step %s/%s · %s ━━━%s\n' "$CYAN$BOLD" "$1" "$STEP_TOTAL" "$2" "$RESET"
}
phase() {
  printf '\n%s━━━ %s ━━━%s\n' "$CYAN$BOLD" "$1" "$RESET"
}

# Prompt framed by blank lines so it stands out; prints only the lowercased
# answer on stdout (the prompt itself goes to stderr, outside $(...) capture).
read_answer() {
  local question="$1" choices="$2" answer
  {
    printf '\n\n'
    printf '  %s  ▶ %s  %s\n' "$PROMPT" "$question" "$RESET"
    printf '  %s%s%s\n' "$BOLD" "$choices" "$RESET"
    printf '  %s>%s ' "$BOLD$YELLOW" "$RESET"
  } >&2
  if ! IFS= read -r answer; then
    printf '\n' >&2
    answer="exit"
  fi
  printf '\n\n' >&2
  printf '%s' "$answer" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]'
}

# Free-text prompt (keeps case and inner spaces); "exit" quits, empty asks again.
read_text() {
  local question="$1" hint="$2" answer
  while true; do
    {
      printf '\n\n'
      printf '  %s  ▶ %s  %s\n' "$PROMPT" "$question" "$RESET"
      printf '  %s%s%s\n' "$BOLD" "$hint" "$RESET"
      printf '  %s>%s ' "$BOLD$YELLOW" "$RESET"
    } >&2
    if ! IFS= read -r answer; then
      answer="exit"
    fi
    printf '\n\n' >&2
    answer="$(printf '%s' "$answer" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    if [ "$(printf '%s' "$answer" | tr '[:upper:]' '[:lower:]')" = "exit" ]; then
      info "Exited by user." >&2
      return 1
    fi
    if [ -n "$answer" ]; then
      printf '%s' "$answer"
      return 0
    fi
    warn "Please type a message or exit." >&2
  done
}

confirm() {
  local answer
  while true; do
    answer="$(read_answer "$1" "Type  y  to continue  ·  exit  to quit")"
    case "$answer" in
      y) return 0 ;;
      exit) info "Exited by user."; cleanup_and_exit 0 ;;
      *) warn "Please type y or exit." ;;
    esac
  done
}

# ----------------------------------------------------------------------------- state / rollback

VERSION_CHANGED=0   # version bumped but not committed yet
OLD_VERSION=""
UNPUSHED=0          # local commits ahead of origin before the release commit
COMMITTED=0
PUSHED=0
PUBLISHED=0
NEW_VERSION=""

cleanup_and_exit() {
  local code="$1"
  if [ "$VERSION_CHANGED" -eq 1 ] && [ "$COMMITTED" -eq 0 ]; then
    uv version -q "$OLD_VERSION" --no-sync 2>/dev/null || true
    info "Reverted the version to ${OLD_VERSION} (other uncommitted changes are untouched)."
  fi
  if [ "$COMMITTED" -eq 1 ] && [ "$PUSHED" -eq 0 ]; then
    warn "Commit and tag ${TAG_PREFIX}${NEW_VERSION} exist locally but were not pushed."
    info "Undo with: git tag -d ${TAG_PREFIX}${NEW_VERSION} && git reset --hard HEAD~1"
  fi
  if [ "$PUSHED" -eq 1 ] && [ "$PUBLISHED" -eq 0 ]; then
    warn "${TAG_PREFIX}${NEW_VERSION} is pushed but not on PyPI. Publish later with: ./release.sh --publish-only"
  fi
  exit "$code"
}
trap 'cleanup_and_exit 130' INT

# ----------------------------------------------------------------------------- helpers

load_tokens() {
  if [ -f .env.release ]; then
    set -a
    # shellcheck disable=SC1091
    . ./.env.release
    set +a
    ok "Loaded tokens from .env.release"
  fi
  if [ -z "${UV_PUBLISH_TOKEN:-}" ]; then
    fail "UV_PUBLISH_TOKEN is not set (put it in .env.release or export it)."
  fi
  ok "PyPI token: set"
  if [ -n "${GITHUB_TOKEN:-}" ]; then
    ok "GitHub token: set (used for git push)"
  else
    info "GitHub token: not set (git push uses your existing git credentials)"
  fi
}

project_version() { uv version --short 2>/dev/null; }

published_version() {
  curl -fsS --max-time 10 "https://pypi.org/pypi/${PACKAGE}/json" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["info"]["version"])'
}

on_pypi() {
  curl -fs --max-time 10 -o /dev/null "https://pypi.org/pypi/${PACKAGE}/$1/json"
}

newer() {  # newer <a> <b>: true when version a > version b
  python3 -c 'import sys
k = lambda v: [int(x) for x in v.split("+")[0].split(".")]
sys.exit(0 if k(sys.argv[1]) > k(sys.argv[2]) else 1)' "$1" "$2"
}

bump() {  # bump <version> <major|minor|fix>
  local major minor patch
  IFS=. read -r major minor patch <<<"$1"
  patch="${patch%%[!0-9]*}"
  case "$2" in
    major) echo "$((major + 1)).0.0" ;;
    minor) echo "${major}.$((minor + 1)).0" ;;
    fix)   echo "${major}.${minor}.$((patch + 1))" ;;
  esac
}

git_push() {
  if [ -n "${GITHUB_TOKEN:-}" ]; then
    # One-off auth header via env (not argv, not saved to git config).
    local auth
    auth="$(printf 'x-access-token:%s' "$GITHUB_TOKEN" | base64 | tr -d '\n')"
    GIT_CONFIG_COUNT=1 \
    GIT_CONFIG_KEY_0="http.https://github.com/.extraheader" \
    GIT_CONFIG_VALUE_0="AUTHORIZATION: basic ${auth}" \
      git push "$@"
  else
    git push "$@"
  fi
}

build_and_dry_run() {
  rm -rf dist
  uv build -q --out-dir dist
  ok "Built:"
  for f in dist/*; do info "  $(basename "$f")"; done
  uv publish --dry-run dist/* >/dev/null
  ok "PyPI dry-run passed (nothing uploaded)."
}

publish() {
  uv publish dist/*
  PUBLISHED=1
  ok "Published ${PACKAGE} ${NEW_VERSION} to PyPI."
  info "https://pypi.org/project/${PACKAGE}/${NEW_VERSION}/"
  info "Install/upgrade: uv tool upgrade ${PACKAGE}"
}

# ----------------------------------------------------------------------------- flows

preflight() {
  for cmd in uv git curl python3; do
    command -v "$cmd" >/dev/null || fail "missing command: $cmd"
  done
  load_tokens
  local branch
  branch="$(git branch --show-current)"
  [ "$branch" = "$BRANCH" ] || fail "Releases are cut from '$BRANCH' (current: '$branch')."
  git fetch -q origin "$BRANCH" --tags
  local behind ahead
  behind="$(git rev-list --count "HEAD..origin/$BRANCH")"
  ahead="$(git rev-list --count "origin/$BRANCH..HEAD")"
  [ "$behind" -eq 0 ] \
    || fail "Local $BRANCH is $behind commit(s) behind origin/$BRANCH. Pull first."
  ok "On $BRANCH, not behind origin."
  if [ -n "$(git status --porcelain)" ]; then
    warn "Uncommitted changes will be included in the release commit:"
    git status --short | sed 's/^/      /'
  fi
  UNPUSHED="$ahead"
  if [ "$ahead" -gt 0 ]; then
    warn "$ahead unpushed commit(s) will be pushed together with the release:"
    git log --format='      %h %s' "origin/$BRANCH..HEAD"
  fi
}

full_release() {
  printf '\n%s  yjcli release%s\n' "$BOLD" "$RESET"

  # ---- checks: run right away, nothing is changed
  phase "Preflight checks"
  preflight
  local current published
  current="$(project_version)"
  published="$(published_version)" || fail "Could not read the latest version from PyPI."
  info "Current version : ${BOLD}${current}${RESET}  (pyproject.toml — bump is based on this)"
  info "Latest on PyPI  : ${BOLD}${published}${RESET}"

  # ---- input: everything is asked first, nothing runs yet
  phase "Input"
  info "major → $(bump "$current" major)   minor → $(bump "$current" minor)   fix → $(bump "$current" fix)"
  local answer candidate
  while true; do
    answer="$(read_answer "Which part to bump?" "Type  major  ·  minor  ·  fix  ·  exit")"
    case "$answer" in
      major|minor|fix) ;;
      exit) info "Exited by user."; cleanup_and_exit 0 ;;
      *) warn "Please type major, minor, fix or exit."; continue ;;
    esac
    candidate="$(bump "$current" "$answer")"
    if ! newer "$candidate" "$published"; then
      warn "$candidate is not newer than PyPI's $published."
    elif on_pypi "$candidate"; then
      warn "$candidate is already on PyPI."
    elif git rev-parse -q --verify "refs/tags/${TAG_PREFIX}${candidate}" >/dev/null; then
      warn "Tag ${TAG_PREFIX}${candidate} already exists."
    else
      NEW_VERSION="$candidate"
      break
    fi
  done
  ok "Selected: ${current} → ${BOLD}${NEW_VERSION}${RESET}"
  local message
  message="$(read_text "Commit message?" "Type the message (e.g. release: ${NEW_VERSION} — ...)  ·  exit  to quit")" \
    || cleanup_and_exit 0

  # ---- plan: one confirmation for everything below
  phase "Plan"
  info "Version : ${current} → ${BOLD}${NEW_VERSION}${RESET}"
  info "Tests   : unit tests + scripts/e2e.sh"
  info "Build   : sdist + wheel into dist/, PyPI dry-run"
  info "Commit  : every change below (git add -A; .gitignore'd files excluded) + the version bump"
  git status --short | sed 's/^/           /'
  info "Message : ${message}"
  info "Tag     : ${TAG_PREFIX}${NEW_VERSION}"
  info "Push    : origin ${BRANCH} + tag"
  if [ "$UNPUSHED" -gt 0 ]; then
    info "          includes ${UNPUSHED} earlier unpushed commit(s):"
    git log --format='           %h %s' "origin/$BRANCH..HEAD"
  fi
  info "Publish : ${PACKAGE} ${NEW_VERSION} to PyPI"
  warn "PyPI does not allow re-uploading ${NEW_VERSION} once published."
  confirm "Run all of the above?"

  # ---- run: no more questions; a failure stops here and rolls back what it can
  step 1 "Version bump"
  OLD_VERSION="$current"
  VERSION_CHANGED=1
  uv version -q "$NEW_VERSION" --no-sync
  ok "Version: ${current} → ${BOLD}${NEW_VERSION}${RESET}"

  step 2 "Tests"
  uv run -q python -m unittest discover -s tests || fail "Unit tests failed."
  scripts/e2e.sh || fail "E2E scenarios failed (see sandbox/)."
  ok "All tests passed."

  step 3 "Build + PyPI dry-run"
  build_and_dry_run

  step 4 "Git commit, tag, push"
  git add -A
  git commit -q -m "$message"
  git tag "${TAG_PREFIX}${NEW_VERSION}"
  COMMITTED=1
  git_push -q origin "$BRANCH" "refs/tags/${TAG_PREFIX}${NEW_VERSION}" || fail "git push failed."
  PUSHED=1
  ok "Pushed ${BRANCH} and ${TAG_PREFIX}${NEW_VERSION}."

  step 5 "Publish to PyPI"
  publish || fail "uv publish failed."
  printf '\n  %s%sRelease %s done.%s\n\n' "$GREEN" "$BOLD" "$NEW_VERSION" "$RESET"
}

publish_only() {
  STEP_TOTAL=3
  printf '\n%s  yjcli release · publish only%s\n' "$BOLD" "$RESET"

  step 1 "Checks"
  confirm "Run checks?"
  for cmd in uv git curl python3; do
    command -v "$cmd" >/dev/null || fail "missing command: $cmd"
  done
  load_tokens
  NEW_VERSION="$(project_version)"
  [ -z "$(git status --porcelain)" ] || fail "Working tree is not clean."
  git rev-parse -q --verify "refs/tags/${TAG_PREFIX}${NEW_VERSION}" >/dev/null \
    || fail "Tag ${TAG_PREFIX}${NEW_VERSION} not found. Run the full release instead."
  [ "$(git rev-parse HEAD)" = "$(git rev-parse "${TAG_PREFIX}${NEW_VERSION}^{commit}")" ] \
    || fail "HEAD is not at ${TAG_PREFIX}${NEW_VERSION}. Check out that tag first."
  on_pypi "$NEW_VERSION" && fail "$NEW_VERSION is already on PyPI."
  ok "HEAD is ${TAG_PREFIX}${NEW_VERSION}, not on PyPI yet."
  PUSHED=1

  step 2 "Build + PyPI dry-run"
  confirm "Build and dry-run?"
  build_and_dry_run

  step 3 "Publish to PyPI"
  warn "PyPI does not allow re-uploading ${NEW_VERSION} once published."
  confirm "Publish ${PACKAGE} ${NEW_VERSION} to PyPI?"
  publish || fail "uv publish failed."
  printf '\n  %s%sPublished %s.%s\n\n' "$GREEN" "$BOLD" "$NEW_VERSION" "$RESET"
}

case "${1:-}" in
  "") full_release ;;
  --publish-only) publish_only ;;
  -h|--help) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//' ;;
  *) echo "unknown option: $1 (see --help)"; exit 2 ;;
esac
