#!/bin/sh
# Runs before the envsubst step. MEDIA_CDN_ORIGIN goes straight into the Content-Security-Policy,
# so it must be empty or exactly one https origin: no wildcard, path, ';' or whitespace that could
# widen the policy.
set -eu

origin="${MEDIA_CDN_ORIGIN:-}"
[ -z "$origin" ] && exit 0

fail() {
    echo "MEDIA_CDN_ORIGIN rejected: $1 (expected something like https://cdn.example.com)" >&2
    exit 1
}

# Any character outside this set (including newline, ';', '*', space, quotes) is refused.
case "$origin" in
    *[!A-Za-z0-9.:/-]*) fail "contains characters not allowed in an origin" ;;
esac
printf '%s' "$origin" | grep -Eq '^https://[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?(:[0-9]{1,5})?$' \
    || fail "must be https://host[:port] with no path"
