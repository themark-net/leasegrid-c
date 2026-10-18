#!/usr/bin/env bash
# Fixture for `semgrep --test tools/semgrep`.
awk '{
# ruleid: awk-interval-expression
  while (match(line, /[A-Za-z0-9_-]{40,}/)) { line = substr(line, RSTART + RLENGTH) }
# ruleid: awk-interval-expression
  if ($0 ~ /[a-z2-7]{20,}/) print "x"
# ok: awk-interval-expression
  while (match(line, /[A-Za-z0-9_-][A-Za-z0-9_-]*/)) { line = substr(line, RSTART + RLENGTH) }
}'
# ok: awk-interval-expression
sed -E 's#[a-z2-7]{20,}#REDACTED#g'
