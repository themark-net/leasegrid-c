#!/usr/bin/env bash
# Filter a tahoe.log (stdin) down to known-safe lines for the public CI log (#59).
# Allowlist first, then redact: any pb: token (with or without //, any prefix),
# any furl= / furl: value, and any base32-ish run of 20+ [a-z2-7] (tub-id /
# swissnum length). Lines not on the allowlist (e.g. a furl's continuation on
# the next line, a bare swissnum or fragment) are dropped, not printed.
set -euo pipefail
LC_ALL=C
TS='^[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9:.]+[^ ]* '
KEY='(start|Start|listen|Listen|port|Port|lock|Lock|pid|twistd|Traceback|Error|error|Exception|exit|Exit|stop|Stop|Unhandled|Failure|in use|denied|version)'
grep -E "(${TS}.*${KEY})|^Traceback|^[[:space:]]+File \"|^[A-Za-z_.]*(Error|Exception)(:|$)" \
  | sed -E \
      -e 's#pb:[^[:space:]]*#pb:REDACTED#g' \
      -e 's#([Ff][Uu][Rr][Ll][^=:]*[=:]).*#\1 REDACTED#' \
      -e 's#[a-z2-7]{20,}#REDACTED#g' \
  || true
