#!/bin/sh
#
# Claude Code configuration.
#
# Links the global AGENTS.md / CLAUDE.md and settings.json, then restores and
# updates skills. AGENTS.md is the shared source of truth; CLAUDE.md imports
# it via @AGENTS.md so Claude Code and other agents stay in sync. Codex reads
# it from ~/.codex/AGENTS.md.
#
# Skills need care because this repo is public. Nearly all installed skills
# come from other people's repositories (the bulk from mattpocock/skills) —
# those are NOT committed here; committing them would republish someone's work
# and leave it to rot at whatever revision it was vendored at. Instead
# ai/skill-lock.json records where each came from, this script re-fetches the
# missing ones and the skills.sh CLI pulls the rest up to their latest
# revisions. Only self-authored skills live in ai/skills/.

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

mkdir -p "$HOME/.codex"
link "$DOTFILES/ai/AGENTS.md" "$HOME/.claude/AGENTS.md"
link "$DOTFILES/ai/CLAUDE.md" "$HOME/.claude/CLAUDE.md"
link "$DOTFILES/ai/AGENTS.md" "$HOME/.agents/AGENTS.md"
link "$DOTFILES/ai/AGENTS.md" "$HOME/.codex/AGENTS.md"
link "$DOTFILES/ai/settings.json" "$HOME/.claude/settings.json"
link "$DOTFILES/ai/skill-lock.json" "$HOME/.agents/.skill-lock.json"

# Self-authored skills.
for skill in "$DOTFILES"/ai/skills/*/; do
  [ -d "$skill" ] || continue
  name=$(basename "$skill")
  link "$DOTFILES/ai/skills/$name" "$AGENTS_SKILLS/$name"
done

# Third-party skills are synced against their source repos: skills deleted
# upstream are removed, missing ones restored from the lock file, every skill
# of a followed repo installed, and the rest updated to their latest revision.
# Each distinct source repo is shallow-cloned once into a temp dir.
LOCK="$DOTFILES/ai/skill-lock.json"

# `update` only refreshes skills already in the lock, so skills added upstream
# never arrive. For repos we follow wholesale, install every skill they ship.
FOLLOWED_SKILL_REPOS="mattpocock/skills"

SOURCES=$(mktemp -d)
# shellcheck disable=SC2064
trap "rm -rf '$SOURCES'" EXIT

# Prints the clone dir of a source repo, cloning it on first use.
clone_source() {
  repo_dir="$SOURCES/$(echo "$1" | tr '/:' '__')"
  if [ ! -d "$repo_dir" ]; then
    git clone --depth 1 --quiet "$1" "$repo_dir" 2>/dev/null || return 1
  fi
  echo "$repo_dir"
}

# Prints name<TAB>sourceUrl<TAB>skillPath for every locked skill.
locked_skills() {
  python3 - "$LOCK" <<'PY2'
import json, sys
for name, meta in json.load(open(sys.argv[1]))["skills"].items():
    print(f'{name}\t{meta["sourceUrl"]}\t{meta["skillPath"]}')
PY2
}

# A skill is deprecated when its source repo no longer ships a skill of that
# name anywhere — a skill that only moved directories is kept.
prune_skills() {
  locked_skills | while IFS="$(printf '\t')" read -r name url path; do
    repo_dir=$(clone_source "$url") || {
      echo "    failed to clone $url — keeping $name"
      continue
    }
    [ -f "$repo_dir/$path" ] && continue
    find "$repo_dir" -path "*/$name/SKILL.md" | grep -q . && continue
    echo "  removing $name (deleted from $url)"
    npx -y skills@latest remove "$name" -g -y >/dev/null ||
      echo "    failed to remove $name"
  done
}

restore_skills() {
  locked_skills | while IFS="$(printf '\t')" read -r name url path; do
    [ -d "$AGENTS_SKILLS/$name" ] && continue
    repo_dir=$(clone_source "$url") || {
      echo "    failed to clone $url — skipping $name"
      continue
    }
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

add_followed_skills() {
  for repo in $FOLLOWED_SKILL_REPOS; do
    echo "  installing all skills from $repo"
    npx -y skills@latest add "$repo" -g -s '*' -a universal -y >/dev/null ||
      echo "    failed to install skills from $repo"
  done
}

# Skills already on disk are left at whatever revision they were first cloned
# at, so refresh them through the skills.sh CLI. It owns the lock file (the
# symlink above puts ~/.agents/.skill-lock.json in this repo) and records the
# new revisions there, so a `dot` run leaves ai/skill-lock.json dirty whenever
# an upstream skill has moved — commit it.
update_skills() {
  echo "  updating skills from skills.sh"
  npx -y skills@latest update -g -y || echo "    skill update failed — skills left at their current revisions"
}

if ! command -v python3 >/dev/null 2>&1 || ! command -v npx >/dev/null 2>&1; then
  echo "  python3 or npx not found — skipping skill sync"
elif [ -f "$LOCK" ]; then
  prune_skills
  restore_skills
  add_followed_skills
  update_skills
fi

# Drop links left behind by removed skills.
find "$CLAUDE_SKILLS" -maxdepth 1 -type l ! -exec test -e {} \; -print | while read -r dead; do
  rm "$dead"
  echo "  unlinked $(basename "$dead")"
done

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

# agent-browser skill needs the CLI + a Chrome for Testing binary. Formula is
# in the Brewfile; this only downloads Chromium when the CLI is already on PATH.
if command -v agent-browser >/dev/null 2>&1; then
  if [ ! -d "$HOME/.agent-browser/browsers" ] || [ -z "$(ls -A "$HOME/.agent-browser/browsers" 2>/dev/null)" ]; then
    echo "  installing agent-browser Chromium"
    agent-browser install
  else
    echo "  agent-browser Chromium already present"
  fi
else
  echo "  agent-browser CLI not on PATH — brew bundle (Brewfile) then re-run"
fi

echo "  Claude configuration ready ($(ls "$CLAUDE_SKILLS" | wc -l | tr -d ' ') skills)"
