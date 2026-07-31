alias ls="lsd"
alias la="lsd -al"
alias ll="lsd -l"

# `c` is a function (see functions.zsh), not an alias. As an alias its "$1"
# expanded at definition time to the empty string, so `c foo` ran
# `open -a Cursor foo` only by accident of argument order and `c` alone
# silently opened nothing.

# Reload the shell after editing dotfiles.
alias reload="exec zsh"
