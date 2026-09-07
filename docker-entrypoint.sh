#!/bin/sh
# Give a first `docker compose up` something to render.
#
# The mounted directory starts empty, and a board with no config.yaml is a
# stack trace rather than a screen. So: if DINKYDASH_CONFIG names a file that is
# not there yet, seed it from the documented example and carry on.
#
# Deliberately not in the app. `FileStore` inventing a config would be magic in
# the engine, and the one place this belongs is the container that owns the
# empty directory. In cloud mode DINKYDASH_CONFIG is unset and this does
# nothing at all.
set -e

if [ -n "$DINKYDASH_CONFIG" ] && [ ! -f "$DINKYDASH_CONFIG" ]; then
    mkdir -p "$(dirname "$DINKYDASH_CONFIG")"
    cp /app/config.example.yaml "$DINKYDASH_CONFIG"
    echo "Seeded $DINKYDASH_CONFIG from config.example.yaml — edit it at /settings."
fi

exec "$@"
