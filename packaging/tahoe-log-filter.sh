#!/usr/bin/env bash
# Filter a tahoe.log (stdin) down to known-safe lines for the public CI log (#59).
# Allowlist first, then redact: any pb: token (with or without //, any prefix),
# any furl= / furl: value, and any base32-ish run of 20+ [a-z2-7] (tub-id /
# swissnum length). Lines not on the allowlist (e.g. a furl's continuation on
# the next line, a bare swissnum or fragment) are dropped, not printed.
# v0.1.5: the base32 rule runs first, and the base32, hex and uppercase rules
# redact the whole [A-Za-z0-9] token that holds their run. In v0.1.4 the hex
# rule ran first and could eat the hex-alphabet prefix of a base32 secret glued
# to a 32+ hex run, leaving a sub-20 base32 remnant that leaked.
# v0.1.5 also adds: unpadded base64url runs of 40+ [A-Za-z0-9_-]; mixed-case
# base32 runs of 32+ [A-Za-z2-7]; 3+ dashed groups of exactly 8 [a-z2-7].
# Mixed-case runs of 20-31 stay out: they look like CamelCase class names.
# v0.1.4 added (each only redacts more):
#   hex runs of 32+ [0-9a-fA-F]; padded base64 (16+ chars then = or ==);
#   unpadded base64-alphabet runs of 40+; uppercase base32 runs of 20+
#   [A-Z2-7]; and 5+ groups of exactly 4 [a-z2-7] joined by "-" or " "
#   (a swissnum chunked for reading), bounded by non-alphanumerics.
# Known limit: a base32 fragment shorter than 20 chars on an allowlisted line
# is not redacted; it is indistinguishable from an ordinary word or path part.
# v0.1.7: a 40+ [A-Za-z0-9_-] token is redacted only when it has a digit, or
# both an uppercase and a lowercase letter. A long snake_case or UPPER_SNAKE
# name stays. The check is the same pipeline slot as the old blanket rule.
set -euo pipefail
LC_ALL=C
TS='^[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9:.]+[^ ]* '
KEY='(start|Start|listen|Listen|port|Port|lock|Lock|pid|twistd|Traceback|Error|error|Exception|exit|Exit|stop|Stop|Unhandled|Failure|in use|denied|version)'
grep -E "(${TS}.*${KEY})|^Traceback|^[[:space:]]+File \"|^[A-Za-z_.]*(Error|Exception)(:|$)" \
  | sed -E \
      -e 's#pb:[^[:space:]]*#pb:REDACTED#g' \
      -e 's#([Ff][Uu][Rr][Ll][^=:]*[=:]).*#\1 REDACTED#' \
      -e 's#[A-Za-z0-9]*[a-z2-7]{20,}[A-Za-z0-9]*#REDACTED#g' \
      -e 's#[A-Za-z0-9]*[0-9a-fA-F]{32,}[A-Za-z0-9]*#REDACTED#g' \
      -e 's#[A-Za-z0-9+/]{16,}={1,2}#REDACTED#g' \
      -e 's#[A-Za-z0-9+/]{40,}#REDACTED#g' \
  | awk '
{
  line = $0
  out = ""
  while (match(line, /[A-Za-z0-9_-]{40,}/)) {
    token = substr(line, RSTART, RLENGTH)
    if (token ~ /[0-9]/ || (token ~ /[A-Z]/ && token ~ /[a-z]/))
      token = "REDACTED"
    out = out substr(line, 1, RSTART - 1) token
    line = substr(line, RSTART + RLENGTH)
  }
  print out line
}
' \
  | sed -E \
      -e 's#[A-Za-z0-9]*[A-Z2-7]{20,}[A-Za-z0-9]*#REDACTED#g' \
      -e 's#[A-Za-z0-9]*[A-Za-z2-7]{32,}[A-Za-z0-9]*#REDACTED#g' \
      -e 's#(^|[^A-Za-z0-9])[a-z2-7]{8}(-[a-z2-7]{8}){2,}([^A-Za-z0-9]|$)#\1REDACTED\3#g' \
      -e 's#(^|[^A-Za-z0-9])[a-z2-7]{4}(-[a-z2-7]{4}){4,}([^A-Za-z0-9]|$)#\1REDACTED\3#g' \
      -e 's#(^|[^A-Za-z0-9])[a-z2-7]{4}( [a-z2-7]{4}){4,}([^A-Za-z0-9]|$)#\1REDACTED\3#g' \
  || true
