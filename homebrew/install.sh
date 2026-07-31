#!/bin/sh
#
# Homebrew
#
# Installs Homebrew itself if missing. Package installation is driven by the
# Brewfile via script/install, not from here.
#
# CREDIT: https://github.com/haacked/dotfiles/blob/main/homebrew/install.sh

if ! command -v brew >/dev/null 2>&1
then
  echo "  Installing Homebrew for you."
  NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Apple Silicon installs to /opt/homebrew, which isn't on PATH until the shell
# is reconfigured — make brew usable for the rest of this run.
if ! command -v brew >/dev/null 2>&1
then
  if test -x /opt/homebrew/bin/brew
  then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif test -x /usr/local/bin/brew
  then
    eval "$(/usr/local/bin/brew shellenv)"
  fi
fi

# Fail loudly rather than letting every later brew call fail confusingly.
if ! command -v brew >/dev/null 2>&1
then
  echo "  Homebrew is not available on PATH. Install it from https://brew.sh and re-run." >&2
  exit 1
fi

echo "  Homebrew ready: $(brew --version | head -1)"
