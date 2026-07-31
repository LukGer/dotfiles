#!/bin/sh
#
# Claude Code configuration.
#
# Links the global CLAUDE.md and settings.json, then restores skills.
#
# Skills need care because this repo is public. Of the 46 installed, 45 come
# from other people's repositories (40 from mattpocock/skills alone) — those
# are NOT committed here; committing them would republish someone else's work
# and leave it to rot at whatever revision it was vendored at. Instead
# ai/skill-lock.json records where each came from and this script re-fetches
# them. Only self-authored skills live in ai/skills/.

set -e

DOTFILES="$HOME/.dotfiles"
AGENTS_SKILLS="$HOME/.agents/skills"
CLAUDE_SKILLS="$HOME/.claude/skills"

mkdir -p "$HOME/.claude" "$AGENTS_SKILLS" "$CLAUDE_SKILLS"

link() {
  src="$1"
  dst="$2"

  if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
    return
  fi
  if [ -e "$dst" ] && [ ! -L "$dst" ]; then
    mv "$dst" "$dst.backup"
    echo "  backed up $dst"
  fi
  rm -f "$dst"
  ln -s "$src" "$dst"
  echo "  linked $(basename "$dst")"
}

link "$DOTFILES/ai/CLAUDE.md" "$HOME/.claude/CLAUDE.md"
link "$DOTFILES/ai/settings.json" "$HOME/.claude/settings.json"
link "$DOTFILES/ai/skill-lock.json" "$HOME/.agents/.skill-lock.json"

# Self-authored skills.
for skill in "$DOTFILES"/ai/skills/*/; do
  [ -d "$skill" ] || continue
  name=$(basename "$skill")
  link "$DOTFILES/ai/skills/$name" "$AGENTS_SKILLS/$name"
done

# Third-party skills, restored from the lock file. Each distinct source repo is
# shallow-cloned once into a temp dir, then every skill sourced from it is
# copied out.
restore_skills() {
  lock="$DOTFILES/ai/skill-lock.json"
  [ -f "$lock" ] || return 0
  command -v python3 >/dev/null 2>&1 || {
    echo "  python3 not found — skipping skill restore"
    return 0
  }

  missing=$(python3 - "$lock" "$AGENTS_SKILLS" <<'PY'
import json, os, sys
lock, dest = sys.argv[1], sys.argv[2]
skills = json.load(open(lock))["skills"]
for name, meta in skills.items():
    if not os.path.isdir(os.path.join(dest, name)):
        print(f'{name}\t{meta["sourceUrl"]}\t{meta["skillPath"]}')
PY
)

  if [ -z "$missing" ]; then
    echo "  all $(python3 -c "import json;print(len(json.load(open('$lock'))['skills']))") locked skills already present"
    return 0
  fi

  tmp=$(mktemp -d)
  # shellcheck disable=SC2064
  trap "rm -rf '$tmp'" EXIT

  echo "$missing" | while IFS="$(printf '\t')" read -r name url path; do
    [ -z "$name" ] && continue
    repo_dir="$tmp/$(echo "$url" | tr '/:' '__')"
    if [ ! -d "$repo_dir" ]; then
      echo "  cloning $url"
      git clone --depth 1 --quiet "$url" "$repo_dir" 2>/dev/null || {
        echo "    failed to clone $url — skipping $name"
        continue
      }
    fi
    # skillPath points at the SKILL.md; the skill is its containing directory.
    src_dir="$repo_dir/$(dirname "$path")"
    if [ -d "$src_dir" ]; then
      cp -R "$src_dir" "$AGENTS_SKILLS/$name"
      echo "  restored $name"
    else
      echo "    $path not found in $url — skipping $name"
    fi
  done
}

restore_skills

# Claude reads skills from ~/.claude/skills; point each one at ~/.agents/skills.
# Skip *.backup directories — link() creates those when it replaces a real
# directory with a symlink, and they are not skills.
for skill in "$AGENTS_SKILLS"/*/; do
  [ -d "$skill" ] || continue
  name=$(basename "$skill")
  case "$name" in
    *.backup) continue ;;
  esac
  link "$AGENTS_SKILLS/$name" "$CLAUDE_SKILLS/$name"
done

echo "  Claude configuration ready ($(ls "$CLAUDE_SKILLS" | wc -l | tr -d ' ') skills)"
