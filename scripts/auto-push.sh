#!/usr/bin/env zsh
# Watches the repo for changes, commits with descriptive messages, and pushes to origin.
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

INTERVAL="${AUTO_PUSH_INTERVAL:-30}"
LOG_FILE="$REPO_ROOT/.auto-push.log"
LOCK_FILE="$REPO_ROOT/.auto-push.lock"
BRANCH="${AUTO_PUSH_BRANCH:-main}"
REMOTE="${AUTO_PUSH_REMOTE:-origin}"

log() {
  print -r -- "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

scope_for_path() {
  case "$1" in
    apps/web/*) print -r -- web ;;
    apps/engine/*) print -r -- engine ;;
    packages/ui/*) print -r -- ui ;;
    packages/types/*) print -r -- types ;;
    packages/config/*) print -r -- config ;;
    supabase/*) print -r -- database ;;
    scripts/*) print -r -- tooling ;;
    *) print -r -- repo ;;
  esac
}

humanize_name() {
  local name="${1:t:r}"
  name="${name#.}"
  [[ -z "$name" ]] && name="${1:t}"
  print -r -- "${name//[-_]/ }"
}

summarize_area() {
  local scope="$1"
  shift
  local -a names=()
  local file base label

  for file in "$@"; do
    file="${file%/}"
    base="${file:t}"
    [[ -z "$base" ]] && continue
    [[ "$base" == "package.json" || "$base" == "__init__.py" || "$base" == "*.tsbuildinfo" ]] && continue
    [[ "$base" == *.tsbuildinfo ]] && continue
    label="$(humanize_name "$base")"
    [[ -z "$label" || "$label" == " " ]] && continue
    names+=("$label")
  done

  if (( ${#names[@]} == 0 )); then
    print -r -- "${scope} updates"
    return
  fi

  if (( ${#names[@]} <= 3 )); then
    print -r -- "${scope}: ${(j:, :)names}"
    return
  fi

  print -r -- "${scope}: ${names[1]}, ${names[2]}, and $((${#names[@]} - 2)) more"
}

build_commit_message() {
  local -a added=() modified=() deleted=()
  local -A scope_added scope_modified scope_deleted
  local -a status_lines=("${(@f)$(git status --porcelain)}")
  local line change_status path scope

  for line in "${status_lines[@]}"; do
    [[ -z "$line" ]] && continue
    change_status="${line[1,2]}"
    path="${line[4,-1]}"
    path="${path%/}"

    case "$change_status" in
      "??"|"A "|"A?"|"AM") added+=("$path") ;;
      " M"|"M "|"MM") modified+=("$path") ;;
      " D"|"D "|"D?"|"MD") deleted+=("$path") ;;
      *) modified+=("$path") ;;
    esac
  done

  if (( ${#added[@]} + ${#modified[@]} + ${#deleted[@]} == 0 )); then
    return 1
  fi

  local file
  for file in "${added[@]}"; do
    scope="$(scope_for_path "$file")"
    scope_added[$scope]+="$file"$'\n'
  done
  for file in "${modified[@]}"; do
    scope="$(scope_for_path "$file")"
    scope_modified[$scope]+="$file"$'\n'
  done
  for file in "${deleted[@]}"; do
    scope="$(scope_for_path "$file")"
    scope_deleted[$scope]+="$file"$'\n'
  done

  local -a parts=()
  local -a unique_scopes=()
  local s

  unique_scopes=(${(k)scope_added} ${(k)scope_modified} ${(k)scope_deleted})
  unique_scopes=(${(u)unique_scopes})

  local -a area_files=()
  local action part

  for s in "${unique_scopes[@]}"; do
    area_files=()

    if [[ -n "${scope_added[$s]:-}" ]]; then
      while IFS= read -r file; do
        [[ -n "$file" ]] && area_files+=("$file")
      done <<< "${scope_added[$s]}"
    fi
    if [[ -n "${scope_modified[$s]:-}" ]]; then
      while IFS= read -r file; do
        [[ -n "$file" ]] && area_files+=("$file")
      done <<< "${scope_modified[$s]}"
    fi
    if [[ -n "${scope_deleted[$s]:-}" ]]; then
      while IFS= read -r file; do
        [[ -n "$file" ]] && area_files+=("$file")
      done <<< "${scope_deleted[$s]}"
    fi

    if [[ -n "${scope_added[$s]:-}" && -z "${scope_modified[$s]:-}" && -z "${scope_deleted[$s]:-}" ]]; then
      action="Add"
    elif [[ -n "${scope_deleted[$s]:-}" && -z "${scope_added[$s]:-}" && -z "${scope_modified[$s]:-}" ]]; then
      action="Remove"
    else
      action="Update"
    fi

    parts+=("${action} $(summarize_area "$s" "${area_files[@]}")")
  done

  local subject="${(j:; :)parts}"
  if (( ${#subject} > 72 )); then
    subject="${subject[1,69]}..."
  fi

  print -r -- "$subject"
}

commit_and_push() {
  if [[ -f "$LOCK_FILE" ]] && kill -0 "$(<"$LOCK_FILE")" 2>/dev/null; then
    return 0
  fi

  print -r -- $$ > "$LOCK_FILE"
  trap 'rm -f "$LOCK_FILE"' EXIT

  if [[ -z "$(git status --porcelain)" ]]; then
    return 0
  fi

  local message
  message="$(build_commit_message)" || return 0

  git add -A

  if git diff --cached --quiet; then
    return 0
  fi

  git commit -m "$message"
  log "Committed: $message"

  if git push "$REMOTE" "$BRANCH"; then
    log "Pushed to $REMOTE/$BRANCH"
  else
    log "Push failed — will retry on next cycle"
    return 1
  fi
}

log "Auto-push watcher started (every ${INTERVAL}s on $REMOTE/$BRANCH)"

if [[ "${AUTO_PUSH_ONCE:-}" == "1" ]]; then
  commit_and_push || true
  exit 0
fi

while true; do
  commit_and_push || true
  sleep "$INTERVAL"
done
