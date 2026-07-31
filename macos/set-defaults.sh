#!/bin/sh
#
# Sets reasonable macOS defaults.
#
# NOT run automatically by script/bootstrap or bin/dot — read it first, then
# run it yourself. Some of these need a logout or a Finder/Dock restart.
#
# CREDIT: https://github.com/holman/dotfiles/blob/master/macos/set-defaults.sh
# (Safari and hostname sections dropped; Chrome and Cursor are the browsers
# and editors in use here.)

if test ! "$(uname)" = "Darwin"
then
  exit 0
fi

# Use AirDrop over every interface.
defaults write com.apple.NetworkBrowser BrowseAllInterfaces -bool true

# Finder: list view everywhere.
defaults write com.apple.finder FXPreferredViewStyle -string "Nlsv"

# Finder: show hidden files, all filename extensions, and the path bar.
defaults write com.apple.finder AppleShowAllFiles -bool true
defaults write NSGlobalDomain AppleShowAllExtensions -bool true
defaults write com.apple.finder ShowPathbar -bool true

# Finder: show volumes on the desktop.
defaults write com.apple.finder ShowExternalHardDrivesOnDesktop -bool true
defaults write com.apple.finder ShowRemovableMediaOnDesktop -bool true

# Unhide ~/Library.
chflags nohidden ~/Library

# Screensaver on the bottom-left hot corner.
defaults write com.apple.dock wvous-bl-corner -int 5
defaults write com.apple.dock wvous-bl-modifier -int 0

# Avoid creating .DS_Store files on network and USB volumes.
defaults write com.apple.desktopservices DSDontWriteNetworkStores -bool true
defaults write com.apple.desktopservices DSDontWriteUSBStores -bool true

# Apply the settings that need a relaunch.
for app in Finder Dock SystemUIServer; do
  killall "$app" >/dev/null 2>&1
done

echo "macOS defaults applied. Some changes need a logout to take effect."
