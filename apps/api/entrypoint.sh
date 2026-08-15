#!/bin/sh
# Baked into the image and invoked directly (no inline "sh -c '...&&...'"
# string in any platform's config) — that pattern broke on Render, which
# doesn't shell-parse a dockerCommand value the way a real shell would: it
# was looking up "alembic upgrade head && uvicorn ... --port 10000" as one
# literal (space-and-all) executable name rather than parsing && as a shell
# operator. A real script sidesteps the ambiguity entirely, and works
# identically on Render, the self-hosted VM, and local `docker run`.
set -e
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
