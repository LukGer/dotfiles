# Open a path in Cursor, defaulting to the current directory.
c() {
  open "${1:-.}" -a "Cursor"
}

# Stage everything, commit with the given message, push.
gp() {
  if [ -z "$1" ]; then
    echo "usage: gp <commit message>" >&2
    return 1
  fi
  git add . &&
  git commit -m "$1" &&
  git push
}
