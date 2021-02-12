#!/bin/sh
set -e
prog="${0##*/}"

main() {
  local become
  if [ "$1" = --sudo ]; then
    shift
    become=yes
  fi

  local cmd="$( which "${prog%.sh}" )"
  set -x
  ${become:+sudo -E} "$cmd" --traceback "$@"
}

main "$@"
